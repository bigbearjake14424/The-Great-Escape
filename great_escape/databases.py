from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .config import APP_NAME
from .models import DatabaseDumpProfile
from .platform_utils import popen_platform_options


class DatabaseDumpMixin:
    """Manage database dump profiles and add generated SQL files to archives."""

    def _install_database_menu(self) -> None:
        menubar = self.nametowidget(self.cget("menu"))
        database_menu = tk.Menu(menubar, tearoff=False)
        database_menu.add_command(label="Manage MySQL / MariaDB Dumps…", command=self._show_database_profiles)
        menubar.insert_cascade(2, label="Databases", menu=database_menu)

    def _show_database_profiles(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title(f"{APP_NAME} Database Dumps")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("940x430")
        dialog.minsize(760, 360)

        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill="both", expand=True)

        columns = ("enabled", "name", "server", "user", "scope", "executable")
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        headings = {
            "enabled": "Use",
            "name": "Profile",
            "server": "Server",
            "user": "User",
            "scope": "Database scope",
            "executable": "Dump program",
        }
        widths = {"enabled": 55, "name": 150, "server": 190, "user": 120, "scope": 190, "executable": 120}
        for column in columns:
            tree.heading(column, text=headings[column])
            tree.column(column, width=widths[column], anchor="center" if column == "enabled" else "w")
        tree.pack(fill="both", expand=True)

        def refresh() -> None:
            tree.delete(*tree.get_children())
            for index, profile in enumerate(self.database_profiles):
                tree.insert(
                    "",
                    "end",
                    iid=str(index),
                    values=(
                        "Yes" if profile.enabled else "No",
                        profile.name,
                        f"{profile.host}:{profile.port}",
                        profile.user,
                        profile.scope_label,
                        profile.executable,
                    ),
                )

        def selected_index() -> int | None:
            selection = tree.selection()
            return int(selection[0]) if selection else None

        def add_profile() -> None:
            profile = self._edit_database_profile(dialog, DatabaseDumpProfile(name="Database backup"))
            if profile:
                self.database_profiles.append(profile)
                refresh()

        def edit_profile() -> None:
            index = selected_index()
            if index is None:
                messagebox.showinfo(APP_NAME, "Select a database profile to edit.", parent=dialog)
                return
            updated = self._edit_database_profile(dialog, self.database_profiles[index])
            if updated:
                self.database_profiles[index] = updated
                refresh()

        def toggle_profile() -> None:
            index = selected_index()
            if index is not None:
                self.database_profiles[index].enabled = not self.database_profiles[index].enabled
                refresh()

        def remove_profile() -> None:
            index = selected_index()
            if index is not None and messagebox.askyesno(APP_NAME, "Remove the selected database profile?", parent=dialog):
                self.database_profiles.pop(index)
                refresh()

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Add", command=add_profile).pack(side="left")
        ttk.Button(buttons, text="Edit", command=edit_profile).pack(side="left", padx=5)
        ttk.Button(buttons, text="Enable / Disable", command=toggle_profile).pack(side="left")
        ttk.Button(buttons, text="Remove", command=remove_profile).pack(side="left", padx=5)
        ttk.Button(buttons, text="Save and Close", command=lambda: (self._save_settings(notify=False), dialog.destroy())).pack(side="right")

        note = (
            "Passwords are not stored in JSON. Use a MySQL/MariaDB client option file in Defaults file, "
            "for example ~/.my.cnf on Linux or an option file created for this app on Windows."
        )
        ttk.Label(frame, text=note, wraplength=880, justify="left").pack(anchor="w", pady=(10, 0))
        tree.bind("<Double-1>", lambda _event: edit_profile())
        refresh()

    def _edit_database_profile(
        self,
        parent: tk.Misc,
        profile: DatabaseDumpProfile,
    ) -> DatabaseDumpProfile | None:
        dialog = tk.Toplevel(parent)
        dialog.title("Database dump profile")
        dialog.transient(parent)
        dialog.grab_set()
        dialog.resizable(False, False)

        values = asdict(profile)
        variables = {
            "name": tk.StringVar(value=str(values["name"])),
            "database": tk.StringVar(value=str(values["database"])),
            "host": tk.StringVar(value=str(values["host"])),
            "port": tk.StringVar(value=str(values["port"])),
            "user": tk.StringVar(value=str(values["user"])),
            "executable": tk.StringVar(value=str(values["executable"])),
            "defaults_file": tk.StringVar(value=str(values["defaults_file"])),
            "extra_args": tk.StringVar(value=str(values["extra_args"])),
            "all_databases": tk.BooleanVar(value=bool(values["all_databases"])),
            "enabled": tk.BooleanVar(value=bool(values["enabled"])),
        }

        body = ttk.Frame(dialog, padding=14)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)

        rows = (
            ("Profile name:", "name"),
            ("Host:", "host"),
            ("Port:", "port"),
            ("User:", "user"),
            ("Database:", "database"),
            ("Dump executable:", "executable"),
            ("Defaults file:", "defaults_file"),
            ("Extra arguments:", "extra_args"),
        )
        for row, (label, key) in enumerate(rows):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Entry(body, textvariable=variables[key], width=54).grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=4)

        def browse_defaults() -> None:
            filename = filedialog.askopenfilename(title="Select MySQL/MariaDB option file", parent=dialog)
            if filename:
                variables["defaults_file"].set(filename)

        ttk.Button(body, text="Browse", command=browse_defaults).grid(row=6, column=2, padx=(6, 0))
        ttk.Label(body, text="Use 'auto', 'mysqldump', 'mariadb-dump', or a full executable path.").grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(4, 0)
        )
        ttk.Checkbutton(body, text="Dump all databases", variable=variables["all_databases"]).grid(
            row=9, column=0, columnspan=3, sticky="w", pady=4
        )
        ttk.Checkbutton(body, text="Enable this profile", variable=variables["enabled"]).grid(
            row=10, column=0, columnspan=3, sticky="w", pady=4
        )

        result: list[DatabaseDumpProfile] = []

        def save() -> None:
            try:
                port = int(variables["port"].get())
                if not 1 <= port <= 65535:
                    raise ValueError
            except ValueError:
                messagebox.showerror(APP_NAME, "Port must be a number from 1 to 65535.", parent=dialog)
                return
            name = variables["name"].get().strip()
            database = variables["database"].get().strip()
            all_databases = variables["all_databases"].get()
            if not name:
                messagebox.showerror(APP_NAME, "Enter a profile name.", parent=dialog)
                return
            if not all_databases and not database:
                messagebox.showerror(APP_NAME, "Enter a database name or select Dump all databases.", parent=dialog)
                return
            result.append(
                DatabaseDumpProfile(
                    name=name,
                    database=database,
                    host=variables["host"].get().strip() or "localhost",
                    port=port,
                    user=variables["user"].get().strip() or "root",
                    executable=variables["executable"].get().strip() or "auto",
                    defaults_file=variables["defaults_file"].get().strip(),
                    extra_args=variables["extra_args"].get().strip(),
                    all_databases=all_databases,
                    enabled=variables["enabled"].get(),
                )
            )
            dialog.destroy()

        controls = ttk.Frame(body)
        controls.grid(row=11, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(controls, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(controls, text="Save", command=save).pack(side="right", padx=(0, 6))
        dialog.wait_window()
        return result[0] if result else None

    def _create_archive(self, sources: list[Path], archive_path: Path, config: dict, log_file: Path) -> None:
        profiles = [DatabaseDumpProfile(**item) for item in config.get("database_profiles", []) if item.get("enabled", True)]
        if not profiles:
            super()._create_archive(sources, archive_path, config, log_file)
            return

        with tempfile.TemporaryDirectory(prefix="the-great-escape-db-") as temp_name:
            dump_dir = Path(temp_name) / "database_dumps"
            dump_dir.mkdir(parents=True, exist_ok=True)
            for profile in profiles:
                self._check_cancelled()
                self._dump_database(profile, dump_dir, log_file)
            super()._create_archive([*sources, dump_dir], archive_path, config, log_file)

    def _dump_database(self, profile: DatabaseDumpProfile, dump_dir: Path, log_file: Path) -> None:
        executable = self._resolve_dump_executable(profile.executable)
        safe_name = self._safe_filename_prefix(profile.name) or "database"
        scope = "all_databases" if profile.all_databases else self._safe_filename_prefix(profile.database)
        output_path = dump_dir / f"{safe_name}_{scope}.sql"

        command = [executable]
        if profile.defaults_file:
            defaults_path = Path(profile.defaults_file).expanduser()
            if not defaults_path.is_file():
                raise FileNotFoundError(f"Database defaults file does not exist: {defaults_path}")
            command.append(f"--defaults-extra-file={os.fspath(defaults_path)}")
        command.extend([
            "--host", profile.host,
            "--port", str(profile.port),
            "--user", profile.user,
            "--single-transaction",
            "--routines",
            "--events",
            "--triggers",
            "--hex-blob",
        ])
        if profile.extra_args:
            command.extend(shlex.split(profile.extra_args, posix=os.name != "nt"))
        if profile.all_databases:
            command.append("--all-databases")
        else:
            command.extend(["--databases", profile.database])

        self._worker_log(log_file, f"Creating database dump '{profile.name}' from {profile.host}:{profile.port}.")
        normalized = [os.fspath(argument) for argument in command]
        with output_path.open("wb") as output_handle:
            process = subprocess.Popen(
                normalized,
                stdout=output_handle,
                stderr=subprocess.PIPE,
                **popen_platform_options(),
            )
            with self.process_lock:
                self.current_process = process
            try:
                _stdout, stderr = process.communicate()
                self._check_cancelled(process)
                if process.returncode != 0:
                    detail = stderr.decode(errors="replace").strip() if stderr else "unknown database dump error"
                    raise RuntimeError(f"Database dump '{profile.name}' failed: {detail}")
            finally:
                with self.process_lock:
                    if self.current_process is process:
                        self.current_process = None
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"Database dump '{profile.name}' produced an empty SQL file.")
        self._worker_log(log_file, f"Database dump completed: {output_path.name} ({self._human_size(output_path.stat().st_size)})")

    @staticmethod
    def _resolve_dump_executable(requested: str) -> str:
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
