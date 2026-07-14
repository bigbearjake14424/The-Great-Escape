import fnmatch
import json
import subprocess
from pathlib import Path

from .config import DESTINATION_RETENTION_COUNT
from .models import RcloneDestination


class RetentionMixin:
    """Prune older generated archives after successful destination copies."""

    def _copy_to_local(self, archive_path: Path, destination: Path, log_file: Path) -> None:
        super()._copy_to_local(archive_path, destination, log_file)
        try:
            self._prune_local_destination(archive_path, destination, log_file)
        except Exception as exc:
            self._worker_log(log_file, f"WARNING: Local retention cleanup failed for {destination}: {exc}")

    def _copy_to_rclone(
        self,
        archive_path: Path,
        destination: RcloneDestination,
        config: dict,
        log_file: Path,
    ) -> None:
        super()._copy_to_rclone(archive_path, destination, config, log_file)
        try:
            self._prune_rclone_destination(archive_path, destination, log_file)
        except Exception as exc:
            self._worker_log(
                log_file,
                f"WARNING: rclone retention cleanup failed for {destination.display_target}: {exc}",
            )

    def _prune_local_destination(self, archive_path: Path, destination: Path, log_file: Path) -> None:
        pattern = self._archive_retention_pattern(archive_path.name)
        candidates = [
            path
            for path in destination.iterdir()
            if path.is_file() and fnmatch.fnmatch(path.name, pattern)
        ]
        candidates.sort(key=lambda path: (path.stat().st_mtime, path.name), reverse=True)

        old_archives = candidates[DESTINATION_RETENTION_COUNT:]
        for old_archive in old_archives:
            self._check_cancelled()
            old_archive.unlink()
            self._worker_log(log_file, f"Retention removed local archive: {old_archive}")

        self._worker_log(
            log_file,
            f"Local retention complete for {destination}: kept newest "
            f"{min(len(candidates), DESTINATION_RETENTION_COUNT)} matching archive(s).",
        )

    def _prune_rclone_destination(
        self,
        archive_path: Path,
        destination: RcloneDestination,
        log_file: Path,
    ) -> None:
        target = destination.display_target.rstrip("/")
        pattern = self._archive_retention_pattern(archive_path.name)
        command = [
            "rclone",
            "lsjson",
            target,
            "--files-only",
            "--include",
            pattern,
        ]

        self._check_cancelled()
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )
        self._check_cancelled()

        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown rclone error"
            raise RuntimeError(f"rclone lsjson failed: {detail}")

        entries = json.loads(result.stdout or "[]")
        files = [
            entry
            for entry in entries
            if not entry.get("IsDir", False)
            and fnmatch.fnmatch(str(entry.get("Name", "")), pattern)
        ]
        files.sort(
            key=lambda entry: (str(entry.get("ModTime", "")), str(entry.get("Name", ""))),
            reverse=True,
        )

        old_archives = files[DESTINATION_RETENTION_COUNT:]
        for entry in old_archives:
            self._check_cancelled()
            name = str(entry["Name"])
            remote_path = f"{target}/{name}"
            self._run_process(["rclone", "deletefile", remote_path], log_file)
            self._worker_log(log_file, f"Retention removed remote archive: {remote_path}")

        self._worker_log(
            log_file,
            f"rclone retention complete for {target}: kept newest "
            f"{min(len(files), DESTINATION_RETENTION_COUNT)} matching archive(s).",
        )

    @staticmethod
    def _archive_retention_pattern(archive_name: str) -> str:
        suffix_length = len("_YYYYMMDD_HHMMSS.tar.xz")
        if len(archive_name) <= suffix_length or not archive_name.endswith(".tar.xz"):
            raise ValueError(f"Unexpected generated archive name: {archive_name}")

        prefix = archive_name[:-suffix_length]
        if not prefix:
            raise ValueError(f"Could not determine archive prefix from: {archive_name}")

        return f"{prefix}_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9].tar.xz"
