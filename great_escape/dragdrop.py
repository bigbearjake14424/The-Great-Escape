from __future__ import annotations

from pathlib import Path

from .models import LocalDestination, SourceItem
from .windowing import DND_FILES, DRAG_AND_DROP_AVAILABLE


class DragDropMixin:
    """Enable file and folder drops when tkinterdnd2 is installed."""

    def _configure_drag_and_drop(self) -> None:
        self.drag_and_drop_available = DRAG_AND_DROP_AVAILABLE
        if not DRAG_AND_DROP_AVAILABLE:
            self._log(
                "Drag-and-drop is unavailable. Install tkinterdnd2 to enable it: "
                "python -m pip install tkinterdnd2"
            )
            return

        try:
            self.source_tree.drop_target_register(DND_FILES)
            self.source_tree.dnd_bind("<<Drop>>", self._drop_sources)
            self.local_tree.drop_target_register(DND_FILES)
            self.local_tree.dnd_bind("<<Drop>>", self._drop_local_destinations)
            self._log("Drag-and-drop is enabled for sources and local destinations.")
        except Exception as exc:
            self.drag_and_drop_available = False
            self._log(f"Drag-and-drop could not be initialized: {exc}")

    def _drop_sources(self, event: object) -> str:
        paths = self._parse_drop_paths(getattr(event, "data", ""))
        existing = {str(Path(item.path).expanduser().resolve()) for item in self.sources}
        added = 0
        for path in paths:
            candidate = Path(path).expanduser()
            if not candidate.exists():
                continue
            normalized = str(candidate.resolve())
            if normalized not in existing:
                self.sources.append(SourceItem(normalized))
                existing.add(normalized)
                added += 1
        self._refresh_source_tree()
        if added:
            self._save_settings(notify=False)
            self._log(f"Added {added} source item(s) by drag-and-drop.")
        return "copy"

    def _drop_local_destinations(self, event: object) -> str:
        paths = self._parse_drop_paths(getattr(event, "data", ""))
        existing = {str(Path(item.path).expanduser().resolve()) for item in self.local_destinations}
        added = 0
        ignored = 0
        for path in paths:
            candidate = Path(path).expanduser()
            if not candidate.is_dir():
                ignored += 1
                continue
            normalized = str(candidate.resolve())
            if normalized not in existing:
                self.local_destinations.append(LocalDestination(normalized))
                existing.add(normalized)
                added += 1
        self._refresh_local_tree()
        if added:
            self._save_settings(notify=False)
            self._log(f"Added {added} local destination(s) by drag-and-drop.")
        if ignored:
            self._log(f"Ignored {ignored} dropped item(s) because destinations must be folders.")
        return "copy"

    def _parse_drop_paths(self, data: str) -> list[str]:
        if not data:
            return []
        try:
            return [str(value) for value in self.tk.splitlist(data)]
        except Exception:
            return [data.strip("{}")]
