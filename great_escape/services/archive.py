from __future__ import annotations

import os
import shlex
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .process_runner import ProcessRunner


class ArchiveService:
    def __init__(
        self,
        process_runner: ProcessRunner,
        log: Callable[[Path, str], None],
        progress: Callable[[int, str], None],
        human_size: Callable[[int], str],
    ) -> None:
        self.process_runner = process_runner
        self.log = log
        self.progress = progress
        self.human_size = human_size

    def create(self, sources: list[Path], archive_path: Path, config: dict[str, Any], log_file: Path) -> None:
        level = "-9e" if config["compression"].startswith("Maximum") else "-9" if config["compression"].startswith("High") else "-6"
        threads = max(1, min(os.cpu_count() or 1, int(config["threads"])))
        compressor = f"xz {level} -T{threads}"
        command = ["tar", "--create", "--file", str(archive_path), f"--use-compress-program={compressor}", "--warning=no-file-changed"]
        for source in sources:
            command.extend(["-C", str(source.parent), source.name])
        self.log(log_file, "Creating compressed tarball.")
        self.log(log_file, "Command: " + shlex.join(command))
        self.progress(10, "Compressing files with xz")
        self.process_runner.run(command, log_file, success_codes={0, 1})
        if not archive_path.exists() or archive_path.stat().st_size == 0:
            raise RuntimeError("tar/xz did not create a usable archive.")
        self.log(log_file, f"Archive created: {archive_path} ({self.human_size(archive_path.stat().st_size)})")

    def verify(self, archive_path: Path, log_file: Path) -> None:
        self.process_runner.check_cancelled()
        self.log(log_file, "Verifying archive integrity with tar -tJf.")
        self.progress(58, "Verifying archive integrity")
        self.process_runner.run(["tar", "-tJf", str(archive_path)], log_file, log_output=False)
        self.log(log_file, "Archive verification passed.")
