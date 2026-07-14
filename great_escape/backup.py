import os
import shlex
import shutil
import signal
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
import tkinter as tk
from tkinter import messagebox

from .config import APP_NAME, APP_VERSION, DEFAULT_LOG_DIR
from .models import CancelledError, LocalDestination, RcloneDestination, SourceItem


class BackupMixin:
    def _start_backup(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return

        validation_error = self._validate_backup()
        if validation_error:
            messagebox.showerror(APP_NAME, validation_error)
            return

        self._save_settings(notify=False)
        self.cancel_event.clear()
        self.progress["value"] = 0
        self.progress_text_var.set("Starting backup…")
        self.status_var.set("Backup running")
        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")

        config_snapshot = self._settings_dict()
        self.worker_thread = threading.Thread(
            target=self._backup_worker,
            args=(config_snapshot,),
            daemon=True,
            name="backup-worker",
        )
        self.worker_thread.start()

    def _validate_backup(self) -> str | None:
        if shutil.which("tar") is None:
            return "The 'tar' program is not installed or is not in PATH."
        if shutil.which("xz") is None:
            return "The 'xz' program is not installed or is not in PATH."

        enabled_sources = [item for item in self.sources if item.enabled]
        if not enabled_sources:
            return "Enable at least one source file or folder."

        missing = [item.path for item in enabled_sources if not Path(item.path).expanduser().exists()]
        if missing and not self.skip_missing_var.get():
            return "These enabled sources do not exist:\n\n" + "\n".join(missing[:12])

        local_enabled = any(item.enabled for item in self.local_destinations)
        remote_enabled = any(item.enabled for item in self.rclone_destinations)
        if not local_enabled and not remote_enabled and not self.keep_local_archive_var.get():
            return "Enable a destination or choose to keep the archive in the working folder."

        if remote_enabled and shutil.which("rclone") is None:
            return "At least one rclone destination is enabled, but rclone is not installed or not in PATH."

        try:
            threads = int(self.threads_var.get())
            max_threads = max(1, os.cpu_count() or 1)
            if not 1 <= threads <= max_threads:
                return f"Compression threads must be between 1 and {max_threads}."
        except (ValueError, tk.TclError):
            return "Compression threads must be a whole number."

        prefix = self._safe_filename_prefix(self.archive_prefix_var.get())
        if not prefix:
            return "Enter an archive filename prefix."

        archive_dir = Path(self.archive_dir_var.get()).expanduser()
        try:
            archive_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return f"The working archive folder cannot be created:\n{exc}"
        if not os.access(archive_dir, os.W_OK):
            return f"The working archive folder is not writable:\n{archive_dir}"

        return None

    def _backup_worker(self, config: dict[str, Any]) -> None:
        log_file: Path | None = None
        archive_path: Path | None = None
        try:
            DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = DEFAULT_LOG_DIR / f"backup_{stamp}.log"
            self._queue("logfile", str(log_file))

            sources = [SourceItem(**item) for item in config["sources"] if item.get("enabled", True)]
            local_destinations = [
                LocalDestination(**item) for item in config["local_destinations"] if item.get("enabled", True)
            ]
            rclone_destinations = [
                RcloneDestination(**item) for item in config["rclone_destinations"] if item.get("enabled", True)
            ]

            valid_sources: list[Path] = []
            for source in sources:
                path = Path(source.path).expanduser()
                if path.exists():
                    valid_sources.append(path)
                elif config["skip_missing"]:
                    self._worker_log(log_file, f"WARNING: Skipping missing source: {path}")
                else:
                    raise FileNotFoundError(f"Source does not exist: {path}")

            if not valid_sources:
                raise RuntimeError("No enabled source paths exist.")

            archive_dir = Path(config["archive_dir"]).expanduser()
            archive_dir.mkdir(parents=True, exist_ok=True)
            prefix = self._safe_filename_prefix(config["archive_prefix"])
            archive_path = archive_dir / f"{prefix}_{stamp}.tar.xz"

            self._worker_log(log_file, "=" * 72)
            self._worker_log(log_file, f"{APP_NAME} {APP_VERSION}")
            self._worker_log(log_file, f"Archive: {archive_path}")
            self._worker_log(log_file, f"Sources: {len(valid_sources)}")
            self._worker_log(log_file, f"Compression threads: {config['threads']}")
            self._worker_log(log_file, "=" * 72)

            self._queue("progress", (5, "Preparing source list"))
            self._check_cancelled()

            self._create_archive(valid_sources, archive_path, config, log_file)
            self._queue("progress", (55, "Archive created"))

            if config["verify_archive"]:
                self._verify_archive(archive_path, log_file)
            self._queue("progress", (65, "Archive verified" if config["verify_archive"] else "Archive ready"))

            total_destinations = len(local_destinations) + len(rclone_destinations)
            completed = 0

            for destination in local_destinations:
                self._check_cancelled()
                self._copy_to_local(archive_path, Path(destination.path).expanduser(), log_file)
                completed += 1
                self._destination_progress(completed, total_destinations, f"Copied to {destination.path}")

            for destination in rclone_destinations:
                self._check_cancelled()
                self._copy_to_rclone(archive_path, destination, config, log_file)
                completed += 1
                self._destination_progress(completed, total_destinations, f"Uploaded to {destination.display_target}")

            if not config["keep_local_archive"]:
                archive_path.unlink(missing_ok=True)
                self._worker_log(log_file, "Removed working archive after successful distribution.")
                archive_path = None

            self._queue("progress", (100, "Backup completed successfully"))
            self._worker_log(log_file, "Backup completed successfully.")
            self._queue("finished", {"success": True, "archive": str(archive_path) if archive_path else None, "log": str(log_file)})

        except CancelledError:
            if archive_path and archive_path.exists():
                try:
                    archive_path.unlink()
                except OSError:
                    pass
            if log_file:
                self._worker_log(log_file, "Backup cancelled by user.")
            self._queue("finished", {"success": False, "cancelled": True, "log": str(log_file) if log_file else None})
        except Exception as exc:
            if archive_path and archive_path.exists():
                try:
                    archive_path.unlink()
                except OSError:
                    pass
            if log_file:
                self._worker_log(log_file, f"ERROR: {exc}")
            self._queue("finished", {"success": False, "error": str(exc), "log": str(log_file) if log_file else None})

    def _create_archive(self, sources: list[Path], archive_path: Path, config: dict[str, Any], log_file: Path) -> None:
        level = "-9e" if config["compression"].startswith("Maximum") else "-9" if config["compression"].startswith("High") else "-6"
        threads = max(1, min(os.cpu_count() or 1, int(config["threads"])))
        compressor = f"xz {level} -T{threads}"

        command = [
            "tar",
            "--create",
            "--file", str(archive_path),
            f"--use-compress-program={compressor}",
            "--warning=no-file-changed",
        ]
        for source in sources:
            command.extend(["-C", str(source.parent), source.name])

        self._worker_log(log_file, "Creating compressed tarball.")
        self._worker_log(log_file, "Command: " + shlex.join(command))
        self._queue("progress", (10, "Compressing files with xz"))
        self._run_process(command, log_file, success_codes={0, 1})

        if not archive_path.exists() or archive_path.stat().st_size == 0:
            raise RuntimeError("tar/xz did not create a usable archive.")

        size = self._human_size(archive_path.stat().st_size)
        self._worker_log(log_file, f"Archive created: {archive_path} ({size})")

    def _verify_archive(self, archive_path: Path, log_file: Path) -> None:
        self._check_cancelled()
        self._worker_log(log_file, "Verifying archive integrity with tar -tJf.")
        self._queue("progress", (58, "Verifying archive integrity"))
        self._run_process(["tar", "-tJf", str(archive_path)], log_file, log_output=False)
        self._worker_log(log_file, "Archive verification passed.")

    def _copy_to_local(self, archive_path: Path, destination: Path, log_file: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        if not destination.is_dir():
            raise NotADirectoryError(f"Local destination is not a folder: {destination}")
        if not os.access(destination, os.W_OK):
            raise PermissionError(f"Local destination is not writable: {destination}")

        target = destination / archive_path.name
        partial = destination / f".{archive_path.name}.partial"
        self._worker_log(log_file, f"Copying archive to local destination: {target}")

        try:
            with archive_path.open("rb") as source_handle, partial.open("wb") as destination_handle:
                while True:
                    self._check_cancelled()
                    chunk = source_handle.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    destination_handle.write(chunk)
            shutil.copystat(archive_path, partial)
            partial.replace(target)
        finally:
            if partial.exists():
                partial.unlink(missing_ok=True)

        if target.stat().st_size != archive_path.stat().st_size:
            raise RuntimeError(f"Size verification failed after copying to {target}")
        self._worker_log(log_file, f"Local copy completed: {target}")

    def _copy_to_rclone(
        self,
        archive_path: Path,
        destination: RcloneDestination,
        config: dict[str, Any],
        log_file: Path,
    ) -> None:
        target = destination.display_target
        command = [
            "rclone", "copyto", str(archive_path), f"{target.rstrip('/')}/{archive_path.name}",
            "--transfers", str(max(1, int(config["rclone_transfers"]))),
            "--checkers", str(max(1, int(config["rclone_checkers"]))),
            "--stats", "10s",
            "--stats-one-line",
            "--retries", "3",
            "--low-level-retries", "10",
            "--checksum",
            "-v",
        ]
        self._worker_log(log_file, f"Uploading archive with rclone: {target}")
        self._run_process(command, log_file)
        self._worker_log(log_file, f"rclone upload completed: {target}")

    def _destination_progress(self, completed: int, total: int, text: str) -> None:
        if total <= 0:
            percent = 95
        else:
            percent = 65 + int((completed / total) * 30)
        self._queue("progress", (min(percent, 95), text))

    def _run_process(
        self,
        command: list[str | os.PathLike[str]],
        log_file: Path,
        *,
        success_codes: set[int] | None = None,
        log_output: bool = True,
    ) -> None:
        success_codes = success_codes or {0}
        self._check_cancelled()

        normalized_command = [os.fspath(argument) for argument in command]

        process = subprocess.Popen(
            normalized_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        with self.process_lock:
            self.current_process = process

        try:
            assert process.stdout is not None
            for line in process.stdout:
                self._check_cancelled(process)
                clean = line.rstrip()
                if clean and log_output:
                    self._worker_log(log_file, clean)
            return_code = process.wait()
            self._check_cancelled()
            if return_code not in success_codes:
                raise RuntimeError(
                    f"Command failed with exit code {return_code}: "
                    f"{shlex.join(normalized_command)}"
                )
        finally:
            with self.process_lock:
                if self.current_process is process:
                    self.current_process = None

    def _check_cancelled(self, process: subprocess.Popen[str] | None = None) -> None:
        if not self.cancel_event.is_set():
            return
        if process and process.poll() is None:
            self._terminate_process_group(process)
        raise CancelledError()

    @staticmethod
    def _terminate_process_group(process: subprocess.Popen[str]) -> None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def _cancel_backup(self) -> None:
        if not self.worker_thread or not self.worker_thread.is_alive():
            return
        self.cancel_event.set()
        self.status_var.set("Cancelling…")
        self.progress_text_var.set("Stopping the active operation…")
        self.cancel_button.configure(state="disabled")
        with self.process_lock:
            process = self.current_process
        if process and process.poll() is None:
            self._terminate_process_group(process)
