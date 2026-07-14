from __future__ import annotations

import tkinter as tk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    AppTk = TkinterDnD.Tk
    DRAG_AND_DROP_AVAILABLE = True
except ImportError:
    DND_FILES = "DND_Files"
    AppTk = tk.Tk
    DRAG_AND_DROP_AVAILABLE = False


__all__ = ["AppTk", "DND_FILES", "DRAG_AND_DROP_AVAILABLE"]
