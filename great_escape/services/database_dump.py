from __future__ import annotations

import os
import shlex
import shutil
import sqlite3
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from ..models import DatabaseDumpProfile
from .process_runner import ProcessRunner


class DatabaseDumpService:
    def __init__(
        self,
        process_runner: ProcessRunner,
        log: Callable[[Path, str], None],
        safe_filename: Callable[[str], str],
        human_size: Callable[[int], str],
    ) -> None:
        self.process_runner = process_runner
        self.log = log
        self.safe_filename = safe_filename
        self.human_size = human_size

    @contextmanager
    def include_dumps(
        self,
        sources: list[Path],
        profiles: list[DatabaseDumpProfile],
        log_file: Path,
    ) -> Iterator[list[Path]]:
        enabled = [profile for profile in profiles if profile.enabled]
        if not enabled:
            yield list(sources)
            return
        with tempfile.TemporaryDirectory(prefix="the-great-escape-db-") as temp_name:
            dump_dir = Path(temp_name) / "database_dumps"
            dump_dir.mkdir(parents=True, exist_ok=True)
            for profile in enabled:
                self.process_runner.check_cancelled()
                if profile.engine.lower() == "sqlite":
                    self._dump_sqlite(profile, dump_dir, log_file)
                else:
                    self._dump_mysql(profile, dump_dir, log_file)
            yield [*sources, dump_dir]

    def _dump_sqlite(self, profile: DatabaseDumpProfile, dump_dir: Path, log_file: Path) -> None:
        source_path = Path(profile.sqlite_path).expanduser()
        if not source_path.is_file():
            raise FileNotFoundError(f"SQLite database does not exist: {source_path}")
        safe_name = self.safe_filename(profile.name) or source_path.stem or "sqlite"
        snapshot_path = dump_dir / f".{safe_name}.snapshot.sqlite3"
        output_path = dump_dir / f"{safe_name}.sql"
        self.log(log_file, f"Creating SQLite dump '{profile.name}' from {source_path}.")
        source_uri = source_path.resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(source_uri, uri=True) as source_connection:
            with sqlite3.connect(snapshot_path) as snapshot_connection:
                source_connection.backup(snapshot_connection)
        try:
            with sqlite3.connect(snapshot_path) as snapshot_connection:
                with output_path.open("w", encoding="utf-8", newline="\n") as output_handle:
                    for statement in snapshot_connection.iterdump():
                        self.process_runner.check_cancelled()
                        output_handle.write(statement + "\n")
        finally:
            snapshot_path.unlink(missing_ok=True)
        self._validate_output(profile.name, output_path)
        self.log(log_file, f"SQLite dump completed: {output_path.name} ({self.human_size(output_path.stat().st_size)})")

    def _dump_mysql(self, profile: DatabaseDumpProfile, dump_dir: Path, log_file: Path) -> None:
        executable = self._resolve_executable(profile.executable)
        safe_name = self.safe_filename(profile.name) or "database"
        scope = "all_databases" if profile.all_databases else self.safe_filename(profile.database)
        output_path = dump_dir / f"{safe_name}_{scope}.sql"
        command = [executable]
        if profile.defaults_file:
            defaults_path = Path(profile.defaults_file).expanduser()
            if not defaults_path.is_file():
                raise FileNotFoundError(f"Database defaults file does not exist: {defaults_path}")
            command.append(f"--defaults-extra-file={os.fspath(defaults_path)}")
        command.extend(["--host", profile.host, "--port", str(profile.port), "--user", profile.user, "--single-transaction", "--routines", "--events", "--triggers", "--hex-blob"])
        if profile.extra_args:
            command.extend(shlex.split(profile.extra_args, posix=os.name != "nt"))
        command.append("--all-databases" if profile.all_databases else "--databases")
        if not profile.all_databases:
            command.append(profile.database)
        self.log(log_file, f"Creating MySQL/MariaDB dump '{profile.name}' from {profile.host}:{profile.port}.")
        self.process_runner.run_to_file(command, output_path, error_label=f"Database dump '{profile.name}' failed")
        self._validate_output(profile.name, output_path)
        self.log(log_file, f"MySQL/MariaDB dump completed: {output_path.name} ({self.human_size(output_path.stat().st_size)})")

    @staticmethod
    def _resolve_executable(requested: str) -> str:
        if requested and requested.lower() != "auto":
            resolved = shutil.which(requested) or (requested if Path(requested).is_file() else None)
            if resolved:
                return os.fspath(resolved)
            raise FileNotFoundError(f"Database dump executable was not found: {requested}")
        for candidate in ("mariadb-dump", "mysqldump"):
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        raise FileNotFoundError("Neither mariadb-dump nor mysqldump was found in PATH.")

    @staticmethod
    def _validate_output(name: str, output_path: Path) -> None:
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"Database dump '{name}' produced an empty SQL file.")
