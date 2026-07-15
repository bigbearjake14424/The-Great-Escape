from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .config import APP_NAME
from .models import DatabaseDumpProfile


class DatabaseDumpMixin:
    """Build database-profile dialogs; dump execution belongs to DatabaseDumpService."""

    def _install_database_menu(self) -> None:
        menubar = self.nametowidget(self.cget("menu"))
        database_menu = tk.Menu(menubar, tearoff=False)
        database_menu.add_command(label="Manage Database Dumps…", command=self._show_database_profiles)
        menubar.insert_cascade(2, label="Databases", menu=database_menu)

    def _install_database_source_note(self) -> None:
        note = ttk.LabelFrame(
            self.sources_tab,
            text="Database backups",
            style="Section.TLabelframe",
            padding=8,
        )
        note.pack(fill="x", pady=(8, 0))
        ttk.Label(
            note,
            text=(
                "MySQL, MariaDB, and SQLite dumps can be generated automatically and included in this backup. "
                "Database profiles are managed separately from ordinary file and folder sources."
            ),
            wraplength=850,
            justify="left",
        ).pack(side="left", fill="x", expand=True)
        ttk.Button(note, text="Manage Database Dumps…", command=self._show_database_profiles).pack(
            side="right", padx=(8, 0)
        )

    def _show_database_profiles(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title(f"{APP_NAME} Database Dumps")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("1040x450")
        dialog.minsize(820, 380)

        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill="both", expand=True)
        columns = ("enabled", "name", "engine", "location", "user", "scope")
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        headings = {
            "enabled": "Use",
            "name": "Profile",
            "engine": "Database type",
            "location": "Server or file",
            "user": "User",
            "scope": "Database scope",
        }
        widths = {"enabled": 55, "name": 150, "engine": 135, "location": 260, "user": 110, "scope": 250}
        for column in columns:
            tree.heading(column, text=headings[column])
            tree.column(column, width=widths[column], anchor="center" if column == "enabled" else "w")
        tree.pack(fill="both", expand=True)

        def refresh() -> None:
            tree.delete(*tree.get_children())
            for index, profile in enumerate(self.database_profiles):
                location = profile.sqlite_path if profile.engine.lower() == "sqlite" else f"{profile.host}:{profile.port}"
                user = "—" if profile.engine.lower() == "sqlite" else profile.user
                tree.insert(
                    "",
                    "end",
                    iid=str(index),
                    values=(
                        "Yes" if profile.enabled else "No",
                        profile.name,
                        profile.engine_label,
                        location,
                        user,
                        profile.scope_label,
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
        ttk.Button(
            buttons,
            text="Save and Close",
            command=lambda: (self._save_settings(notify=False), dialog.destroy()),
        ).pack(side="right")
        ttk.Label(
            frame,
            text=(
                "MySQL/MariaDB passwords are never stored in JSON; use a protected client option file. "
                "SQLite uses Python's built-in sqlite3 module and needs no external dump program."
            ),
            wraplength=980,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))
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
            "engine": tk.StringVar(value=str(values.get("engine", "mysql"))),
            "database": tk.StringVar(value=str(values["database"])),
            "host": tk.StringVar(value=str(values["host"])),
            "port": tk.StringVar(value=str(values["port"])),
            "user": tk.StringVar(value=str(values["user"])),
            "executable": tk.StringVar(value=str(values["executable"])),
            "defaults_file": tk.StringVar(value=str(values["defaults_file"])),
            "extra_args": tk.StringVar(value=str(values["extra_args"])),
            "all_databases": tk.BooleanVar(value=bool(values["all_databases"])),
            "sqlite_path": tk.StringVar(value=str(values.get("sqlite_path", ""))),
            "enabled": tk.BooleanVar(value=bool(values["enabled"])),
        }

        body = ttk.Frame(dialog, padding=14)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        ttk.Label(body, text="Profile name:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=variables["name"], width=56).grid(
            row=0, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=4
        )
        ttk.Label(body, text="Database type:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(
            body,
            textvariable=variables["engine"],
            values=("mysql", "sqlite"),
            state="readonly",
            width=18,
        ).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=4)

        mysql_frame = ttk.LabelFrame(body, text="MySQL / MariaDB", padding=10)
        mysql_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 4))
        mysql_frame.columnconfigure(1, weight=1)
        mysql_rows = (
            ("Host:", "host"),
            ("Port:", "port"),
            ("User:", "user"),
            ("Database:", "database"),
            ("Dump executable:", "executable"),
            ("Defaults file:", "defaults_file"),
            ("Extra arguments:", "extra_args"),
        )
        for row, (label, key) in enumerate(mysql_rows):
            ttk.Label(mysql_frame, text=label).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Entry(mysql_frame, textvariable=variables[key], width=52).grid(
                row=row, column=1, sticky="ew", padx=(8, 0), pady=3
            )

        def browse_defaults() -> None:
            filename = filedialog.askopenfilename(title="Select MySQL/MariaDB option file", parent=dialog)
            if filename:
                variables["defaults_file"].set(filename)

        ttk.Button(mysql_frame, text="Browse", command=browse_defaults).grid(row=5, column=2, padx=(6, 0))
        ttk.Checkbutton(mysql_frame, text="Dump all databases", variable=variables["all_databases"]).grid(
            row=7, column=0, columnspan=3, sticky="w", pady=(5, 0)
        )

        sqlite_frame = ttk.LabelFrame(body, text="SQLite", padding=10)
        sqlite_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=4)
        sqlite_frame.columnconfigure(1, weight=1)
        ttk.Label(sqlite_frame, text="SQLite database file:").grid(row=0, column=0, sticky="w")
        ttk.Entry(sqlite_frame, textvariable=variables["sqlite_path"], width=52).grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )

        def browse_sqlite() -> None:
            filename = filedialog.askopenfilename(
                title="Select SQLite database",
                parent=dialog,
                filetypes=(("SQLite databases", "*.db *.sqlite *.sqlite3"), ("All files", "*.*")),
            )
            if filename:
                variables["sqlite_path"].set(filename)

        ttk.Button(sqlite_frame, text="Browse", command=browse_sqlite).grid(row=0, column=2, padx=(6, 0))
        ttk.Label(
            sqlite_frame,
            text="A consistent SQL dump is generated with Python's built-in sqlite3 backup API.",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Checkbutton(body, text="Enable this profile", variable=variables["enabled"]).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=6
        )

        result: list[DatabaseDumpProfile] = []

        def save() -> None:
            engine = variables["engine"].get().strip().lower()
            name = variables["name"].get().strip()
            if not name:
                messagebox.showerror(APP_NAME, "Enter a profile name.", parent=dialog)
                return
            if engine == "sqlite":
                sqlite_path = Path(variables["sqlite_path"].get()).expanduser()
                if not sqlite_path.is_file():
                    messagebox.showerror(APP_NAME, "Select an existing SQLite database file.", parent=dialog)
                    return
                port = 3306
            else:
                try:
                    port = int(variables["port"].get())
                    if not 1 <= port <= 65535:
                        raise ValueError
                except ValueError:
                    messagebox.showerror(APP_NAME, "Port must be a number from 1 to 65535.", parent=dialog)
                    return
                if not variables["all_databases"].get() and not variables["database"].get().strip():
                    messagebox.showerror(APP_NAME, "Enter a database name or select Dump all databases.", parent=dialog)
                    return
            result.append(
                DatabaseDumpProfile(
                    name=name,
                    engine=engine,
                    database=variables["database"].get().strip(),
                    host=variables["host"].get().strip() or "localhost",
                    port=port,
                    user=variables["user"].get().strip() or "root",
                    executable=variables["executable"].get().strip() or "auto",
                    defaults_file=variables["defaults_file"].get().strip(),
                    extra_args=variables["extra_args"].get().strip(),
                    all_databases=variables["all_databases"].get(),
                    sqlite_path=variables["sqlite_path"].get().strip(),
                    enabled=variables["enabled"].get(),
                )
            )
            dialog.destroy()

        controls = ttk.Frame(body)
        controls.grid(row=5, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(controls, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(controls, text="Save", command=save).pack(side="right", padx=(0, 6))
        dialog.wait_window()
        return result[0] if result else None
