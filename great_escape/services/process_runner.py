from __future__ import annotations

import os
import shlex
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

from ..models import CancelledError
from ..platform_utils import popen_platform_options, terminate_process_tree


class ProcessRunner:
    """Run cancellable child processes without depending on the GUI class MRO."""

    def __init__(
        self,
        cancel_event: threading.Event,
        process_lock: threading.Lock,
        set_current_process: Callable[[subprocess.Popen | None], None],
        log: Callable[[Path, str], None],
    ) -> None:
        self._cancel_event = cancel_event
        self._process_lock = process_lock
        self._set_current_process = set_current_process
        self._log = log

    def check_cancelled(self, process: subprocess.Popen | None = None) -> None:
        if not self._cancel_event.is_set():
            return
        if process is not None and process.poll() is None:
            terminate_process_tree(process)
        raise CancelledError()

    def run(
        self,
        command: list[str | os.PathLike[str]],
        log_file: Path,
        *,
        success_codes: set[int] | None = None,
        log_output: bool = True,
    ) -> None:
        success_codes = success_codes or {0}
        self.check_cancelled()
        normalized = [os.fspath(argument) for argument in command]
        process = subprocess.Popen(
            normalized,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            **popen_platform_options(),
        )
        self._register(process)
        try:
            assert process.stdout is not None
            for line in process.stdout:
                self.check_cancelled(process)
                clean = line.rstrip()
                if clean and log_output:
                    self._log(log_file, clean)
            return_code = process.wait()
            self.check_cancelled()
            if return_code not in success_codes:
                raise RuntimeError(
                    f"Command failed with exit code {return_code}: {shlex.join(normalized)}"
                )
        finally:
            self._clear(process)

    def run_to_file(
        self,
        command: list[str | os.PathLike[str]],
        output_path: Path,
        *,
        error_label: str,
    ) -> None:
        self.check_cancelled()
        normalized = [os.fspath(argument) for argument in command]
        with output_path.open("wb") as output_handle:
            process = subprocess.Popen(
                normalized,
                stdout=output_handle,
                stderr=subprocess.PIPE,
                **popen_platform_options(),
            )
            self._register(process)
            try:
                _stdout, stderr = process.communicate()
                self.check_cancelled(process)
                if process.returncode != 0:
                    detail = stderr.decode(errors="replace").strip() if stderr else "unknown error"
                    raise RuntimeError(f"{error_label}: {detail}")
            finally:
                self._clear(process)

    def terminate_active(self, process: subprocess.Popen | None) -> None:
        if process is not None and process.poll() is None:
            terminate_process_tree(process)

    def _register(self, process: subprocess.Popen) -> None:
        with self._process_lock:
            self._set_current_process(process)

    def _clear(self, process: subprocess.Popen) -> None:
        with self._process_lock:
            self._set_current_process(None)
