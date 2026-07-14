import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .config import APP_NAME
from .models import LocalDestination, RcloneDestination, SourceItem


class UIMixin:
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
        frame = ttk.LabelFrame(
            self.sources_tab,
            text="Files and folders to include",
            style="Section.TLabelframe",
            padding=8,
        )
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
        ttk.Spinbox(
            archive_frame,
            from_=1,
            to=max(1, os.cpu_count() or 1),
            textvariable=self.threads_var,
            width=7,
        ).grid(row=3, column=1, sticky="w", padx=8)
        ttk.Label(
            archive_frame,
            text=f"Detected CPU threads: {os.cpu_count() or 1}. Use 4 on a Raspberry Pi 5.",
        ).grid(row=3, column=2, sticky="w")

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
                "",
                "end",
                iid=str(index),
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
