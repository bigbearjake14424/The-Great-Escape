from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .config import APP_NAME, APP_VERSION, DEFAULT_LOG_DIR
from .models import DatabaseDumpProfile, LocalDestination, RcloneDestination, SourceItem
from .services import ArchiveService, DatabaseDumpService, DestinationService, ProcessRunner


class BackupController:
    """Coordinate a backup using composed services instead of mixin ordering."""

    def __init__(
        self,
        process_runner: ProcessRunner,
        archive_service: ArchiveService,
        database_service: DatabaseDumpService,
        destination_service: DestinationService,
        queue_message,
        log,
        safe_filename,
    ) -> None:
        self.process_runner = process_runner
        self.archive_service = archive_service
        self.database_service = database_service
        self.destination_service = destination_service
        self.queue_message = queue_message
        self.log = log
        self.safe_filename = safe_filename

    def run(self, config: dict[str, Any]) -> dict[str, Any]:
        log_file: Path | None = None
        archive_path: Path | None = None
        try:
            DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = DEFAULT_LOG_DIR / f"backup_{stamp}.log"
            self.queue_message("logfile", str(log_file))

            sources = [SourceItem(**item) for item in config["sources"] if item.get("enabled", True)]
            local_destinations = [LocalDestination(**item) for item in config["local_destinations"] if item.get("enabled", True)]
            rclone_destinations = [RcloneDestination(**item) for item in config["rclone_destinations"] if item.get("enabled", True)]
            database_profiles = [DatabaseDumpProfile(**item) for item in config.get("database_profiles", []) if item.get("enabled", True)]

            valid_sources: list[Path] = []
            for source in sources:
                path = Path(source.path).expanduser()
                if path.exists():
                    valid_sources.append(path)
                elif config["skip_missing"]:
                    self.log(log_file, f"WARNING: Skipping missing source: {path}")
                else:
                    raise FileNotFoundError(f"Source does not exist: {path}")
            if not valid_sources and not database_profiles:
                raise RuntimeError("No enabled source paths or database profiles exist.")

            archive_dir = Path(config["archive_dir"]).expanduser()
            archive_dir.mkdir(parents=True, exist_ok=True)
            prefix = self.safe_filename(config["archive_prefix"])
            archive_path = archive_dir / f"{prefix}_{stamp}.tar.xz"

            self.log(log_file, "=" * 72)
            self.log(log_file, f"{APP_NAME} {APP_VERSION}")
            self.log(log_file, f"Archive: {archive_path}")
            self.log(log_file, f"File/folder sources: {len(valid_sources)}")
            self.log(log_file, f"Database profiles: {len(database_profiles)}")
            self.log(log_file, f"Compression threads: {config['threads']}")
            self.log(log_file, "=" * 72)

            self.queue_message("progress", (5, "Preparing source list"))
            self.process_runner.check_cancelled()
            with self.database_service.include_dumps(valid_sources, database_profiles, log_file) as archive_sources:
                self.archive_service.create(archive_sources, archive_path, config, log_file)
            self.queue_message("progress", (55, "Archive created"))

            if config["verify_archive"]:
                self.archive_service.verify(archive_path, log_file)
            self.queue_message("progress", (65, "Archive verified" if config["verify_archive"] else "Archive ready"))

            total = len(local_destinations) + len(rclone_destinations)
            completed = 0
            for destination in local_destinations:
                self.process_runner.check_cancelled()
                self.destination_service.copy_local(archive_path, Path(destination.path).expanduser(), log_file)
                completed += 1
                self._destination_progress(completed, total, f"Copied to {destination.path}")
            for destination in rclone_destinations:
                self.process_runner.check_cancelled()
                self.destination_service.copy_rclone(archive_path, destination, config, log_file)
                completed += 1
                self._destination_progress(completed, total, f"Uploaded to {destination.display_target}")

            if not config["keep_local_archive"]:
                archive_path.unlink(missing_ok=True)
                self.log(log_file, "Removed working archive after successful distribution.")
                archive_path = None

            self.queue_message("progress", (100, "Backup completed successfully"))
            self.log(log_file, "Backup completed successfully.")
            return {"success": True, "archive": str(archive_path) if archive_path else None, "log": str(log_file)}
        except Exception:
            if archive_path and archive_path.exists():
                archive_path.unlink(missing_ok=True)
            raise

    def _destination_progress(self, completed: int, total: int, text: str) -> None:
        percent = 95 if total <= 0 else 65 + int((completed / total) * 30)
        self.queue_message("progress", (min(percent, 95), text))
