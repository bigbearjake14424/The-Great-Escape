from __future__ import annotations

from copy import deepcopy
from tkinter import colorchooser, font, messagebox, ttk
import tkinter as tk

from .config import APP_NAME, DEFAULT_APPEARANCE


class AppearanceMixin:
    """Apply and edit application-wide fonts, colors, and TTK styling."""

    def _initialize_appearance(self) -> None:
        self.appearance = deepcopy(DEFAULT_APPEARANCE)

    def _install_appearance_menu(self) -> None:
        menubar = self.nametowidget(self.cget("menu"))
        appearance_menu = tk.Menu(menubar, tearoff=False)
        appearance_menu.add_command(label="Customize…", command=self._show_appearance_dialog)
        appearance_menu.add_command(label="Reset to Defaults", command=self._reset_appearance)
        menubar.insert_cascade(2, label="Appearance", menu=appearance_menu)

    def _apply_appearance(self) -> None:
        values = {**DEFAULT_APPEARANCE, **self.appearance}
        style = ttk.Style(self)
        requested_theme = str(values["ttk_theme"])
        if requested_theme in style.theme_names():
            style.theme_use(requested_theme)
        elif "clam" in style.theme_names():
            style.theme_use("clam")

        family = str(values["font_family"])
        base_size = int(values["base_font_size"])
        heading_size = int(values["heading_font_size"])
        tree_size = int(values["treeview_font_size"])
        button_size = int(values["button_font_size"])
        background = str(values["background"])
        foreground = str(values["foreground"])
        surface = str(values["surface"])
        accent = str(values["accent"])
        selection_foreground = str(values["selection_foreground"])

        for named_font in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                current = font.nametofont(named_font)
                current.configure(family=family, size=base_size)
            except tk.TclError:
                pass

        self.configure(background=background)
        style.configure("TFrame", background=background)
        style.configure("TLabel", background=background, foreground=foreground, font=(family, base_size))
        style.configure("Title.TLabel", background=background, foreground=foreground, font=(family, heading_size, "bold"))
        style.configure("TLabelframe", background=background)
        style.configure("TLabelframe.Label", background=background, foreground=foreground, font=(family, base_size, "bold"))
        style.configure("Section.TLabelframe.Label", background=background, foreground=foreground, font=(family, base_size, "bold"))
        style.configure("TButton", font=(family, button_size), padding=(10, 6))
        style.configure("TCheckbutton", background=background, foreground=foreground, font=(family, base_size))
        style.configure("TEntry", fieldbackground=surface, foreground=foreground, font=(family, base_size))
        style.configure("TCombobox", fieldbackground=surface, foreground=foreground, font=(family, base_size))
        style.configure("TSpinbox", fieldbackground=surface, foreground=foreground, font=(family, base_size))
        style.configure("TNotebook", background=background)
        style.configure("TNotebook.Tab", font=(family, base_size), padding=(10, 5))
        style.configure(
            "Treeview",
            background=surface,
            fieldbackground=surface,
            foreground=foreground,
            font=(family, tree_size),
            rowheight=max(24, tree_size + 14),
        )
        style.configure("Treeview.Heading", font=(family, tree_size, "bold"))
        style.map("Treeview", background=[("selected", accent)], foreground=[("selected", selection_foreground)])
        style.configure("TProgressbar", background=accent)

        if hasattr(self, "log_text"):
            self.log_text.configure(
                background=surface,
                foreground=foreground,
                insertbackground=foreground,
                selectbackground=accent,
                selectforeground=selection_foreground,
                font=(family, base_size),
            )

    def _show_appearance_dialog(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title(f"{APP_NAME} Appearance")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        values = {**DEFAULT_APPEARANCE, **self.appearance}
        variables = {
            "ttk_theme": tk.StringVar(value=str(values["ttk_theme"])),
            "font_family": tk.StringVar(value=str(values["font_family"])),
            "base_font_size": tk.IntVar(value=int(values["base_font_size"])),
            "heading_font_size": tk.IntVar(value=int(values["heading_font_size"])),
            "treeview_font_size": tk.IntVar(value=int(values["treeview_font_size"])),
            "button_font_size": tk.IntVar(value=int(values["button_font_size"])),
            "background": tk.StringVar(value=str(values["background"])),
            "foreground": tk.StringVar(value=str(values["foreground"])),
            "surface": tk.StringVar(value=str(values["surface"])),
            "accent": tk.StringVar(value=str(values["accent"])),
            "selection_foreground": tk.StringVar(value=str(values["selection_foreground"])),
        }

        body = ttk.Frame(dialog, padding=14)
        body.grid(sticky="nsew")
        body.columnconfigure(1, weight=1)

        ttk.Label(body, text="TTK theme:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Combobox(
            body,
            textvariable=variables["ttk_theme"],
            values=ttk.Style(self).theme_names(),
            state="readonly",
            width=28,
        ).grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(body, text="Font family:").grid(row=1, column=0, sticky="w", pady=4)
        families = sorted(set(font.families(self)))
        ttk.Combobox(
            body,
            textvariable=variables["font_family"],
            values=families,
            state="readonly",
            width=28,
        ).grid(row=1, column=1, sticky="ew", pady=4)

        labels = (
            ("Base font size:", "base_font_size"),
            ("Heading font size:", "heading_font_size"),
            ("Treeview font size:", "treeview_font_size"),
            ("Button font size:", "button_font_size"),
        )
        row = 2
        for label, key in labels:
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Spinbox(body, from_=8, to=32, textvariable=variables[key], width=8).grid(
                row=row, column=1, sticky="w", pady=4
            )
            row += 1

        def choose_color(key: str) -> None:
            selected = colorchooser.askcolor(color=variables[key].get(), parent=dialog)[1]
            if selected:
                variables[key].set(selected)

        for label, key in (
            ("Window background:", "background"),
            ("Text color:", "foreground"),
            ("Entry/list background:", "surface"),
            ("Accent/selection:", "accent"),
            ("Selected text color:", "selection_foreground"),
        ):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", pady=4)
            holder = ttk.Frame(body)
            holder.grid(row=row, column=1, sticky="ew", pady=4)
            ttk.Entry(holder, textvariable=variables[key], width=14).pack(side="left", fill="x", expand=True)
            ttk.Button(holder, text="Choose…", command=lambda selected_key=key: choose_color(selected_key)).pack(
                side="left", padx=(6, 0)
            )
            row += 1

        def apply_changes(save: bool = False) -> None:
            try:
                updated = {key: variable.get() for key, variable in variables.items()}
                for size_key in ("base_font_size", "heading_font_size", "treeview_font_size", "button_font_size"):
                    updated[size_key] = int(updated[size_key])
                self.appearance = updated
                self._apply_appearance()
                if save:
                    self._save_settings(notify=False)
                    dialog.destroy()
            except (ValueError, tk.TclError) as exc:
                messagebox.showerror(APP_NAME, f"Could not apply appearance settings:\n{exc}", parent=dialog)

        buttons = ttk.Frame(body)
        buttons.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Apply", command=apply_changes).pack(side="left")
        ttk.Button(buttons, text="Save", command=lambda: apply_changes(True)).pack(side="left", padx=6)
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left")

    def _reset_appearance(self) -> None:
        if not messagebox.askyesno(APP_NAME, "Reset all fonts and colors to their defaults?"):
            return
        self.appearance = deepcopy(DEFAULT_APPEARANCE)
        self._apply_appearance()
        self._save_settings(notify=False)
