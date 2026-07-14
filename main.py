#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""The Great Escape

A Tkinter/TTK GUI for creating a highly compressed .tar.xz archive and then
copying that completed archive to multiple local folders and rclone remotes.

Designed for Linux, including Raspberry Pi OS, with:
    python3, tar, xz, and optionally rclone

Compression uses GNU tar with multi-threaded xz. Thread count is configurable.

The archive is built once. Only after tar/xz finishes successfully is the
archive copied/uploaded to the enabled destinations.
"""

from __future__ import annotations

import json
import os
import queue
import shlex
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk


APP_NAME = "The Great Escape"
APP_VERSION = "1.1.0"
CONFIG_DIR = Path.home() / ".config" / "the-great-escape"
CONFIG_FILE = CONFIG_DIR / "settings.json"
DEFAULT_ARCHIVE_DIR = Path.home() / "Backups" / "The-Great-Escape"
DEFAULT_LOG_DIR = CONFIG_DIR / "logs"

DEFAULT_SOURCES: list[str] = []

DEFAULT_LOCAL_DESTINATIONS: list[str] = []


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


class BackupApp(tk.Tk):
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

    # ------------------------------------------------------------------
    # GUI construction
    # ------------------------------------------------------------------

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        available = style.theme_names()
        if "clam" in available:
            style.theme_use("clam")
        style.configure("Title.TLabel", font=("TkDefaultFont", 16, "bold"))
        style.configure("Section.TLabelframe.Label", font=("TkDefaultFont", 11, "bold"))
        style.configure("Treeview", rowheight=27)

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Save Settings", command=self._save_settings)
        file_menu.add_command(label="Reload Settings", command=self._reload_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        tools_menu = tk.Menu(menubar, tearoff=False)
        tools_menu.add_command(label="Check Required Programs", command=lambda: self._check_requirements(True))
        tools_menu.add_command(label="Open rclone Config", command=self._open_rclone_config)
        tools_menu.add_command(label="List rclone Remotes", command=self._show_rclone_remotes)
        tools_menu.add_separator()
        tools_menu.add_command(label="Open Log Folder", command=self._open_log_folder)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Build one compressed archive, then distribute it to local folders and rclone remotes.",
        ).pack(anchor="w", pady=(0, 10))

        toolbar = ttk.Frame(outer)
        toolbar.pack(fill="x", pady=(0, 10))

        self.start_button = ttk.Button(toolbar, text="▶ Start Backup", command=self._start_backup)
        self.start_button.pack(side="left")
        self.cancel_button = ttk.Button(
            toolbar, text="■ Cancel", command=self._cancel_backup, state="disabled"
        )
        self.cancel_button.pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Save Settings", command=self._save_settings).pack(side="left", padx=(6, 0))
        ttk.Label(toolbar, textvariable=self.status_var).pack(side="right")

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)

        self.sources_tab = ttk.Frame(notebook, padding=10)
        self.destinations_tab = ttk.Frame(notebook, padding=10)
        self.options_tab = ttk.Frame(notebook, padding=10)
        self.log_tab = ttk.Frame(notebook, padding=10)

        notebook.add(self.sources_tab, text="1. Sources")
        notebook.add(self.destinations_tab, text="2. Destinations")
        notebook.add(self.options_tab, text="3. Archive Options")
        notebook.add(self.log_tab, text="4. Activity Log")

        self._build_sources_tab()
        self._build_destinations_tab()
        self._build_options_tab()
        self._build_log_tab()

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(10, 0))

        self.progress = ttk.Progressbar(bottom, mode="determinate", maximum=100)
        self.progress.pack(fill="x")
        ttk.Label(bottom, textvariable=self.progress_text_var).pack(anchor="w", pady=(3, 6))

        ttk.Label(bottom, textvariable=self.status_var).pack(anchor="w")

    def _build_sources_tab(self) -> None:
        frame = ttk.LabelFrame(self.sources_tab, text="Files and folders to include", style="Section.TLabelframe", padding=8)
        frame.pack(fill="both", expand=True)

        columns = ("enabled", "type", "path")
        self.source_tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended")
        self.source_tree.heading("enabled", text="Use")
        self.source_tree.heading("type", text="Type")
        self.source_tree.heading("path", text="Path")
        self.source_tree.column("enabled", width=55, anchor="center", stretch=False)
        self.source_tree.column("type", width=90, anchor="center", stretch=False)
        self.source_tree.column("path", width=750)
        self.source_tree.pack(side="left", fill="both", expand=True)
        self.source_tree.bind("<Double-1>", lambda _event: self._toggle_selected_sources())

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.source_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.source_tree.configure(yscrollcommand=scrollbar.set)

        buttons = ttk.Frame(self.sources_tab)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Add Files", command=self._add_files).pack(side="left")
        ttk.Button(buttons, text="Add Folder", command=self._add_folder).pack(side="left", padx=5)
        ttk.Button(buttons, text="Enable / Disable", command=self._toggle_selected_sources).pack(side="left")
        ttk.Button(buttons, text="Remove", command=self._remove_selected_sources).pack(side="left", padx=5)
        ttk.Button(buttons, text="Clear", command=self._clear_sources).pack(side="left")

    def _build_destinations_tab(self) -> None:
        local_frame = ttk.LabelFrame(
            self.destinations_tab,
            text="Local destination folders",
            style="Section.TLabelframe",
            padding=8,
        )
        local_frame.pack(fill="both", expand=True, pady=(0, 8))

        self.local_tree = ttk.Treeview(local_frame, columns=("enabled", "path"), show="headings", height=7)
        self.local_tree.heading("enabled", text="Use")
        self.local_tree.heading("path", text="Folder")
        self.local_tree.column("enabled", width=55, anchor="center", stretch=False)
        self.local_tree.column("path", width=780)
        self.local_tree.pack(side="left", fill="both", expand=True)
        self.local_tree.bind("<Double-1>", lambda _event: self._toggle_selected_local())
        local_scroll = ttk.Scrollbar(local_frame, orient="vertical", command=self.local_tree.yview)
        local_scroll.pack(side="right", fill="y")
        self.local_tree.configure(yscrollcommand=local_scroll.set)

        local_buttons = ttk.Frame(self.destinations_tab)
        local_buttons.pack(fill="x", pady=(0, 8))
        ttk.Button(local_buttons, text="Add Local Folder", command=self._add_local_destination).pack(side="left")
        ttk.Button(local_buttons, text="Enable / Disable", command=self._toggle_selected_local).pack(side="left", padx=5)
        ttk.Button(local_buttons, text="Remove", command=self._remove_selected_local).pack(side="left")

        remote_frame = ttk.LabelFrame(
            self.destinations_tab,
            text="rclone destinations",
            style="Section.TLabelframe",
            padding=8,
        )
        remote_frame.pack(fill="both", expand=True)

        self.rclone_tree = ttk.Treeview(
            remote_frame,
            columns=("enabled", "remote", "folder", "target"),
            show="headings",
            height=7,
        )
        for name, text, width in (
            ("enabled", "Use", 55),
            ("remote", "Remote", 160),
            ("folder", "Remote folder", 250),
            ("target", "Full target", 380),
        ):
            self.rclone_tree.heading(name, text=text)
            self.rclone_tree.column(name, width=width, anchor="center" if name == "enabled" else "w")
        self.rclone_tree.pack(side="left", fill="both", expand=True)
        self.rclone_tree.bind("<Double-1>", lambda _event: self._toggle_selected_rclone())
        remote_scroll = ttk.Scrollbar(remote_frame, orient="vertical", command=self.rclone_tree.yview)
        remote_scroll.pack(side="right", fill="y")
        self.rclone_tree.configure(yscrollcommand=remote_scroll.set)

        remote_buttons = ttk.Frame(self.destinations_tab)
        remote_buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(remote_buttons, text="Add rclone Destination", command=self._add_rclone_destination).pack(side="left")
        ttk.Button(remote_buttons, text="Edit", command=self._edit_rclone_destination).pack(side="left", padx=5)
        ttk.Button(remote_buttons, text="Enable / Disable", command=self._toggle_selected_rclone).pack(side="left")
        ttk.Button(remote_buttons, text="Remove", command=self._remove_selected_rclone).pack(side="left", padx=5)
        ttk.Button(remote_buttons, text="Run rclone Config", command=self._open_rclone_config).pack(side="left")

    def _build_options_tab(self) -> None:
        archive_frame = ttk.LabelFrame(
            self.options_tab,
            text="Archive creation",
            style="Section.TLabelframe",
            padding=12,
        )
        archive_frame.pack(fill="x")
        archive_frame.columnconfigure(1, weight=1)

        ttk.Label(archive_frame, text="Working archive folder:").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(archive_frame, textvariable=self.archive_dir_var).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(archive_frame, text="Browse", command=self._choose_archive_dir).grid(row=0, column=2)

        ttk.Label(archive_frame, text="Archive filename prefix:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(archive_frame, textvariable=self.archive_prefix_var, width=30).grid(row=1, column=1, sticky="w", padx=8)

        ttk.Label(archive_frame, text="Compression:").grid(row=2, column=0, sticky="w", pady=5)
        compression_combo = ttk.Combobox(
            archive_frame,
            textvariable=self.compression_var,
            values=("Maximum (xz -9e)", "High (xz -9)", "Balanced (xz -6)"),
            state="readonly",
            width=25,
        )
        compression_combo.grid(row=2, column=1, sticky="w", padx=8)

        ttk.Label(archive_frame, text="Compression threads:").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Spinbox(archive_frame, from_=1, to=max(1, os.cpu_count() or 1), textvariable=self.threads_var, width=7).grid(
            row=3, column=1, sticky="w", padx=8
        )
        ttk.Label(archive_frame, text=f"Detected CPU threads: {os.cpu_count() or 1}. Use 4 on a Raspberry Pi 5.").grid(row=3, column=2, sticky="w")

        ttk.Checkbutton(
            archive_frame,
            text="Skip missing source paths instead of stopping",
            variable=self.skip_missing_var,
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=4)
        ttk.Checkbutton(
            archive_frame,
            text="Verify the completed tarball before copying it",
            variable=self.verify_archive_var,
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=4)
        ttk.Checkbutton(
            archive_frame,
            text="Keep the original tarball in the working archive folder",
            variable=self.keep_local_archive_var,
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=4)

        rclone_frame = ttk.LabelFrame(
            self.options_tab,
            text="rclone transfer settings",
            style="Section.TLabelframe",
            padding=12,
        )
        rclone_frame.pack(fill="x", pady=(10, 0))

        ttk.Label(rclone_frame, text="Parallel transfers:").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Spinbox(rclone_frame, from_=1, to=32, textvariable=self.rclone_transfers_var, width=7).grid(
            row=0, column=1, sticky="w", padx=8
        )
        ttk.Label(rclone_frame, text="Checkers:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Spinbox(rclone_frame, from_=1, to=64, textvariable=self.rclone_checkers_var, width=7).grid(
            row=1, column=1, sticky="w", padx=8
        )

        note = (
            "Maximum xz compression is CPU- and memory-intensive. The app creates the archive once, "
            "then distributes that finished file. rclone destinations must already be configured with 'rclone config'."
        )
        ttk.Label(self.options_tab, text=note, wraplength=900, justify="left").pack(anchor="w", pady=12)

    def _build_log_tab(self) -> None:
        frame = ttk.Frame(self.log_tab)
        frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(frame, wrap="word", state="disabled", font=("TkFixedFont", 10))
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.log_text.yview)
        scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scroll.set)

        row = ttk.Frame(self.log_tab)
        row.pack(fill="x", pady=(8, 0))
        ttk.Button(row, text="Clear Display", command=self._clear_log_display).pack(side="left")
        ttk.Button(row, text="Open Log Folder", command=self._open_log_folder).pack(side="left", padx=5)

    # ------------------------------------------------------------------
    # Tree/list operations
    # ------------------------------------------------------------------

    @staticmethod
    def _yes_no(value: bool) -> str:
        return "Yes" if value else "No"

    def _refresh_all_trees(self) -> None:
        self._refresh_source_tree()
        self._refresh_local_tree()
        self._refresh_rclone_tree()

    def _refresh_source_tree(self) -> None:
        self.source_tree.delete(*self.source_tree.get_children())
        for index, item in enumerate(self.sources):
            path = Path(item.path).expanduser()
            kind = "Folder" if path.is_dir() else "File" if path.is_file() else "Missing"
            self.source_tree.insert("", "end", iid=str(index), values=(self._yes_no(item.enabled), kind, item.path))

    def _refresh_local_tree(self) -> None:
        self.local_tree.delete(*self.local_tree.get_children())
        for index, item in enumerate(self.local_destinations):
            self.local_tree.insert("", "end", iid=str(index), values=(self._yes_no(item.enabled), item.path))

    def _refresh_rclone_tree(self) -> None:
        self.rclone_tree.delete(*self.rclone_tree.get_children())
        for index, item in enumerate(self.rclone_destinations):
            self.rclone_tree.insert(
                "", "end", iid=str(index),
                values=(self._yes_no(item.enabled), item.remote, item.folder, item.display_target),
            )

    def _add_files(self) -> None:
        files = filedialog.askopenfilenames(title="Select files to back up")
        existing = {str(Path(item.path).expanduser()) for item in self.sources}
        for filename in files:
            normalized = str(Path(filename).expanduser())
            if normalized not in existing:
                self.sources.append(SourceItem(normalized))
                existing.add(normalized)
        self._refresh_source_tree()

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select folder to back up")
        if folder and folder not in {item.path for item in self.sources}:
            self.sources.append(SourceItem(folder))
            self._refresh_source_tree()

    def _toggle_selected_sources(self) -> None:
        for iid in self.source_tree.selection():
            index = int(iid)
            self.sources[index].enabled = not self.sources[index].enabled
        self._refresh_source_tree()

    def _remove_selected_sources(self) -> None:
        for index in sorted((int(iid) for iid in self.source_tree.selection()), reverse=True):
            self.sources.pop(index)
        self._refresh_source_tree()

    def _clear_sources(self) -> None:
        if self.sources and messagebox.askyesno(APP_NAME, "Remove every source from the list?"):
            self.sources.clear()
            self._refresh_source_tree()

    def _add_local_destination(self) -> None:
        folder = filedialog.askdirectory(title="Select local backup destination")
        if folder and folder not in {item.path for item in self.local_destinations}:
            self.local_destinations.append(LocalDestination(folder))
            self._refresh_local_tree()

    def _toggle_selected_local(self) -> None:
        for iid in self.local_tree.selection():
            item = self.local_destinations[int(iid)]
            item.enabled = not item.enabled
        self._refresh_local_tree()

    def _remove_selected_local(self) -> None:
        for index in sorted((int(iid) for iid in self.local_tree.selection()), reverse=True):
            self.local_destinations.pop(index)
        self._refresh_local_tree()

    def _add_rclone_destination(self) -> None:
        remote = simpledialog.askstring(APP_NAME, "rclone remote name (example: apple or gdrive):", parent=self)
        if not remote:
            return
        remote = remote.strip().rstrip(":")
        folder = simpledialog.askstring(
            APP_NAME,
            "Folder inside that remote (example: Backups):",
            initialvalue="Backups",
            parent=self,
        )
        if folder is None:
            return
        self.rclone_destinations.append(RcloneDestination(remote=remote, folder=folder.strip("/")))
        self._refresh_rclone_tree()

    def _edit_rclone_destination(self) -> None:
        selected = self.rclone_tree.selection()
        if len(selected) != 1:
            messagebox.showinfo(APP_NAME, "Select one rclone destination to edit.")
            return
        item = self.rclone_destinations[int(selected[0])]
        remote = simpledialog.askstring(APP_NAME, "rclone remote name:", initialvalue=item.remote, parent=self)
        if not remote:
            return
        folder = simpledialog.askstring(APP_NAME, "Remote folder:", initialvalue=item.folder, parent=self)
        if folder is None:
            return
        item.remote = remote.strip().rstrip(":")
        item.folder = folder.strip("/")
        self._refresh_rclone_tree()

    def _toggle_selected_rclone(self) -> None:
        for iid in self.rclone_tree.selection():
            item = self.rclone_destinations[int(iid)]
            item.enabled = not item.enabled
        self._refresh_rclone_tree()

    def _remove_selected_rclone(self) -> None:
        for index in sorted((int(iid) for iid in self.rclone_tree.selection()), reverse=True):
            self.rclone_destinations.pop(index)
        self._refresh_rclone_tree()

    def _choose_archive_dir(self) -> None:
        folder = filedialog.askdirectory(title="Select working archive folder")
        if folder:
            self.archive_dir_var.set(folder)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _settings_dict(self) -> dict[str, Any]:
        return {
            "sources": [asdict(item) for item in self.sources],
            "local_destinations": [asdict(item) for item in self.local_destinations],
            "rclone_destinations": [asdict(item) for item in self.rclone_destinations],
            "archive_dir": self.archive_dir_var.get(),
            "archive_prefix": self.archive_prefix_var.get(),
            "threads": self.threads_var.get(),
            "compression": self.compression_var.get(),
            "skip_missing": self.skip_missing_var.get(),
            "verify_archive": self.verify_archive_var.get(),
            "keep_local_archive": self.keep_local_archive_var.get(),
            "rclone_transfers": self.rclone_transfers_var.get(),
            "rclone_checkers": self.rclone_checkers_var.get(),
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
            return

        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            self.sources = [SourceItem(**item) for item in data.get("sources", [])]
            self.local_destinations = [LocalDestination(**item) for item in data.get("local_destinations", [])]
            self.rclone_destinations = [RcloneDestination(**item) for item in data.get("rclone_destinations", [])]
            self.archive_dir_var.set(data.get("archive_dir", str(DEFAULT_ARCHIVE_DIR)))
            self.archive_prefix_var.set(data.get("archive_prefix", "backup"))
            self.threads_var.set(data.get("threads", min(4, os.cpu_count() or 1)))
            self.compression_var.set(data.get("compression", "Maximum (xz -9e)"))
            self.skip_missing_var.set(data.get("skip_missing", True))
            self.verify_archive_var.set(data.get("verify_archive", True))
            self.keep_local_archive_var.set(data.get("keep_local_archive", True))
            self.rclone_transfers_var.set(data.get("rclone_transfers", 4))
            self.rclone_checkers_var.set(data.get("rclone_checkers", 8))
        except Exception as exc:
            messagebox.showwarning(APP_NAME, f"Settings could not be loaded. Defaults will be used.\n\n{exc}")
            self.sources = [SourceItem(path) for path in DEFAULT_SOURCES]
            self.local_destinations = [LocalDestination(path) for path in DEFAULT_LOCAL_DESTINATIONS]

    def _reload_settings(self) -> None:
        self._load_settings()
        self._refresh_all_trees()
        self._log("Settings reloaded.")

    # ------------------------------------------------------------------
    # Backup workflow
    # ------------------------------------------------------------------

    def _start_backup(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return

        validation_error = self._validate_backup()
        if validation_error:
            messagebox.showerror(APP_NAME, validation_error)
            return

        self._save_settings(notify=False)
        self.cancel_event.clear()
        self.progress["value"] = 0
        self.progress_text_var.set("Starting backup…")
        self.status_var.set("Backup running")
        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")

        config_snapshot = self._settings_dict()
        self.worker_thread = threading.Thread(
            target=self._backup_worker,
            args=(config_snapshot,),
            daemon=True,
            name="backup-worker",
        )
        self.worker_thread.start()

    def _validate_backup(self) -> str | None:
        if shutil.which("tar") is None:
            return "The 'tar' program is not installed or is not in PATH."
        if shutil.which("xz") is None:
            return "The 'xz' program is not installed or is not in PATH."

        enabled_sources = [item for item in self.sources if item.enabled]
        if not enabled_sources:
            return "Enable at least one source file or folder."

        missing = [item.path for item in enabled_sources if not Path(item.path).expanduser().exists()]
        if missing and not self.skip_missing_var.get():
            return "These enabled sources do not exist:\n\n" + "\n".join(missing[:12])

        local_enabled = any(item.enabled for item in self.local_destinations)
        remote_enabled = any(item.enabled for item in self.rclone_destinations)
        if not local_enabled and not remote_enabled and not self.keep_local_archive_var.get():
            return "Enable a destination or choose to keep the archive in the working folder."

        if remote_enabled and shutil.which("rclone") is None:
            return "At least one rclone destination is enabled, but rclone is not installed or not in PATH."

        try:
            threads = int(self.threads_var.get())
            max_threads = max(1, os.cpu_count() or 1)
            if not 1 <= threads <= max_threads:
                return f"Compression threads must be between 1 and {max_threads}."
        except (ValueError, tk.TclError):
            return "Compression threads must be a whole number."

        prefix = self._safe_filename_prefix(self.archive_prefix_var.get())
        if not prefix:
            return "Enter an archive filename prefix."

        archive_dir = Path(self.archive_dir_var.get()).expanduser()
        try:
            archive_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return f"The working archive folder cannot be created:\n{exc}"
        if not os.access(archive_dir, os.W_OK):
            return f"The working archive folder is not writable:\n{archive_dir}"

        return None

    def _backup_worker(self, config: dict[str, Any]) -> None:
        log_file: Path | None = None
        archive_path: Path | None = None
        try:
            DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = DEFAULT_LOG_DIR / f"backup_{stamp}.log"
            self._queue("logfile", str(log_file))

            sources = [SourceItem(**item) for item in config["sources"] if item.get("enabled", True)]
            local_destinations = [
                LocalDestination(**item) for item in config["local_destinations"] if item.get("enabled", True)
            ]
            rclone_destinations = [
                RcloneDestination(**item) for item in config["rclone_destinations"] if item.get("enabled", True)
            ]

            valid_sources: list[Path] = []
            for source in sources:
                path = Path(source.path).expanduser()
                if path.exists():
                    valid_sources.append(path)
                elif config["skip_missing"]:
                    self._worker_log(log_file, f"WARNING: Skipping missing source: {path}")
                else:
                    raise FileNotFoundError(f"Source does not exist: {path}")

            if not valid_sources:
                raise RuntimeError("No enabled source paths exist.")

            archive_dir = Path(config["archive_dir"]).expanduser()
            archive_dir.mkdir(parents=True, exist_ok=True)
            prefix = self._safe_filename_prefix(config["archive_prefix"])
            archive_path = archive_dir / f"{prefix}_{stamp}.tar.xz"

            self._worker_log(log_file, "=" * 72)
            self._worker_log(log_file, f"{APP_NAME} {APP_VERSION}")
            self._worker_log(log_file, f"Archive: {archive_path}")
            self._worker_log(log_file, f"Sources: {len(valid_sources)}")
            self._worker_log(log_file, f"Compression threads: {config['threads']}")
            self._worker_log(log_file, "=" * 72)

            self._queue("progress", (5, "Preparing source list"))
            self._check_cancelled()

            self._create_archive(valid_sources, archive_path, config, log_file)
            self._queue("progress", (55, "Archive created"))

            if config["verify_archive"]:
                self._verify_archive(archive_path, log_file)
            self._queue("progress", (65, "Archive verified" if config["verify_archive"] else "Archive ready"))

            total_destinations = len(local_destinations) + len(rclone_destinations)
            completed = 0

            for destination in local_destinations:
                self._check_cancelled()
                self._copy_to_local(archive_path, Path(destination.path).expanduser(), log_file)
                completed += 1
                self._destination_progress(completed, total_destinations, f"Copied to {destination.path}")

            for destination in rclone_destinations:
                self._check_cancelled()
                self._copy_to_rclone(archive_path, destination, config, log_file)
                completed += 1
                self._destination_progress(completed, total_destinations, f"Uploaded to {destination.display_target}")

            if not config["keep_local_archive"]:
                archive_path.unlink(missing_ok=True)
                self._worker_log(log_file, "Removed working archive after successful distribution.")
                archive_path = None

            self._queue("progress", (100, "Backup completed successfully"))
            self._worker_log(log_file, "Backup completed successfully.")
            self._queue("finished", {"success": True, "archive": str(archive_path) if archive_path else None, "log": str(log_file)})

        except CancelledError:
            if archive_path and archive_path.exists():
                try:
                    archive_path.unlink()
                except OSError:
                    pass
            if log_file:
                self._worker_log(log_file, "Backup cancelled by user.")
            self._queue("finished", {"success": False, "cancelled": True, "log": str(log_file) if log_file else None})
        except Exception as exc:
            if archive_path and archive_path.exists():
                try:
                    archive_path.unlink()
                except OSError:
                    pass
            if log_file:
                self._worker_log(log_file, f"ERROR: {exc}")
            self._queue("finished", {"success": False, "error": str(exc), "log": str(log_file) if log_file else None})

    def _create_archive(self, sources: list[Path], archive_path: Path, config: dict[str, Any], log_file: Path) -> None:
        level = "-9e" if config["compression"].startswith("Maximum") else "-9" if config["compression"].startswith("High") else "-6"
        threads = max(1, min(os.cpu_count() or 1, int(config["threads"])))
        compressor = f"xz {level} -T{threads}"

        # GNU tar's -C entries preserve readable relative names and avoid storing
        # absolute paths. Duplicate basenames are allowed by tar, though restoring
        # one over another should be done carefully.
        command = [
            "tar",
            "--create",
            "--file", str(archive_path),
            f"--use-compress-program={compressor}",
            "--warning=no-file-changed",
        ]
        for source in sources:
            command.extend(["-C", str(source.parent), source.name])

        self._worker_log(log_file, "Creating compressed tarball.")
        self._worker_log(log_file, "Command: " + shlex.join(command))
        self._queue("progress", (10, "Compressing files with xz"))
        self._run_process(command, log_file, success_codes={0, 1})

        if not archive_path.exists() or archive_path.stat().st_size == 0:
            raise RuntimeError("tar/xz did not create a usable archive.")

        size = self._human_size(archive_path.stat().st_size)
        self._worker_log(log_file, f"Archive created: {archive_path} ({size})")

    def _verify_archive(self, archive_path: Path, log_file: Path) -> None:
        self._check_cancelled()
        self._worker_log(log_file, "Verifying archive integrity with tar -tJf.")
        self._queue("progress", (58, "Verifying archive integrity"))
        self._run_process(["tar", "-tJf", str(archive_path)], log_file, log_output=False)
        self._worker_log(log_file, "Archive verification passed.")

    def _copy_to_local(self, archive_path: Path, destination: Path, log_file: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        if not destination.is_dir():
            raise NotADirectoryError(f"Local destination is not a folder: {destination}")
        if not os.access(destination, os.W_OK):
            raise PermissionError(f"Local destination is not writable: {destination}")

        target = destination / archive_path.name
        partial = destination / f".{archive_path.name}.partial"
        self._worker_log(log_file, f"Copying archive to local destination: {target}")

        try:
            with archive_path.open("rb") as source_handle, partial.open("wb") as destination_handle:
                while True:
                    self._check_cancelled()
                    chunk = source_handle.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    destination_handle.write(chunk)
            shutil.copystat(archive_path, partial)
            partial.replace(target)
        finally:
            if partial.exists():
                partial.unlink(missing_ok=True)

        if target.stat().st_size != archive_path.stat().st_size:
            raise RuntimeError(f"Size verification failed after copying to {target}")
        self._worker_log(log_file, f"Local copy completed: {target}")

    def _copy_to_rclone(
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
            "--stats", "10s",
            "--stats-one-line",
            "--retries", "3",
            "--low-level-retries", "10",
            "--checksum",
            "-v",
        ]
        self._worker_log(log_file, f"Uploading archive with rclone: {target}")
        self._run_process(command, log_file)
        self._worker_log(log_file, f"rclone upload completed: {target}")

    def _destination_progress(self, completed: int, total: int, text: str) -> None:
        if total <= 0:
            percent = 95
        else:
            percent = 65 + int((completed / total) * 30)
        self._queue("progress", (min(percent, 95), text))

    def _run_process(
        self,
        command: list[str],
        log_file: Path,
        *,
        success_codes: set[int] | None = None,
        log_output: bool = True,
    ) -> None:
        success_codes = success_codes or {0}
        self._check_cancelled()

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        with self.process_lock:
            self.current_process = process

        try:
            assert process.stdout is not None
            for line in process.stdout:
                self._check_cancelled(process)
                clean = line.rstrip()
                if clean and log_output:
                    self._worker_log(log_file, clean)
            return_code = process.wait()
            self._check_cancelled()
            if return_code not in success_codes:
                raise RuntimeError(f"Command failed with exit code {return_code}: {shlex.join(command)}")
        finally:
            with self.process_lock:
                if self.current_process is process:
                    self.current_process = None

    def _check_cancelled(self, process: subprocess.Popen[str] | None = None) -> None:
        if not self.cancel_event.is_set():
            return
        if process and process.poll() is None:
            self._terminate_process_group(process)
        raise CancelledError()

    @staticmethod
    def _terminate_process_group(process: subprocess.Popen[str]) -> None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def _cancel_backup(self) -> None:
        if not self.worker_thread or not self.worker_thread.is_alive():
            return
        self.cancel_event.set()
        self.status_var.set("Cancelling…")
        self.progress_text_var.set("Stopping the active operation…")
        self.cancel_button.configure(state="disabled")
        with self.process_lock:
            process = self.current_process
        if process and process.poll() is None:
            self._terminate_process_group(process)

    # ------------------------------------------------------------------
    # Worker/UI messaging and logging
    # ------------------------------------------------------------------

    def _queue(self, kind: str, payload: Any) -> None:
        self.message_queue.put((kind, payload))

    def _process_messages(self) -> None:
        try:
            while True:
                kind, payload = self.message_queue.get_nowait()
                if kind == "log":
                    self._log(str(payload))
                elif kind == "progress":
                    percent, text = payload
                    self.progress["value"] = percent
                    self.progress_text_var.set(text)
                elif kind == "finished":
                    self._handle_finished(payload)
                elif kind == "logfile":
                    self._log(f"Log file: {payload}")
        except queue.Empty:
            pass
        self.after(100, self._process_messages)

    def _worker_log(self, log_file: Path, message: str) -> None:
        timestamped = f"{datetime.now():%Y-%m-%d %H:%M:%S} | {message}"
        try:
            with log_file.open("a", encoding="utf-8") as handle:
                handle.write(timestamped + "\n")
        except OSError:
            pass
        self._queue("log", timestamped)

    def _log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message.rstrip() + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log_display(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _handle_finished(self, result: dict[str, Any]) -> None:
        self.start_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.worker_thread = None

        if result.get("success"):
            self.status_var.set("Backup completed")
            archive = result.get("archive")
            text = "Backup completed successfully."
            if archive:
                text += f"\n\nWorking archive:\n{archive}"
            if result.get("log"):
                text += f"\n\nLog:\n{result['log']}"
            messagebox.showinfo(APP_NAME, text)
        elif result.get("cancelled"):
            self.status_var.set("Backup cancelled")
            self.progress_text_var.set("Backup cancelled")
            messagebox.showwarning(APP_NAME, "The backup was cancelled. Any incomplete working archive was removed.")
        else:
            self.status_var.set("Backup failed")
            self.progress_text_var.set("Backup failed")
            messagebox.showerror(APP_NAME, f"Backup failed:\n\n{result.get('error', 'Unknown error')}")

    # ------------------------------------------------------------------
    # Tools and helpers
    # ------------------------------------------------------------------

    def _check_requirements(self, show_success: bool = True) -> bool:
        checks = {
            "tar": shutil.which("tar"),
            "xz": shutil.which("xz"),
            "rclone": shutil.which("rclone"),
        }
        missing_required = [name for name in ("tar", "xz") if not checks[name]]
        lines = [f"{name}: {path or 'NOT FOUND'}" for name, path in checks.items()]
        self._log("Program check:\n  " + "\n  ".join(lines))

        if missing_required:
            messagebox.showerror(APP_NAME, "Missing required programs:\n\n" + "\n".join(missing_required))
            return False
        if show_success:
            rclone_note = "" if checks["rclone"] else "\n\nrclone is optional unless cloud destinations are enabled."
            messagebox.showinfo(APP_NAME, "Required archive programs were found." + rclone_note)
        return True

    def _open_rclone_config(self) -> None:
        if shutil.which("rclone") is None:
            messagebox.showerror(APP_NAME, "rclone is not installed or is not in PATH.")
            return
        try:
            subprocess.Popen(["x-terminal-emulator", "-e", "rclone", "config"])
        except FileNotFoundError:
            messagebox.showinfo(APP_NAME, "Open a terminal and run:\n\nrclone config")

    def _show_rclone_remotes(self) -> None:
        if shutil.which("rclone") is None:
            messagebox.showerror(APP_NAME, "rclone is not installed or is not in PATH.")
            return
        try:
            result = subprocess.run(["rclone", "listremotes"], text=True, capture_output=True, check=False, timeout=15)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "rclone returned an error")
            remotes = result.stdout.strip() or "No rclone remotes are configured."
            messagebox.showinfo(APP_NAME, remotes)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not list rclone remotes:\n{exc}")

    def _open_log_folder(self) -> None:
        DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.Popen(["xdg-open", str(DEFAULT_LOG_DIR)])
        except FileNotFoundError:
            messagebox.showinfo(APP_NAME, f"Log folder:\n{DEFAULT_LOG_DIR}")

    def _show_about(self) -> None:
        messagebox.showinfo(
            APP_NAME,
            f"{APP_NAME} {APP_VERSION}\n\n"
            "Creates a .tar.xz archive using GNU tar and multi-threaded xz, then distributes the completed archive "
            "to enabled local folders and rclone destinations. Settings are stored only in your home directory.",
        )

    def _on_close(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            if not messagebox.askyesno(APP_NAME, "A backup is running. Cancel it and exit?"):
                return
            self._cancel_backup()
        self._save_settings(notify=False)
        self.destroy()

    @staticmethod
    def _safe_filename_prefix(value: str) -> str:
        cleaned = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in value.strip())
        return cleaned.strip("_")

    @staticmethod
    def _human_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
            if value < 1024 or unit == "TiB":
                return f"{value:.1f} {unit}"
            value /= 1024
        return f"{value:.1f} TiB"


def main() -> None:
    app = BackupApp()
    app.mainloop()


if __name__ == "__main__":
    main()
