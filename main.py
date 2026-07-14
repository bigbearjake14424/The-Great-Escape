#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Launch The Great Escape backup manager."""

from great_escape import BackupApp


def main() -> None:
    app = BackupApp()
    app.mainloop()


if __name__ == "__main__":
    main()
