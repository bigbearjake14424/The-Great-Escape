import os
import shutil
import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from .config import APP_NAME


class BackupMixin:
    """GUI-facing backup actions; execution is delegated to BackupController."""

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
        enabled_databases = [item for item in self.database_profiles if item.enabled]
        if not enabled_sources and not enabled_databases:
            return "Enable at least one source file, folder, or database profile."

        missing = [
            item.path
            for item in enabled_sources
            if not Path(item.path).expanduser().exists()
        ]
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

    def _backup_worker(self, config: dict) -> None:
        result = self.backup_controller.run(config)
        self._queue("finished", result)

    def _cancel_backup(self) -> None:
        if not self.worker_thread or not self.worker_thread.is_alive():
            return
        self.cancel_event.set()
        self.status_var.set("Cancelling…")
        self.progress_text_var.set("Stopping the active operation…")
        self.cancel_button.configure(state="disabled")
        with self.process_lock:
            process = self.current_process
        self.process_runner.terminate_active(process)
