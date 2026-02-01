"""Marking mixin for the ace TUI app."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from ...status import get_available_statuses
from ..modals import StatusModal

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

    def action_bulk_change_status(self) -> None:
        """Change status for all marked ChangeSpecs."""
        if self.current_tab != "changespecs":
            return

        if not self.marked_indices:
            self.notify("No ChangeSpecs marked", severity="warning")  # type: ignore[attr-defined]
            return

        # Get marked changespecs (sorted by index for consistent ordering)
        marked_specs = [self.changespecs[i] for i in sorted(self.marked_indices)]

        # Find common available statuses (intersection)
        common_statuses: set[str] | None = None
        for spec in marked_specs:
            available = set(get_available_statuses(spec.status))
            if common_statuses is None:
                common_statuses = available
            else:
                common_statuses &= available

        if not common_statuses:
            self.notify("No common status transitions available", severity="warning")  # type: ignore[attr-defined]
            return

        def on_dismiss(new_status: str | None) -> None:
            if new_status:
                self._apply_bulk_status_change(marked_specs, new_status)

        # Use first marked spec for modal display
        self.push_screen(StatusModal(marked_specs[0].status), on_dismiss)  # type: ignore[attr-defined]

    def _apply_bulk_status_change(
        self, changespecs: list[ChangeSpec], new_status: str
    ) -> None:
        """Apply status change to multiple ChangeSpecs."""
        success_count = 0
        fail_count = 0

        for spec in changespecs:
            try:
                self._apply_status_change(spec, new_status)  # type: ignore[attr-defined]
                success_count += 1
            except Exception:
                fail_count += 1

        # Clear marks after bulk operation (indices will shift)
        self.marked_indices = set()  # type: ignore[assignment]

        # Reload and reposition
        self._reload_and_reposition()  # type: ignore[attr-defined]

        # Show summary notification
        if fail_count == 0:
            self.notify(f"Changed {success_count} ChangeSpec(s) to {new_status}")  # type: ignore[attr-defined]
        else:
            self.notify(  # type: ignore[attr-defined]
                f"Changed {success_count}, failed {fail_count}",
                severity="warning",
            )
