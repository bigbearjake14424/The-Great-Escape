import os
import queue
import subprocess
import threading
from typing import Any
import tkinter as tk

from .backup import BackupMixin
from .config import APP_NAME, APP_VERSION, DEFAULT_ARCHIVE_DIR
from .messaging import MessagingMixin
from .models import LocalDestination, RcloneDestination, SourceItem
from .retention import RetentionMixin
from .settings import SettingsMixin
from .tools import ToolsMixin
from .ui import UIMixin


class BackupApp(
    UIMixin,
    SettingsMixin,
    RetentionMixin,
    BackupMixin,
    MessagingMixin,
    ToolsMixin,
    tk.Tk,
):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1120x760")
        self.minsize(900, 620)

        self.sources: list[SourceItem] = []
        self.local_destinations: list[LocalDestination] = []
        self.rclone_destinations: list[RcloneDestination] = []

        self.message_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.worker_thread: threading.Thread | None = None
        self.cancel_event = threading.Event()
        self.current_process: subprocess.Popen[str] | None = None
        self.process_lock = threading.Lock()

        self.archive_dir_var = tk.StringVar(value=str(DEFAULT_ARCHIVE_DIR))
        self.archive_prefix_var = tk.StringVar(value="backup")
        self.threads_var = tk.IntVar(value=min(4, os.cpu_count() or 1))
        self.compression_var = tk.StringVar(value="Maximum (xz -9e)")
        self.skip_missing_var = tk.BooleanVar(value=True)
        self.verify_archive_var = tk.BooleanVar(value=True)
        self.keep_local_archive_var = tk.BooleanVar(value=True)
        self.rclone_transfers_var = tk.IntVar(value=4)
        self.rclone_checkers_var = tk.IntVar(value=8)
        self.status_var = tk.StringVar(value="Ready")
        self.progress_text_var = tk.StringVar(value="No backup running")

        self._configure_styles()
        self._build_menu()
        self._build_ui()
        self._load_settings()
        self._refresh_all_trees()
        self._check_requirements(show_success=False)
        self.after(100, self._process_messages)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
