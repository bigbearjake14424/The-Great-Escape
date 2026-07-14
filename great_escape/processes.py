from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

from .models import CancelledError
from .platform_utils import popen_platform_options, terminate_process_tree


class ProcessMixin:
    """Cross-platform subprocess execution and cancellation."""

    def _run_process(
        self,
        command: list[str | os.PathLike[str]],
        log_file: Path,
        *,
        success_codes: set[int] | None = None,
        log_output: bool = True,
    ) -> None:
        success_codes = success_codes or {0}
        self._check_cancelled()
        normalized_command = [os.fspath(argument) for argument in command]

        process = subprocess.Popen(
            normalized_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            **popen_platform_options(),
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
                raise RuntimeError(
                    f"Command failed with exit code {return_code}: "
                    f"{shlex.join(normalized_command)}"
                )
        finally:
            with self.process_lock:
                if self.current_process is process:
                    self.current_process = None

    def _check_cancelled(self, process: subprocess.Popen[str] | None = None) -> None:
        if not self.cancel_event.is_set():
            return
        if process and process.poll() is None:
            terminate_process_tree(process)
        raise CancelledError()

    @staticmethod
    def _terminate_process_group(process: subprocess.Popen[str]) -> None:
        terminate_process_tree(process)
