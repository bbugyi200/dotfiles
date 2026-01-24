"""Advanced navigation mixin for fold mode, help modal, and history navigation."""

from __future__ import annotations

from ...changespec_history import ChangeSpecHistoryEntry
from ._types import NavigationMixinBase


class AdvancedNavigationMixin(NavigationMixinBase):
    """Mixin providing fold mode, help modal, and history navigation."""

    # --- Fold Mode Actions ---

    def action_start_fold_mode(self) -> None:
        """Enter fold mode - waiting for sub-key (c/h/z)."""
        self._fold_mode_active = True

    def _handle_fold_key(self, key: str) -> bool:
        """Handle fold sub-key. Returns True if handled."""
        if not self._fold_mode_active:
            return False

        self._fold_mode_active = False

        if key == "c":
            self.commits_collapsed = not self.commits_collapsed
            self._refresh_display()  # type: ignore[attr-defined]
            return True
        elif key == "h":
            self.hooks_collapsed = not self.hooks_collapsed
            self._refresh_display()  # type: ignore[attr-defined]
            return True
        elif key == "m":
            self.mentors_collapsed = not self.mentors_collapsed
            self._refresh_display()  # type: ignore[attr-defined]
            return True
        elif key == "z":
            # Toggle all - if different states, collapse all
            if self.commits_collapsed == self.hooks_collapsed == self.mentors_collapsed:
                new_state = not self.commits_collapsed
            else:
                new_state = True  # Default to collapsed if mismatched
            self.commits_collapsed = new_state
            self.hooks_collapsed = new_state
            self.mentors_collapsed = new_state
            self._refresh_display()  # type: ignore[attr-defined]
            return True
        else:
            # Invalid key - cancel fold mode
            return True

    # --- Help Action ---

    def action_show_help(self) -> None:
        """Show the help modal with all keybindings."""
        from ...modals import HelpModal

        self.push_screen(  # type: ignore[attr-defined]
            HelpModal(
                current_tab=self.current_tab,
                active_query=self.canonical_query_string,  # type: ignore[attr-defined]
            )
        )

    # --- ChangeSpec History Navigation (ctrl+o / ctrl+k) ---

    def _get_current_changespec_history_entry(
        self,
    ) -> ChangeSpecHistoryEntry | None:
        """Create a history entry for the current ChangeSpec.

        Returns:
            ChangeSpecHistoryEntry for the current CL, or None if no CLs.
        """
        from ...changespec_history import ChangeSpecHistoryEntry

        if not self.changespecs or self.current_idx >= len(self.changespecs):
            return None

        cs = self.changespecs[self.current_idx]
        return ChangeSpecHistoryEntry(
            name=cs.name,
            file_path=cs.file_path,
            query=self.canonical_query_string,  # type: ignore[attr-defined]
        )

    def _push_changespec_to_history(self) -> None:
        """Push current ChangeSpec to history before navigating away.

        Called by _navigate_to_changespec() and click handlers.
        """
        from ...changespec_history import push_to_prev_stack

        entry = self._get_current_changespec_history_entry()
        if entry is not None:
            push_to_prev_stack(entry, self._changespec_history)

    def _find_changespec_by_name_and_path(
        self, name: str, file_path: str
    ) -> int | None:
        """Find a ChangeSpec by name and file_path in current filtered list.

        Args:
            name: The ChangeSpec name.
            file_path: The path to the .gp file.

        Returns:
            The index in self.changespecs, or None if not found.
        """
        for idx, cs in enumerate(self.changespecs):
            if cs.name == name and cs.file_path == file_path:
                return idx
        return None

    def _navigate_to_history_entry(self, entry: ChangeSpecHistoryEntry) -> bool:
        """Navigate to a ChangeSpec from a history entry.

        This may change the query and reload changespecs if needed.

        Args:
            entry: The history entry to navigate to.

        Returns:
            True if navigation succeeded, False otherwise.
        """
        from ....query import parse_query

        # First check if target is in current list
        target_idx = self._find_changespec_by_name_and_path(entry.name, entry.file_path)

        if target_idx is not None:
            # Target is visible - just jump to it
            self.current_idx = target_idx
            return True

        # Target not in current list - need to restore the original query
        try:
            new_parsed = parse_query(entry.query)
            self.parsed_query = new_parsed
            self.query_string = entry.query
            self._load_changespecs()  # type: ignore[attr-defined]
            self._save_current_query()  # type: ignore[attr-defined]

            # Find and select the target
            target_idx = self._find_changespec_by_name_and_path(
                entry.name, entry.file_path
            )
            if target_idx is not None:
                self.current_idx = target_idx
                return True
            else:
                # ChangeSpec no longer exists in this query result
                self.notify(  # type: ignore[attr-defined]
                    f"ChangeSpec '{entry.name}' no longer exists in query results",
                    severity="warning",
                )
                return False

        except Exception as e:
            self.notify(f"History navigation error: {e}", severity="error")  # type: ignore[attr-defined]
            return False

    def action_prev_changespec_history(self) -> None:
        """Navigate to previous ChangeSpec in history (ctrl+o)."""
        from ...changespec_history import navigate_prev

        if self.current_tab != "changespecs":
            return

        current_entry = self._get_current_changespec_history_entry()
        if current_entry is None:
            return

        prev_entry = navigate_prev(current_entry, self._changespec_history)
        if prev_entry is None:
            self.notify("No previous CL in history", severity="information")  # type: ignore[attr-defined]
            return

        self._navigate_to_history_entry(prev_entry)

    def action_next_changespec_history(self) -> None:
        """Navigate to next ChangeSpec in history (ctrl+k)."""
        from ...changespec_history import navigate_next

        if self.current_tab != "changespecs":
            return

        current_entry = self._get_current_changespec_history_entry()
        if current_entry is None:
            return

        next_entry = navigate_next(current_entry, self._changespec_history)
        if next_entry is None:
            self.notify("No next CL in history", severity="information")  # type: ignore[attr-defined]
            return

        self._navigate_to_history_entry(next_entry)
