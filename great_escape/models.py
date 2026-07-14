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


class CancelledError(RuntimeError):
    """Raised internally when the user cancels a backup."""
