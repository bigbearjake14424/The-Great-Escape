from pathlib import Path

APP_NAME = "The Great Escape"
APP_VERSION = "1.1.1"
CONFIG_DIR = Path.home() / ".config" / "the-great-escape"
CONFIG_FILE = CONFIG_DIR / "settings.json"
DEFAULT_ARCHIVE_DIR = Path.home() / "Backups" / "The-Great-Escape"
DEFAULT_LOG_DIR = CONFIG_DIR / "logs"
DEFAULT_SOURCES: list[str] = []
DEFAULT_LOCAL_DESTINATIONS: list[str] = []
