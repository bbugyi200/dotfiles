"""Marking mixin for the ace TUI app."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ...changespec import ChangeSpec

# Type alias for tab names
TabName = Literal["changespecs", "agents", "axe"]


class MarkingMixin:
    """Mixin providing marking actions for ChangeSpecs."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    current_idx: int
    current_tab: TabName
    marked_indices: set[int]

    def action_toggle_mark(self) -> None:
        """Toggle mark on the current ChangeSpec."""
        if self.current_tab != "changespecs":
            return

        if not self.changespecs:
            self.notify("No ChangeSpecs to mark", severity="warning")  # type: ignore[attr-defined]
            return

        idx = self.current_idx
        was_marked = idx in self.marked_indices

        if was_marked:
            self.marked_indices.discard(idx)
        else:
            self.marked_indices.add(idx)

        # Force reactive update by reassigning
        self.marked_indices = set(self.marked_indices)  # type: ignore[assignment]

        self._refresh_display()  # type: ignore[attr-defined]

        # Auto-navigate to next spec (with wraparound)
        if len(self.changespecs) > 1:
            self.current_idx = (self.current_idx + 1) % len(self.changespecs)

    def action_clear_marks(self) -> None:
        """Clear all marks."""
        if self.current_tab != "changespecs":
            return

        if not self.marked_indices:
            self.notify("No marks to clear", severity="warning")  # type: ignore[attr-defined]
            return

        count = len(self.marked_indices)
        self.marked_indices = set()  # type: ignore[assignment]
        self._refresh_display()  # type: ignore[attr-defined]
        self.notify(f"Cleared {count} mark(s)")  # type: ignore[attr-defined]
