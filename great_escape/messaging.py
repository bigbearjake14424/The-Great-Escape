import queue
from datetime import datetime
from pathlib import Path
from typing import Any
from tkinter import messagebox

from .config import APP_NAME


class MessagingMixin:
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
