from __future__ import annotations

import os
import platform
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from tkinter import Tk


def maximize_window(window: Tk) -> None:
    """Maximize a Tk window using the best method for the current platform."""
    window.update_idletasks()
    system = platform.system()

    try:
        if system == "Windows":
            window.state("zoomed")
        elif system == "Darwin":
            window.attributes("-zoomed", True)
        else:
            window.attributes("-zoomed", True)
    except Exception:
        width = window.winfo_screenwidth()
        height = window.winfo_screenheight()
        window.geometry(f"{width}x{height}+0+0")


def open_path(path: Path) -> None:
    """Open a file or folder with the operating system's default handler."""
    path = path.expanduser().resolve()
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", os.fspath(path)])
    else:
        subprocess.Popen(["xdg-open", os.fspath(path)])


def launch_rclone_config() -> bool:
    """Launch rclone config in a terminal. Return False if no terminal is available."""
    if shutil.which("rclone") is None:
        return False

    if sys.platform.startswith("win"):
        subprocess.Popen(["cmd.exe", "/k", "rclone", "config"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        return True

    if sys.platform == "darwin":
        script = 'tell application "Terminal" to do script "rclone config"'
        subprocess.Popen(["osascript", "-e", script])
        return True

    terminal_commands = (
        ["x-terminal-emulator", "-e", "rclone", "config"],
        ["gnome-terminal", "--", "rclone", "config"],
        ["konsole", "-e", "rclone", "config"],
        ["xfce4-terminal", "-e", "rclone config"],
        ["lxterminal", "-e", "rclone config"],
    )
    for command in terminal_commands:
        if shutil.which(command[0]):
            subprocess.Popen(command)
            return True
    return False


def popen_platform_options() -> dict[str, object]:
    """Return subprocess options that allow child-process cancellation."""
    if sys.platform.startswith("win"):
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    """Stop a subprocess group on Windows, macOS, or Linux."""
    if process.poll() is not None:
        return

    try:
        if sys.platform.startswith("win"):
            process.send_signal(signal.CTRL_BREAK_EVENT)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        else:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        if process.poll() is None:
            process.kill()
