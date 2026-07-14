#!/usr/bin/env python3
# Copyright (C) 2026 Jacob Stallings
# SPDX-License-Identifier: GPL-3.0-only
"""Launch The Great Escape backup manager."""

from great_escape import BackupApp


def main() -> None:
    app = BackupApp()
    app.mainloop()


if __name__ == "__main__":
    main()
