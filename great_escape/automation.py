from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from .config import APP_NAME, DEFAULT_AUTOMATION
from .platform_utils import maximize_window


class AutomationMixin:
    """Provide background tray operation and in-process backup scheduling."""

    def _initialize_automation(self) -> None:
        self.automation = deepcopy(DEFAULT_AUTOMATION)
        self.tray_icon = None
        self.tray_available = False
        self._scheduler_after_id: str | None = None
        self._exiting_application = False

    def _install_automation_menu(self) -> None:
        menubar = self.nametowidget(self.cget("menu"))
        automation_menu = tk.Menu(menubar, tearoff=False)
        automation_menu.add_command(label="Schedule and Background…", command=self._show_automation_dialog)
        automation_menu.add_separator()
        automation_menu.add_command(label="Hide to System Tray", command=self._hide_to_tray)
        menubar.insert_cascade(4, label="Automation", menu=automation_menu)

    def _apply_startup_settings(self) -> None:
        self._configure_drag_and_drop()
        if self.automation.get("tray_enabled", False):
            if not self._start_tray_icon(show_errors=False):
                self._disable_unavailable_tray_settings()
        self._start_scheduler()

        if self.automation.get("start_minimized", False) and self.tray_available:
            self.after_idle(self._hide_to_tray)
        else:
            self.after_idle(lambda: maximize_window(self))

    def _show_automation_dialog(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title(f"{APP_NAME} Automation")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        values = {**DEFAULT_AUTOMATION, **self.automation}
        variables = {
            "tray_enabled": tk.BooleanVar(value=bool(values["tray_enabled"])),
            "start_minimized": tk.BooleanVar(value=bool(values["start_minimized"])),
            "close_to_tray": tk.BooleanVar(value=bool(values["close_to_tray"])),
            "schedule_enabled": tk.BooleanVar(value=bool(values["schedule_enabled"])),
            "schedule_frequency": tk.StringVar(value=str(values["schedule_frequency"])),
            "schedule_weekday": tk.StringVar(value=str(values["schedule_weekday"])),
            "schedule_time": tk.StringVar(value=str(values["schedule_time"])),
        }

        body = ttk.Frame(dialog, padding=14)
        body.pack(fill="both", expand=True)

        tray_frame = ttk.LabelFrame(body, text="System tray", padding=10)
        tray_frame.pack(fill="x")
        ttk.Checkbutton(
            tray_frame,
            text="Enable a system tray icon while the application is running",
            variable=variables["tray_enabled"],
        ).pack(anchor="w", pady=3)
        ttk.Checkbutton(
            tray_frame,
            text="Start hidden in the system tray",
            variable=variables["start_minimized"],
        ).pack(anchor="w", pady=3)
        ttk.Checkbutton(
            tray_frame,
            text="Closing the window hides it to the tray instead of exiting",
            variable=variables["close_to_tray"],
        ).pack(anchor="w", pady=3)
        ttk.Label(
            tray_frame,
            text=(
                "System tray support requires pystray and Pillow. Some Linux desktops do not provide "
                "a compatible tray manager; the app will remain visible when no tray is available."
            ),
            wraplength=520,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        schedule_frame = ttk.LabelFrame(body, text="Automatic backup schedule", padding=10)
        schedule_frame.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(
            schedule_frame,
            text="Run backups automatically while The Great Escape is running",
            variable=variables["schedule_enabled"],
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=3)
        ttk.Label(schedule_frame, text="Frequency:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(
            schedule_frame,
            textvariable=variables["schedule_frequency"],
            values=("Daily", "Weekly"),
            state="readonly",
            width=18,
        ).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=4)
        ttk.Label(schedule_frame, text="Weekday:").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Combobox(
            schedule_frame,
            textvariable=variables["schedule_weekday"],
            values=("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
            state="readonly",
            width=18,
        ).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=4)
        ttk.Label(schedule_frame, text="Time (24-hour HH:MM):").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(schedule_frame, textvariable=variables["schedule_time"], width=10).grid(
            row=3, column=1, sticky="w", padx=(8, 0), pady=4
        )

        def save() -> None:
            schedule_time = variables["schedule_time"].get().strip()
            try:
                datetime.strptime(schedule_time, "%H:%M")
            except ValueError:
                messagebox.showerror(APP_NAME, "Schedule time must use 24-hour HH:MM format.", parent=dialog)
                return

            updated = {key: variable.get() for key, variable in variables.items()}
            updated["last_schedule_run"] = str(self.automation.get("last_schedule_run", ""))
            self.automation = {**deepcopy(DEFAULT_AUTOMATION), **updated}

            if self.automation["tray_enabled"]:
                if not self._start_tray_icon(show_errors=True):
                    self._disable_unavailable_tray_settings()
            else:
                self._stop_tray_icon()

            self._save_settings(notify=False)
            self._start_scheduler()
            dialog.destroy()

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="Save", command=save).pack(side="right", padx=(0, 6))

    def _start_scheduler(self) -> None:
        if self._scheduler_after_id:
            try:
                self.after_cancel(self._scheduler_after_id)
            except tk.TclError:
                pass
        self._scheduler_after_id = self.after(15_000, self._scheduler_tick)

    def _scheduler_tick(self) -> None:
        self._scheduler_after_id = None
        try:
            self._run_scheduled_backup_if_due()
        finally:
            if not self._exiting_application:
                self._scheduler_after_id = self.after(30_000, self._scheduler_tick)

    def _run_scheduled_backup_if_due(self) -> None:
        if not self.automation.get("schedule_enabled", False):
            return
        if self.worker_thread and self.worker_thread.is_alive():
            return

        now = datetime.now()
        try:
            scheduled = datetime.strptime(str(self.automation.get("schedule_time", "02:00")), "%H:%M").time()
        except ValueError:
            self._log("Automatic backup skipped because the saved schedule time is invalid.")
            return

        if now.time() < scheduled:
            return
        if str(self.automation.get("schedule_frequency", "Daily")) == "Weekly":
            if now.strftime("%A") != str(self.automation.get("schedule_weekday", "Sunday")):
                return

        run_key = now.date().isoformat()
        if str(self.automation.get("last_schedule_run", "")) == run_key:
            return

        self.automation["last_schedule_run"] = run_key
        self._save_settings(notify=False)
        self._log("Starting scheduled backup.")
        self._start_backup()

    def _start_tray_icon(self, show_errors: bool = True) -> bool:
        if self.tray_icon is not None:
            self.tray_available = True
            return True
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError:
            self.tray_available = False
            if show_errors:
                messagebox.showerror(
                    APP_NAME,
                    "System tray support requires pystray and Pillow.\n\n"
                    "Install them with:\npython -m pip install pystray Pillow",
                )
            return False

        backend_module = getattr(pystray.Icon, "__module__", "")
        if sys.platform.startswith("linux") and backend_module.endswith("._xorg"):
            available, detail = self._linux_x11_tray_manager_available()
            if not available:
                self.tray_available = False
                self._log(f"System tray disabled: {detail}")
                if show_errors:
                    messagebox.showwarning(
                        APP_NAME,
                        "This Linux desktop does not provide an X11 system-tray manager that pystray can use.\n\n"
                        "The Great Escape will continue running normally, but it cannot hide to a tray icon in "
                        "this desktop session. Keep the main window open for scheduled backups.\n\n"
                        "On desktops that support AppIndicator, installing the desktop's AppIndicator support "
                        "may provide a compatible tray.",
                    )
                return False

        image = Image.new("RGBA", (64, 64), (47, 111, 237, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((14, 12, 50, 52), outline="white", width=4)
        draw.line((20, 24, 44, 24), fill="white", width=4)
        draw.line((20, 34, 44, 34), fill="white", width=4)
        draw.line((20, 44, 36, 44), fill="white", width=4)

        def show_window(_icon: object = None, _item: object = None) -> None:
            self.after(0, self._show_from_tray)

        def start_backup(_icon: object = None, _item: object = None) -> None:
            self.after(0, self._start_backup)

        def exit_app(_icon: object = None, _item: object = None) -> None:
            self.after(0, self._exit_application)

        menu = pystray.Menu(
            pystray.MenuItem("Show The Great Escape", show_window, default=True),
            pystray.MenuItem("Start Backup", start_backup),
            pystray.MenuItem("Exit", exit_app),
        )
        self.tray_icon = pystray.Icon("the-great-escape", image, APP_NAME, menu)
        try:
            self.tray_icon.run_detached()
        except Exception as exc:
            self.tray_icon = None
            self.tray_available = False
            if show_errors:
                messagebox.showerror(APP_NAME, f"Could not start the system tray icon:\n{exc}")
            return False

        self.tray_available = True
        return True

    @staticmethod
    def _linux_x11_tray_manager_available() -> tuple[bool, str]:
        """Return whether the current X11 screen owns the system-tray selection."""
        if not os.environ.get("DISPLAY"):
            return False, "No DISPLAY environment variable is available."
        try:
            from Xlib import X, display
        except ImportError:
            return False, "python-xlib is unavailable, so the X11 tray could not be checked."

        connection = None
        try:
            connection = display.Display()
            screen_number = connection.get_default_screen()
            selection_name = f"_NET_SYSTEM_TRAY_S{screen_number}"
            selection_atom = connection.intern_atom(selection_name, only_if_exists=True)
            if selection_atom == X.NONE:
                return False, f"No {selection_name} selection exists."
            owner = connection.get_selection_owner(selection_atom)
            if owner == X.NONE:
                return False, f"No desktop process owns {selection_name}."
            return True, "An X11 system-tray manager is available."
        except Exception as exc:
            return False, f"The X11 tray manager check failed: {exc}"
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    def _disable_unavailable_tray_settings(self) -> None:
        self.automation["tray_enabled"] = False
        self.automation["start_minimized"] = False
        self.automation["close_to_tray"] = False
        self._save_settings(notify=False)

    def _stop_tray_icon(self) -> None:
        icon = self.tray_icon
        self.tray_icon = None
        self.tray_available = False
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass

    def _hide_to_tray(self) -> None:
        if not self._start_tray_icon(show_errors=True):
            return
        self.withdraw()

    def _show_from_tray(self) -> None:
        self.deiconify()
        maximize_window(self)
        self.lift()
        self.focus_force()

    def _handle_window_close(self) -> bool:
        if (
            not self._exiting_application
            and self.automation.get("tray_enabled", False)
            and self.automation.get("close_to_tray", False)
        ):
            self._hide_to_tray()
            return True
        return False

    def _exit_application(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            if not messagebox.askyesno(APP_NAME, "A backup is running. Cancel it and exit?"):
                return
            self._cancel_backup()
        self._exiting_application = True
        self._save_settings(notify=False)
        self._stop_tray_icon()
        self.destroy()
