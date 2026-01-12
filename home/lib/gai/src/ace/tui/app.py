"""Main Textual App for the ace TUI."""

import os
import sys
from typing import Literal

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Footer, Header

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from ..changespec import ChangeSpec
from ..query import parse_query, to_canonical_string
from ..query.types import QueryExpr
from .actions import (
    AgentsMixin,
    AgentWorkflowMixin,
    BaseActionsMixin,
    ChangeSpecMixin,
    EventHandlersMixin,
    HintActionsMixin,
    NavigationMixin,
)
from .models import Agent
from .widgets import (
    AgentDetail,
    AgentInfoPanel,
    AgentList,
    ChangeSpecDetail,
    ChangeSpecInfoPanel,
    ChangeSpecList,
    KeybindingFooter,
    SavedQueriesPanel,
    SearchQueryPanel,
    TabBar,
)

# Type alias for tab names
TabName = Literal["changespecs", "agents"]

# Width bounds for dynamic list panel sizing (in terminal cells)
# MIN must fit: "ChangeSpec: X/Y   (auto-refresh in Ns)" + padding/border
_MIN_LIST_WIDTH = 43
_MAX_LIST_WIDTH = 80


class AceApp(
    AgentWorkflowMixin,
    AgentsMixin,
    ChangeSpecMixin,
    EventHandlersMixin,
    NavigationMixin,
    BaseActionsMixin,
    HintActionsMixin,
    App[None],
):
    """TUI application for navigating ChangeSpecs."""

    TITLE = "gai ace"
    CSS_PATH = "styles.tcss"
    ENABLE_COMMAND_PALETTE = False

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
        Binding("w", "reword", "Reword", show=False),
        Binding("v", "view_files", "View", show=False),
        Binding("h", "edit_hooks", "Hooks", show=False),
        Binding("z", "start_fold_mode", "Fold", show=False),
        Binding("a", "accept_proposal", "Accept", show=False),
        Binding("exclamation_mark", "mark_ready_to_mail", "Ready", show=False),
        Binding("y", "refresh", "Refresh", show=False),
        Binding("slash", "edit_query", "Edit Query", show=False),
        Binding("at", "edit_spec", "Edit Spec", show=False),
        Binding("ctrl+d", "scroll_detail_down", "Scroll Down", show=False),
        Binding("ctrl+u", "scroll_detail_up", "Scroll Up", show=False),
        Binding("ctrl+f", "scroll_prompt_down", "Scroll Prompt Down", show=False),
        Binding("ctrl+b", "scroll_prompt_up", "Scroll Prompt Up", show=False),
        # Saved query keybindings (1-9, 0)
        Binding("1", "load_saved_query_1", "Load Q1", show=False),
        Binding("2", "load_saved_query_2", "Load Q2", show=False),
        Binding("3", "load_saved_query_3", "Load Q3", show=False),
        Binding("4", "load_saved_query_4", "Load Q4", show=False),
        Binding("5", "load_saved_query_5", "Load Q5", show=False),
        Binding("6", "load_saved_query_6", "Load Q6", show=False),
        Binding("7", "load_saved_query_7", "Load Q7", show=False),
        Binding("8", "load_saved_query_8", "Load Q8", show=False),
        Binding("9", "load_saved_query_9", "Load Q9", show=False),
        Binding("0", "load_saved_query_0", "Load Q0", show=False),
        # Tab switching
        Binding("tab", "toggle_tab", "Tab", show=False, priority=True),
        # Agent actions (Agents tab only)
        Binding("space", "start_custom_agent", "Run Agent", show=False),
        Binding("x", "kill_agent", "Kill", show=False),
    ]

    # Reactive properties
    changespecs: reactive[list[ChangeSpec]] = reactive([], recompose=False)
    current_idx: reactive[int] = reactive(0, recompose=False)
    hooks_collapsed: reactive[bool] = reactive(True, recompose=False)
    commits_collapsed: reactive[bool] = reactive(True, recompose=False)
    mentors_collapsed: reactive[bool] = reactive(True, recompose=False)
    current_tab: reactive[TabName] = reactive("changespecs", recompose=False)

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
        self._hint_to_entry_id: dict[int, str] = {}
        self._hint_changespec_name: str = ""

        # Accept mode state
        self._accept_mode_active: bool = False
        self._accept_last_base: str | None = None

        # Fold mode state (for z key sub-command)
        self._fold_mode_active: bool = False

        # Tab state - track position in each tab
        self._changespecs_last_idx: int = 0
        self._agents_last_idx: int = 0
        self._agents: list[Agent] = []

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
        yield TabBar(id="tab-bar")
        with Horizontal(id="main-container"):
            # ChangeSpecs Tab (default visible)
            with Horizontal(id="changespecs-view"):
                with Vertical(id="list-container"):
                    yield ChangeSpecInfoPanel(id="info-panel")
                    yield ChangeSpecList(id="list-panel")
                with Vertical(id="detail-container"):
                    yield SavedQueriesPanel(id="saved-queries-panel")
                    yield SearchQueryPanel(id="search-query-panel")
                    with VerticalScroll(id="detail-scroll"):
                        yield ChangeSpecDetail(id="detail-panel")
            # Agents Tab (hidden by default)
            with Horizontal(id="agents-view", classes="hidden"):
                with Vertical(id="agent-list-container"):
                    yield AgentInfoPanel(id="agent-info-panel")
                    yield AgentList(id="agent-list-panel")
                with Vertical(id="agent-detail-container"):
                    yield AgentDetail(id="agent-detail-panel")
        yield KeybindingFooter(id="keybinding-footer")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the app on mount."""
        # Load initial changespecs and save as last query
        self._load_changespecs()
        self._save_current_query()

        # Initialize saved queries panel
        self._refresh_saved_queries_panel()

        # Set up auto-refresh timer if enabled
        if self.refresh_interval > 0:
            self._countdown_remaining = self.refresh_interval
            self._countdown_timer = self.set_interval(
                1, self._on_countdown_tick, name="countdown"
            )
            self._refresh_timer = self.set_interval(
                self.refresh_interval, self._on_auto_refresh, name="auto-refresh"
            )

    def watch_current_idx(self, old_idx: int, new_idx: int) -> None:
        """React to current_idx changes."""
        if old_idx != new_idx:
            if self.current_tab == "changespecs":
                self._refresh_display()
            else:
                self._refresh_agents_display()

    def watch_current_tab(self, old_tab: TabName, new_tab: TabName) -> None:
        """React to tab changes by showing/hiding views."""
        if old_tab == new_tab:
            return

        # Update tab bar indicator
        tab_bar = self.query_one("#tab-bar", TabBar)
        tab_bar.update_tab(new_tab)

        changespecs_view = self.query_one("#changespecs-view")
        agents_view = self.query_one("#agents-view")

        if new_tab == "changespecs":
            changespecs_view.remove_class("hidden")
            agents_view.add_class("hidden")
            self._refresh_display()
        else:
            changespecs_view.add_class("hidden")
            agents_view.remove_class("hidden")
            # Load agents on first access or refresh
            self._load_agents()
