import shutil
import subprocess
from tkinter import messagebox

from .config import APP_NAME, APP_VERSION, DEFAULT_LOG_DIR
from .platform_utils import launch_rclone_config, open_path


class ToolsMixin:
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

    @staticmethod
    def _open_rclone_config() -> None:
        if shutil.which("rclone") is None:
            messagebox.showerror(APP_NAME, "rclone is not installed or is not in PATH.")
            return
        if not launch_rclone_config():
            messagebox.showinfo(APP_NAME, "Open a terminal and run:\n\nrclone config")

    @staticmethod
    def _show_rclone_remotes() -> None:
        if shutil.which("rclone") is None:
            messagebox.showerror(APP_NAME, "rclone is not installed or is not in PATH.")
            return
        try:
            result = subprocess.run(
                ["rclone", "listremotes"],
                text=True,
                capture_output=True,
                check=False,
                timeout=15,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "rclone returned an error")
            remotes = result.stdout.strip() or "No rclone remotes are configured."
            messagebox.showinfo(APP_NAME, remotes)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not list rclone remotes:\n{exc}")

    @staticmethod
    def _open_log_folder() -> None:
        DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            open_path(DEFAULT_LOG_DIR)
        except (OSError, subprocess.SubprocessError) as exc:
            messagebox.showinfo(APP_NAME, f"Log folder:\n{DEFAULT_LOG_DIR}\n\nCould not open it automatically: {exc}")

    @staticmethod
    def _show_about() -> None:
        messagebox.showinfo(
            APP_NAME,
            f"{APP_NAME} {APP_VERSION}\n\n"
            "Creates a .tar.xz archive using GNU tar and multi-threaded xz, then distributes the completed archive "
            "to enabled local folders and rclone destinations. Appearance and backup settings are stored as JSON "
            "in the user's home directory.",
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
