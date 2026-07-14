import json
import os
from copy import deepcopy
from dataclasses import asdict
from typing import Any
from tkinter import messagebox

from .config import (
    APP_NAME,
    CONFIG_DIR,
    CONFIG_FILE,
    DEFAULT_APPEARANCE,
    DEFAULT_ARCHIVE_DIR,
    DEFAULT_AUTOMATION,
    DEFAULT_LOCAL_DESTINATIONS,
    DEFAULT_SOURCES,
)
from .models import DatabaseDumpProfile, LocalDestination, RcloneDestination, SourceItem


class SettingsMixin:
    def _settings_dict(self) -> dict[str, Any]:
        return {
            "sources": [asdict(item) for item in self.sources],
            "local_destinations": [asdict(item) for item in self.local_destinations],
            "rclone_destinations": [asdict(item) for item in self.rclone_destinations],
            "database_profiles": [asdict(item) for item in self.database_profiles],
            "archive_dir": self.archive_dir_var.get(),
            "archive_prefix": self.archive_prefix_var.get(),
            "threads": self.threads_var.get(),
            "compression": self.compression_var.get(),
            "skip_missing": self.skip_missing_var.get(),
            "verify_archive": self.verify_archive_var.get(),
            "keep_local_archive": self.keep_local_archive_var.get(),
            "rclone_transfers": self.rclone_transfers_var.get(),
            "rclone_checkers": self.rclone_checkers_var.get(),
            "appearance": dict(self.appearance),
            "automation": dict(self.automation),
        }

    def _save_settings(self, notify: bool = True) -> None:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(json.dumps(self._settings_dict(), indent=2), encoding="utf-8")
            self._log(f"Settings saved to {CONFIG_FILE}")
            if notify:
                messagebox.showinfo(APP_NAME, "Settings saved.")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not save settings:\n{exc}")

    def _load_settings(self) -> None:
        if not CONFIG_FILE.exists():
            self.sources = [SourceItem(path) for path in DEFAULT_SOURCES]
            self.local_destinations = [LocalDestination(path) for path in DEFAULT_LOCAL_DESTINATIONS]
            self.rclone_destinations = []
            self.database_profiles = []
            self.appearance = deepcopy(DEFAULT_APPEARANCE)
            self.automation = deepcopy(DEFAULT_AUTOMATION)
            return

        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            self.sources = [SourceItem(**item) for item in data.get("sources", [])]
            self.local_destinations = [LocalDestination(**item) for item in data.get("local_destinations", [])]
            self.rclone_destinations = [RcloneDestination(**item) for item in data.get("rclone_destinations", [])]
            self.database_profiles = [DatabaseDumpProfile(**item) for item in data.get("database_profiles", [])]
            self.archive_dir_var.set(data.get("archive_dir", str(DEFAULT_ARCHIVE_DIR)))
            self.archive_prefix_var.set(data.get("archive_prefix", "backup"))
            self.threads_var.set(data.get("threads", min(4, os.cpu_count() or 1)))
            self.compression_var.set(data.get("compression", "Maximum (xz -9e)"))
            self.skip_missing_var.set(data.get("skip_missing", True))
            self.verify_archive_var.set(data.get("verify_archive", True))
            self.keep_local_archive_var.set(data.get("keep_local_archive", True))
            self.rclone_transfers_var.set(data.get("rclone_transfers", 4))
            self.rclone_checkers_var.set(data.get("rclone_checkers", 8))
            loaded_appearance = data.get("appearance", {})
            self.appearance = {**deepcopy(DEFAULT_APPEARANCE), **loaded_appearance}
            loaded_automation = data.get("automation", {})
            self.automation = {**deepcopy(DEFAULT_AUTOMATION), **loaded_automation}
        except Exception as exc:
            messagebox.showwarning(APP_NAME, f"Settings could not be loaded. Defaults will be used.\n\n{exc}")
            self.sources = [SourceItem(path) for path in DEFAULT_SOURCES]
            self.local_destinations = [LocalDestination(path) for path in DEFAULT_LOCAL_DESTINATIONS]
            self.rclone_destinations = []
            self.database_profiles = []
            self.appearance = deepcopy(DEFAULT_APPEARANCE)
            self.automation = deepcopy(DEFAULT_AUTOMATION)

    def _reload_settings(self) -> None:
        self._load_settings()
        self._apply_appearance()
        self._refresh_all_trees()
        self._apply_startup_settings()
        self._log("Settings reloaded and applied.")
