"""ChangeSpec management mixin for the ace TUI app."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ...changespec import ChangeSpec
    from ...query.types import QueryExpr

# Type alias for tab names
TabName = Literal["changespecs", "agents"]


class ChangeSpecMixin:
    """Mixin providing ChangeSpec loading, filtering, and display methods."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    current_idx: int
    current_tab: TabName
    query_string: str
    parsed_query: QueryExpr
    hooks_collapsed: bool
    commits_collapsed: bool
    mentors_collapsed: bool
    _hint_mode_active: bool
    _hint_mode_hints_for: str | None
    _hint_mappings: dict[int, str]
    _hook_hint_to_idx: dict[int, int]
    _hint_to_entry_id: dict[int, str]

    def _load_changespecs(self) -> None:
        """Load and filter changespecs from disk."""
        from ...changespec import find_all_changespecs

        all_changespecs = find_all_changespecs()
        self.changespecs = self._filter_changespecs(all_changespecs)

        # Ensure current_idx is within bounds
        if self.changespecs:
            if self.current_idx >= len(self.changespecs):
                self.current_idx = len(self.changespecs) - 1
        else:
            self.current_idx = 0

        self._refresh_display()

    def _filter_changespecs(self, changespecs: list[ChangeSpec]) -> list[ChangeSpec]:
        """Filter changespecs using the parsed query."""
        from ...query import evaluate_query

        return [
            cs
            for cs in changespecs
            if evaluate_query(self.parsed_query, cs, changespecs)
        ]

    def _reload_and_reposition(self, current_name: str | None = None) -> None:
        """Reload changespecs and try to stay on the same one."""
        from ...changespec import find_all_changespecs

        if current_name is None and self.changespecs:
            current_name = self.changespecs[self.current_idx].name

        new_changespecs = find_all_changespecs()
        new_changespecs = self._filter_changespecs(new_changespecs)

        # Try to find the same changespec by name
        new_idx = 0
        if current_name:
            for idx, cs in enumerate(new_changespecs):
                if cs.name == current_name:
                    new_idx = idx
                    break

        self.changespecs = new_changespecs  # type: ignore[assignment]
        self.current_idx = new_idx
        self._refresh_display()

    def _refresh_saved_queries_panel(self) -> None:
        """Refresh the saved queries panel."""
        from ..widgets import SavedQueriesPanel

        panel = self.query_one("#saved-queries-panel", SavedQueriesPanel)  # type: ignore[attr-defined]
        panel.refresh_queries(self.canonical_query_string)  # type: ignore[attr-defined]

    def _save_current_query(self) -> None:
        """Save the current query as the last used query."""
        from ...saved_queries import save_last_query

        save_last_query(self.canonical_query_string)  # type: ignore[attr-defined]

    def _load_saved_query(self, slot: str) -> None:
        """Load a saved query from a slot.

        Args:
            slot: The slot number ("0"-"9").
        """
        from ...query import parse_query
        from ...saved_queries import load_saved_queries

        queries = load_saved_queries()
        if slot not in queries:
            self.notify(f"No query saved in slot {slot}", severity="warning")  # type: ignore[attr-defined]
            return

        query = queries[slot]
        try:
            self.parsed_query = parse_query(query)
            self.query_string = query
            self._load_changespecs()
            self._save_current_query()
        except Exception as e:
            self.notify(f"Error loading query: {e}", severity="error")  # type: ignore[attr-defined]

    # --- Saved Query Actions ---

    def action_load_saved_query_1(self) -> None:
        """Load saved query from slot 1."""
        self._load_saved_query("1")

    def action_load_saved_query_2(self) -> None:
        """Load saved query from slot 2."""
        self._load_saved_query("2")

    def action_load_saved_query_3(self) -> None:
        """Load saved query from slot 3."""
        self._load_saved_query("3")

    def action_load_saved_query_4(self) -> None:
        """Load saved query from slot 4."""
        self._load_saved_query("4")

    def action_load_saved_query_5(self) -> None:
        """Load saved query from slot 5."""
        self._load_saved_query("5")

    def action_load_saved_query_6(self) -> None:
        """Load saved query from slot 6."""
        self._load_saved_query("6")

    def action_load_saved_query_7(self) -> None:
        """Load saved query from slot 7."""
        self._load_saved_query("7")

    def action_load_saved_query_8(self) -> None:
        """Load saved query from slot 8."""
        self._load_saved_query("8")

    def action_load_saved_query_9(self) -> None:
        """Load saved query from slot 9."""
        self._load_saved_query("9")

    def action_load_saved_query_0(self) -> None:
        """Load saved query from slot 0."""
        self._load_saved_query("0")

    def _refresh_display(self) -> None:
        """Refresh the display with current state."""
        from ..widgets import (
            ChangeSpecDetail,
            ChangeSpecList,
            KeybindingFooter,
            SearchQueryPanel,
        )

        list_widget = self.query_one("#list-panel", ChangeSpecList)  # type: ignore[attr-defined]
        detail_widget = self.query_one("#detail-panel", ChangeSpecDetail)  # type: ignore[attr-defined]
        search_panel = self.query_one("#search-query-panel", SearchQueryPanel)  # type: ignore[attr-defined]
        footer_widget = self.query_one("#keybinding-footer", KeybindingFooter)  # type: ignore[attr-defined]

        list_widget.update_list(self.changespecs, self.current_idx)
        search_panel.update_query(self.canonical_query_string)  # type: ignore[attr-defined]
        self._refresh_saved_queries_panel()

        if self.changespecs:
            changespec = self.changespecs[self.current_idx]
            # Preserve hints if in hint mode
            if self._hint_mode_active:
                # Respect collapsed states: show hints only on visible lines
                hint_mappings, hook_hint_to_idx, hint_to_entry_id = (
                    detail_widget.update_display_with_hints(
                        changespec,
                        self.canonical_query_string,  # type: ignore[attr-defined]
                        hints_for=self._hint_mode_hints_for,
                        hooks_collapsed=self.hooks_collapsed,
                        commits_collapsed=self.commits_collapsed,
                        mentors_collapsed=self.mentors_collapsed,
                    )
                )
                self._hint_mappings = hint_mappings
                self._hook_hint_to_idx = hook_hint_to_idx
                self._hint_to_entry_id = hint_to_entry_id
            else:
                detail_widget.update_display(
                    changespec,
                    self.canonical_query_string,  # type: ignore[attr-defined]
                    hooks_collapsed=self.hooks_collapsed,
                    commits_collapsed=self.commits_collapsed,
                    mentors_collapsed=self.mentors_collapsed,
                )
            footer_widget.update_bindings(
                changespec,
                self.current_idx,
                len(self.changespecs),
            )
        else:
            detail_widget.show_empty(self.canonical_query_string)  # type: ignore[attr-defined]
            footer_widget.show_empty()

        self._update_info_panel()

    def _update_info_panel(self) -> None:
        """Update the info panel with current position and countdown."""
        from ..widgets import ChangeSpecInfoPanel

        info_panel = self.query_one("#info-panel", ChangeSpecInfoPanel)  # type: ignore[attr-defined]
        # Position is 1-based for display (current_idx is 0-based)
        position = self.current_idx + 1 if self.changespecs else 0
        info_panel.update_position(position, len(self.changespecs))
        info_panel.update_countdown(self._countdown_remaining, self.refresh_interval)  # type: ignore[attr-defined]

    def action_edit_spec(self) -> None:
        """Edit the current ChangeSpec in $EDITOR."""
        if not self.changespecs:
            return
        changespec = self.changespecs[self.current_idx]
        self._open_spec_in_editor(changespec)

    def _open_spec_in_editor(self, changespec: ChangeSpec) -> None:
        """Open ChangeSpec in editor with nvim enhancements."""
        import subprocess

        editor = os.environ.get("EDITOR", "vi")
        file_path = os.path.expanduser(changespec.file_path)
        args = [editor]
        if "/nvim" in editor:
            args.extend(
                [
                    "-c",
                    f"/NAME: \\zs{changespec.name}$",
                    "-c",
                    "normal zz",
                    "-c",
                    "nohlsearch",
                ]
            )
        args.append(file_path)
        with self.suspend():  # type: ignore[attr-defined]
            subprocess.run(args, check=False)
