from dataclasses import dataclass


@dataclass
class SourceItem:
    path: str
    enabled: bool = True


@dataclass
class LocalDestination:
    path: str
    enabled: bool = True


@dataclass
class RcloneDestination:
    remote: str
    folder: str = "Backups"
    enabled: bool = True

    @property
    def display_target(self) -> str:
        folder = self.folder.strip("/")
        return f"{self.remote}:{folder}" if folder else f"{self.remote}:"


@dataclass
class DatabaseDumpProfile:
    name: str
    engine: str = "mysql"
    database: str = ""
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    executable: str = "auto"
    defaults_file: str = ""
    extra_args: str = ""
    all_databases: bool = False
    sqlite_path: str = ""
    enabled: bool = True

    @property
    def engine_label(self) -> str:
        return "SQLite" if self.engine.lower() == "sqlite" else "MySQL / MariaDB"

    @property
    def scope_label(self) -> str:
        if self.engine.lower() == "sqlite":
            return self.sqlite_path or "No SQLite file selected"
        return "All databases" if self.all_databases else self.database


class CancelledError(RuntimeError):
    """Raised internally when the user cancels a backup."""
