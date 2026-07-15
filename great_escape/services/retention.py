from __future__ import annotations

import fnmatch
import json
import subprocess
from collections.abc import Callable
from pathlib import Path

from ..config import DESTINATION_RETENTION_COUNT
from ..models import RcloneDestination
from .process_runner import ProcessRunner


class RetentionService:
    def __init__(
        self,
        process_runner: ProcessRunner,
        log: Callable[[Path, str], None],
    ) -> None:
        self.process_runner = process_runner
        self.log = log

    def prune_local(self, archive_path: Path, destination: Path, log_file: Path) -> None:
        pattern = self.archive_pattern(archive_path.name)
        candidates = [path for path in destination.iterdir() if path.is_file() and fnmatch.fnmatch(path.name, pattern)]
        candidates.sort(key=lambda path: (path.stat().st_mtime, path.name), reverse=True)
        for old_archive in candidates[DESTINATION_RETENTION_COUNT:]:
            self.process_runner.check_cancelled()
            old_archive.unlink()
            self.log(log_file, f"Retention removed local archive: {old_archive}")
        self.log(log_file, f"Local retention complete for {destination}: kept newest {min(len(candidates), DESTINATION_RETENTION_COUNT)} matching archive(s).")

    def prune_rclone(self, archive_path: Path, destination: RcloneDestination, log_file: Path) -> None:
        target = destination.display_target.rstrip("/")
        pattern = self.archive_pattern(archive_path.name)
        self.process_runner.check_cancelled()
        result = subprocess.run(["rclone", "lsjson", target, "--files-only", "--include", pattern], text=True, capture_output=True, check=False, timeout=120)
        self.process_runner.check_cancelled()
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown rclone error"
            raise RuntimeError(f"rclone lsjson failed: {detail}")
        entries = json.loads(result.stdout or "[]")
        files = [entry for entry in entries if not entry.get("IsDir", False) and fnmatch.fnmatch(str(entry.get("Name", "")), pattern)]
        files.sort(key=lambda entry: (str(entry.get("ModTime", "")), str(entry.get("Name", ""))), reverse=True)
        for entry in files[DESTINATION_RETENTION_COUNT:]:
            self.process_runner.check_cancelled()
            remote_path = f"{target}/{entry['Name']}"
            self.process_runner.run(["rclone", "deletefile", remote_path], log_file)
            self.log(log_file, f"Retention removed remote archive: {remote_path}")
        self.log(log_file, f"rclone retention complete for {target}: kept newest {min(len(files), DESTINATION_RETENTION_COUNT)} matching archive(s).")

    @staticmethod
    def archive_pattern(archive_name: str) -> str:
        suffix_length = len("_YYYYMMDD_HHMMSS.tar.xz")
        if len(archive_name) <= suffix_length or not archive_name.endswith(".tar.xz"):
            raise ValueError(f"Unexpected generated archive name: {archive_name}")
        prefix = archive_name[:-suffix_length]
        if not prefix:
            raise ValueError(f"Could not determine archive prefix from: {archive_name}")
        return f"{prefix}_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9].tar.xz"
