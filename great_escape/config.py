from pathlib import Path

APP_NAME = "The Great Escape"
APP_VERSION = "1.5.0"
DESTINATION_RETENTION_COUNT = 5
CONFIG_DIR = Path.home() / ".config" / "the-great-escape"
CONFIG_FILE = CONFIG_DIR / "settings.json"
DEFAULT_ARCHIVE_DIR = Path.home() / "Backups" / "The-Great-Escape"
DEFAULT_LOG_DIR = CONFIG_DIR / "logs"
DEFAULT_SOURCES: list[str] = []
DEFAULT_LOCAL_DESTINATIONS: list[str] = []

DEFAULT_APPEARANCE: dict[str, str | int] = {
    "ttk_theme": "clam",
    "font_family": "TkDefaultFont",
    "base_font_size": 11,
    "heading_font_size": 17,
    "treeview_font_size": 11,
    "button_font_size": 11,
    "background": "#f0f0f0",
    "foreground": "#202020",
    "surface": "#ffffff",
    "accent": "#2f6fed",
    "selection_foreground": "#ffffff",
}
