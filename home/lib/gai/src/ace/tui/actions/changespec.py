"""ChangeSpec management mixin for the ace TUI app."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ...changespec import ChangeSpec
    from ...query.types import QueryExpr
    from ...query_history import QueryHistoryStacks

# Type alias for tab names
TabName = Literal["changespecs", "agents", "axe"]


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
    hide_reverted: bool
    marked_indices: set[int]
    _hint_mode_active: bool
    _hint_mode_hints_for: str | None
    _hint_mappings: dict[int, str]
    _hook_hint_to_idx: dict[int, int]
    _hint_to_entry_id: dict[int, str]
    _query_history: QueryHistoryStacks
    _all_changespecs: list[ChangeSpec]
    _ancestor_keys: dict[str, str]
    _children_keys: dict[str, str]
    _sibling_keys: dict[str, str]
    _hidden_reverted_count: int

    def _load_changespecs(self) -> None:
        """Load and filter changespecs from disk."""
        from ...changespec import find_all_changespecs

        all_changespecs = find_all_changespecs()
        self._all_changespecs = all_changespecs  # Cache for ancestry lookup
        self.changespecs = self._filter_changespecs(all_changespecs)

        # Clear marks on reload (indices may shift)
        self.marked_indices = set()  # type: ignore[assignment]

        # Ensure current_idx is within bounds
        if self.changespecs:
            if self.current_idx >= len(self.changespecs):
                self.current_idx = len(self.changespecs) - 1
        else:
            self.current_idx = 0

        self._refresh_display()

    def _filter_changespecs(self, changespecs: list[ChangeSpec]) -> list[ChangeSpec]:
        """Filter changespecs using the parsed query and hide_reverted setting."""
        from ...changespec import get_base_status
        from ...query import evaluate_query, query_explicitly_targets_reverted

        # First apply the query filter
        result = [
            cs
            for cs in changespecs
            if evaluate_query(self.parsed_query, cs, changespecs)
        ]

        # Check if we should filter out reverted (only if hide_reverted is True
        # AND query doesn't explicitly target reverted)
        self._hidden_reverted_count = 0
        if self.hide_reverted and not query_explicitly_targets_reverted(
            self.parsed_query, changespecs
        ):
            filtered: list[ChangeSpec] = []
            for cs in result:
                if get_base_status(cs.status) == "Reverted":
                    self._hidden_reverted_count += 1
                else:
                    filtered.append(cs)
            result = filtered

        return result

    def _reload_and_reposition(self, current_name: str | None = None) -> None:
        """Reload changespecs and try to stay on the same one."""
        from ...changespec import find_all_changespecs

        if current_name is None and self.changespecs:
            current_name = self.changespecs[self.current_idx].name

        all_changespecs = find_all_changespecs()
        self._all_changespecs = all_changespecs  # Cache for ancestry lookup
        new_changespecs = self._filter_changespecs(all_changespecs)

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

    def _save_current_query(self) -> None:
        """Save the current query as the last used query."""
        from ...saved_queries import save_last_query

        save_last_query(self.canonical_query_string)  # type: ignore[attr-defined]

    def _load_saved_query(self, slot: str) -> None:
        """Load a saved query from a slot.

        Args:
            slot: The slot number ("0"-"9").
        """
        from ...query import parse_query, to_canonical_string
        from ...query_history import push_to_prev_stack, save_query_history
        from ...saved_queries import load_saved_queries

        queries = load_saved_queries()
        if slot not in queries:
            self.notify(f"No query saved in slot {slot}", severity="warning")  # type: ignore[attr-defined]
            return

        query = queries[slot]
        try:
            new_parsed = parse_query(query)
            new_canonical = to_canonical_string(new_parsed)

            # Only push to history if query actually changes
            current_canonical = self.canonical_query_string  # type: ignore[attr-defined]
            if new_canonical != current_canonical:
                push_to_prev_stack(current_canonical, self._query_history)
                save_query_history(self._query_history)

            self.parsed_query = new_parsed
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

    # --- Query History Navigation Actions ---

    def action_prev_query(self) -> None:
        """Navigate to previous query in history (^ key)."""
        from ...query import parse_query
        from ...query_history import navigate_prev, save_query_history

        if self.current_tab != "changespecs":
            return

        current_canonical = self.canonical_query_string  # type: ignore[attr-defined]
        prev_query = navigate_prev(current_canonical, self._query_history)
        if prev_query is None:
            self.notify("No previous query", severity="warning")  # type: ignore[attr-defined]
            return

        try:
            self.parsed_query = parse_query(prev_query)
            self.query_string = prev_query
            self._load_changespecs()
            self._save_current_query()
            save_query_history(self._query_history)
        except Exception as e:
            self.notify(f"Error loading query: {e}", severity="error")  # type: ignore[attr-defined]

    def action_next_query(self) -> None:
        """Navigate to next query in history (_ key)."""
        from ...query import parse_query
        from ...query_history import navigate_next, save_query_history

        if self.current_tab != "changespecs":
            return

        current_canonical = self.canonical_query_string  # type: ignore[attr-defined]
        next_query = navigate_next(current_canonical, self._query_history)
        if next_query is None:
            self.notify("No next query", severity="warning")  # type: ignore[attr-defined]
            return

        try:
            self.parsed_query = parse_query(next_query)
            self.query_string = next_query
            self._load_changespecs()
            self._save_current_query()
            save_query_history(self._query_history)
        except Exception as e:
            self.notify(f"Error loading query: {e}", severity="error")  # type: ignore[attr-defined]

    def _refresh_display(self) -> None:
        """Refresh the display with current state."""
        from ...query import query_explicitly_targets_reverted
        from ..widgets import (
            AncestorsChildrenPanel,
            ChangeSpecDetail,
            ChangeSpecList,
            KeybindingFooter,
            SearchQueryPanel,
        )

        list_widget = self.query_one("#list-panel", ChangeSpecList)  # type: ignore[attr-defined]
        detail_widget = self.query_one("#detail-panel", ChangeSpecDetail)  # type: ignore[attr-defined]
        search_panel = self.query_one("#search-query-panel", SearchQueryPanel)  # type: ignore[attr-defined]
        footer_widget = self.query_one("#keybinding-footer", KeybindingFooter)  # type: ignore[attr-defined]
        ancestors_panel = self.query_one(  # type: ignore[attr-defined]
            "#ancestors-children-panel", AncestorsChildrenPanel
        )

        list_widget.update_list(self.changespecs, self.current_idx, self.marked_indices)
        search_panel.update_query(self.canonical_query_string)  # type: ignore[attr-defined]

        # Calculate effective hide_reverted (disabled if query targets reverted)
        effective_hide_reverted = (
            self.hide_reverted
            and not query_explicitly_targets_reverted(
                self.parsed_query, self._all_changespecs
            )
        )

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
            # Update ancestors/children/siblings panel with hide_reverted
            self._ancestor_keys, self._children_keys, self._sibling_keys = (
                ancestors_panel.update_relationships(
                    changespec,
                    self._all_changespecs,
                    hide_reverted=effective_hide_reverted,
                )
            )
            # Calculate total hidden count for footer
            total_hidden = (
                self._hidden_reverted_count
                + ancestors_panel.get_hidden_reverted_count()
            )
            footer_widget.update_bindings(
                changespec,
                hidden_reverted_count=total_hidden,
                hide_reverted=self.hide_reverted,
            )
        else:
            detail_widget.show_empty(self.canonical_query_string)  # type: ignore[attr-defined]
            footer_widget.show_empty()
            ancestors_panel.clear()
            self._ancestor_keys = {}
            self._children_keys = {}
            self._sibling_keys = {}

        self._update_info_panel()

    def _update_info_panel(self) -> None:
        """Update the info panel with current position and countdown."""
        from ..widgets import ChangeSpecInfoPanel

        info_panel = self.query_one("#info-panel", ChangeSpecInfoPanel)  # type: ignore[attr-defined]
        # Position is 1-based for display (current_idx is 0-based)
        position = self.current_idx + 1 if self.changespecs else 0
        info_panel.update_position(
            position, len(self.changespecs), len(self.marked_indices)
        )
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

    def action_toggle_hide_reverted(self) -> None:
        """Toggle visibility of reverted CLs or non-run agents."""
        if self.current_tab == "agents":
            self._toggle_hide_non_run_agents()  # type: ignore[attr-defined]
            return
        if self.current_tab != "changespecs":
            return
        self.hide_reverted = not self.hide_reverted
        self._reload_and_reposition()
