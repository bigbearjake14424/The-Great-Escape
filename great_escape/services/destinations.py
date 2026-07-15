from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..models import RcloneDestination
from .process_runner import ProcessRunner
from .retention import RetentionService


class DestinationService:
    def __init__(
        self,
        process_runner: ProcessRunner,
        retention: RetentionService,
        log: Callable[[Path, str], None],
    ) -> None:
        self.process_runner = process_runner
        self.retention = retention
        self.log = log

    def copy_local(self, archive_path: Path, destination: Path, log_file: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        if not destination.is_dir():
            raise NotADirectoryError(f"Local destination is not a folder: {destination}")
        if not os.access(destination, os.W_OK):
            raise PermissionError(f"Local destination is not writable: {destination}")
        target = destination / archive_path.name
        partial = destination / f".{archive_path.name}.partial"
        self.log(log_file, f"Copying archive to local destination: {target}")
        try:
            with archive_path.open("rb") as source_handle, partial.open("wb") as destination_handle:
                while True:
                    self.process_runner.check_cancelled()
                    chunk = source_handle.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    destination_handle.write(chunk)
            shutil.copystat(archive_path, partial)
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
        if target.stat().st_size != archive_path.stat().st_size:
            raise RuntimeError(f"Size verification failed after copying to {target}")
        self.log(log_file, f"Local copy completed: {target}")
        try:
            self.retention.prune_local(archive_path, destination, log_file)
        except Exception as exc:
            self.log(log_file, f"WARNING: Local retention cleanup failed for {destination}: {exc}")

    def copy_rclone(
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
            "--stats", "10s", "--stats-one-line", "--retries", "3",
            "--low-level-retries", "10", "--checksum", "-v",
        ]
        self.log(log_file, f"Uploading archive with rclone: {target}")
        self.process_runner.run(command, log_file)
        self.log(log_file, f"rclone upload completed: {target}")
        try:
            self.retention.prune_rclone(archive_path, destination, log_file)
        except Exception as exc:
            self.log(log_file, f"WARNING: rclone retention cleanup failed for {target}: {exc}")
