"""Main Textual App for the ace TUI."""

import os
import sys
from typing import Literal

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Footer, Header

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from ..changespec import ChangeSpec, find_all_changespecs
from ..query import evaluate_query, parse_query, to_canonical_string
from ..query.types import QueryExpr
from .actions import BaseActionsMixin, HintActionsMixin
from .widgets import (
    ChangeSpecDetail,
    ChangeSpecInfoPanel,
    ChangeSpecList,
    KeybindingFooter,
    SearchQueryPanel,
)


class AceApp(BaseActionsMixin, HintActionsMixin, App[None]):
    """TUI application for navigating ChangeSpecs."""

    TITLE = "gai ace"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("j", "next_changespec", "Next", show=False),
        Binding("k", "prev_changespec", "Previous", show=False),
        Binding("q", "quit", "Quit", show=False),
        Binding("s", "change_status", "Status", show=False),
        Binding("r", "run_workflow", "Run", show=False),
        Binding("R", "run_query", "Query", show=False, key_display="R"),
        Binding("m", "mail", "Mail", show=False),
        Binding("f", "findreviewers", "Find Reviewers", show=False),
        Binding("d", "show_diff", "Diff", show=False),
        Binding("v", "view_files", "View", show=False),
        Binding("h", "edit_hooks", "Hooks", show=False),
        Binding("a", "accept_proposal", "Accept", show=False),
        Binding("y", "refresh", "Refresh", show=False),
        Binding("slash", "edit_query", "Edit Query", show=False),
        Binding("ctrl+d", "scroll_detail_down", "Scroll Down", show=False),
        Binding("ctrl+u", "scroll_detail_up", "Scroll Up", show=False),
    ]

    # Reactive properties
    changespecs: reactive[list[ChangeSpec]] = reactive([], recompose=False)
    current_idx: reactive[int] = reactive(0, recompose=False)

    def __init__(
        self,
        query: str = '"(!: "',
        model_size_override: Literal["little", "big"] | None = None,
        refresh_interval: int = 10,
    ) -> None:
        """Initialize the ace TUI app.

        Args:
            query: Query string for filtering ChangeSpecs
            model_size_override: Override model size for all GeminiCommandWrapper instances
            refresh_interval: Auto-refresh interval in seconds (0 to disable)
        """
        super().__init__()
        self.theme = "flexoki"
        self.query_string = query
        self.parsed_query: QueryExpr = parse_query(query)
        self.refresh_interval = refresh_interval
        self._refresh_timer: Timer | None = None
        self._countdown_timer: Timer | None = None
        self._countdown_remaining: int = refresh_interval

        # Hint mode state
        self._hint_mode_active: bool = False
        self._hint_mode_hints_for: str | None = (
            None  # None/"all" or "hooks_latest_only"
        )
        self._hint_mappings: dict[int, str] = {}
        self._hook_hint_to_idx: dict[int, int] = {}
        self._hint_changespec_name: str = ""

        # Set global model size override in environment if specified
        if model_size_override:
            os.environ["GAI_MODEL_SIZE_OVERRIDE"] = model_size_override

    @property
    def canonical_query_string(self) -> str:
        """Get the canonical (normalized) form of the query string.

        Converts the parsed query back to a string with:
        - Explicit AND keywords between atoms
        - Uppercase AND/OR keywords
        - Quoted strings (not @-shorthand)
        """
        return to_canonical_string(self.parsed_query)

    def compose(self) -> ComposeResult:
        """Compose the app layout."""
        yield Header()
        with Horizontal(id="main-container"):
            with Vertical(id="list-container"):
                yield ChangeSpecInfoPanel(id="info-panel")
                yield ChangeSpecList(id="list-panel")
            with Vertical(id="detail-container"):
                yield SearchQueryPanel(id="search-query-panel")
                yield ChangeSpecDetail(id="detail-panel")
        yield KeybindingFooter(id="keybinding-footer")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the app on mount."""
        # Load initial changespecs
        self._load_changespecs()

        # Set up auto-refresh timer if enabled
        if self.refresh_interval > 0:
            self._countdown_remaining = self.refresh_interval
            self._countdown_timer = self.set_interval(
                1, self._on_countdown_tick, name="countdown"
            )
            self._refresh_timer = self.set_interval(
                self.refresh_interval, self._on_auto_refresh, name="auto-refresh"
            )

    def _load_changespecs(self) -> None:
        """Load and filter changespecs from disk."""
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
        return [
            cs
            for cs in changespecs
            if evaluate_query(self.parsed_query, cs, changespecs)
        ]

    def _reload_and_reposition(self, current_name: str | None = None) -> None:
        """Reload changespecs and try to stay on the same one."""
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

        self.changespecs = new_changespecs
        self.current_idx = new_idx
        self._refresh_display()

    def _on_auto_refresh(self) -> None:
        """Auto-refresh handler called by timer."""
        self._countdown_remaining = self.refresh_interval
        self._reload_and_reposition()

    def _on_countdown_tick(self) -> None:
        """Countdown tick handler called every second."""
        self._countdown_remaining -= 1
        if self._countdown_remaining < 0:
            self._countdown_remaining = self.refresh_interval
        self._update_info_panel()

    def _update_info_panel(self) -> None:
        """Update the info panel with current position and countdown."""
        info_panel = self.query_one("#info-panel", ChangeSpecInfoPanel)
        # Position is 1-based for display (current_idx is 0-based)
        position = self.current_idx + 1 if self.changespecs else 0
        info_panel.update_position(position, len(self.changespecs))
        info_panel.update_countdown(self._countdown_remaining, self.refresh_interval)

    def _refresh_display(self) -> None:
        """Refresh the display with current state."""
        list_widget = self.query_one("#list-panel", ChangeSpecList)
        detail_widget = self.query_one("#detail-panel", ChangeSpecDetail)
        search_panel = self.query_one("#search-query-panel", SearchQueryPanel)
        footer_widget = self.query_one("#keybinding-footer", KeybindingFooter)

        list_widget.update_list(self.changespecs, self.current_idx)
        search_panel.update_query(self.canonical_query_string)

        if self.changespecs:
            changespec = self.changespecs[self.current_idx]
            # Preserve hints if in hint mode
            if self._hint_mode_active:
                hint_mappings, hook_hint_to_idx = (
                    detail_widget.update_display_with_hints(
                        changespec,
                        self.canonical_query_string,
                        hints_for=self._hint_mode_hints_for,
                    )
                )
                self._hint_mappings = hint_mappings
                self._hook_hint_to_idx = hook_hint_to_idx
            else:
                detail_widget.update_display(changespec, self.canonical_query_string)
            footer_widget.update_bindings(
                changespec, self.current_idx, len(self.changespecs)
            )
        else:
            detail_widget.show_empty(self.canonical_query_string)
            footer_widget.show_empty()

        self._update_info_panel()

    def watch_current_idx(self, old_idx: int, new_idx: int) -> None:
        """React to current_idx changes."""
        if old_idx != new_idx:
            self._refresh_display()

    # --- Navigation Actions ---

    def action_next_changespec(self) -> None:
        """Navigate to the next ChangeSpec."""
        if self.current_idx < len(self.changespecs) - 1:
            self.current_idx += 1

    def action_prev_changespec(self) -> None:
        """Navigate to the previous ChangeSpec."""
        if self.current_idx > 0:
            self.current_idx -= 1

    def action_scroll_detail_down(self) -> None:
        """Scroll the detail panel down by half a page (vim Ctrl+D style)."""
        detail_widget = self.query_one("#detail-panel", ChangeSpecDetail)
        self.log.info(
            f"scroll_down: max_scroll_y={detail_widget.max_scroll_y}, scroll_y={detail_widget.scroll_y}, region_height={detail_widget.scrollable_content_region.height}"
        )
        height = detail_widget.scrollable_content_region.height
        detail_widget.scroll_relative(y=height // 2, animate=False, force=True)

    def action_scroll_detail_up(self) -> None:
        """Scroll the detail panel up by half a page (vim Ctrl+U style)."""
        detail_widget = self.query_one("#detail-panel", ChangeSpecDetail)
        self.log.info(
            f"scroll_up: max_scroll_y={detail_widget.max_scroll_y}, scroll_y={detail_widget.scroll_y}, region_height={detail_widget.scrollable_content_region.height}"
        )
        height = detail_widget.scrollable_content_region.height
        detail_widget.scroll_relative(y=-(height // 2), animate=False, force=True)

    # --- List Selection Handling ---

    def on_change_spec_list_selection_changed(
        self, event: ChangeSpecList.SelectionChanged
    ) -> None:
        """Handle selection change in the list widget."""
        if 0 <= event.index < len(self.changespecs):
            self.current_idx = event.index
