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

from axe.state import AxeMetrics, AxeStatus

from ..changespec import ChangeSpec
from ..query import parse_query, to_canonical_string
from ..query.types import QueryExpr
from .actions import (
    AgentsMixin,
    AgentWorkflowMixin,
    AxeMixin,
    BaseActionsMixin,
    ChangeSpecMixin,
    ClipboardMixin,
    EventHandlersMixin,
    HintActionsMixin,
    MarkingMixin,
    NavigationMixin,
    ProposalRebaseMixin,
    RenameMixin,
    SyncMixin,
)
from .models import Agent
from .widgets import (
    AgentDetail,
    AgentInfoPanel,
    AgentList,
    AncestorsChildrenPanel,
    AxeDashboard,
    AxeInfoPanel,
    BgCmdList,
    ChangeSpecDetail,
    ChangeSpecInfoPanel,
    ChangeSpecList,
    KeybindingFooter,
    SearchQueryPanel,
    TabBar,
)

# Type alias for tab names
TabName = Literal["changespecs", "agents", "axe"]

# Width bounds for dynamic list panel sizing (in terminal cells)
# MIN must fit: "ChangeSpec: X/Y   (auto-refresh in Ns)" + padding/border
_MIN_LIST_WIDTH = 43
_MAX_LIST_WIDTH = 80

# Width bounds for agent list panel
_MIN_AGENT_LIST_WIDTH = 40
_MAX_AGENT_LIST_WIDTH = 70


class AceApp(
    AgentWorkflowMixin,
    AgentsMixin,
    AxeMixin,
    ChangeSpecMixin,
    ClipboardMixin,
    EventHandlersMixin,
    MarkingMixin,
    NavigationMixin,
    ProposalRebaseMixin,
    RenameMixin,
    SyncMixin,
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
        Binding("M", "mail", "Mail", show=False),
        Binding("d", "show_diff", "Diff", show=False),
        Binding("w", "reword", "Reword", show=False),
        Binding("v", "view_files", "View", show=False),
        Binding("h", "edit_hooks", "Hooks", show=False),
        Binding("H", "hooks_from_failed", "Hooks (Failed)", show=False),
        Binding("z", "start_fold_mode", "Fold", show=False),
        Binding("a", "accept_proposal", "Accept", show=False),
        Binding("b", "rebase", "Rebase", show=False),
        Binding("T", "open_tmux", "Tmux", show=False),
        Binding("t", "start_tmux_mode", "Tmux Mode", show=False),
        Binding("C", "checkout", "Checkout", show=False),
        Binding("c", "start_checkout_mode", "Checkout Mode", show=False),
        # Note: "!" binding removed - use "a" then "@" to mark ready to mail
        Binding("R", "refresh", "Refresh", show=False),
        Binding("y", "sync", "Sync", show=False),
        Binding("slash", "edit_query", "Edit Query", show=False),
        Binding("e", "edit_spec", "Edit Spec", show=False),
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
        Binding("tab", "next_tab", "Next Tab", show=False, priority=True),
        Binding("shift+tab", "prev_tab", "Prev Tab", show=False, priority=True),
        # Axe control (global)
        Binding("X", "toggle_axe", "Start/Stop Axe", show=False),
        Binding("Q", "stop_axe_and_quit", "Stop & Quit", show=False),
        # Agent workflow (all tabs) - shows project/CL selection modals
        Binding("at", "start_custom_agent", "Run Agent", show=False),
        # Run agent from ChangeSpec (CLs tab only)
        Binding("space", "start_agent_from_changespec", "Run Agent (CL)", show=False),
        # Background command (all tabs)
        Binding("exclamation_mark", "start_bgcmd", "Run Cmd", show=False),
        # Marking (CLs tab only)
        Binding("m", "toggle_mark", "Mark", show=False),
        Binding("n", "rename_cl", "Rename", show=False),
        Binding("u", "clear_marks", "Unmark All", show=False),
        Binding("x", "kill_agent", "Kill", show=False),
        Binding("l", "toggle_layout", "Layout", show=False),
        # Copy to clipboard (all tabs)
        Binding("percent_sign", "copy_tab_content", "Copy", show=False),
        # Scroll to top/bottom (Axe tab)
        Binding("g", "scroll_to_top", "Top", show=False),
        Binding("G", "scroll_to_bottom", "Bottom", show=False),
        # Help
        Binding("question_mark", "show_help", "Help", show=False),
        # Query history navigation
        Binding("circumflex_accent", "prev_query", "Prev Query", show=False),
        Binding("underscore", "next_query", "Next Query", show=False),
        # ChangeSpec history navigation (vim-style jumplist)
        Binding("ctrl+o", "prev_changespec_history", "Prev CL History", show=False),
        Binding("ctrl+k", "next_changespec_history", "Next CL History", show=False),
        # Ancestor/child navigation
        Binding("<", "start_ancestor_mode", "Ancestor", show=False),
        Binding(">", "start_child_mode", "Child", show=False),
        # Hide/show reverted
        Binding("full_stop", "toggle_hide_reverted", "Toggle Reverted", show=False),
    ]

    # Reactive properties
    changespecs: reactive[list[ChangeSpec]] = reactive([], recompose=False)
    current_idx: reactive[int] = reactive(0, recompose=False)
    hooks_collapsed: reactive[bool] = reactive(True, recompose=False)
    commits_collapsed: reactive[bool] = reactive(True, recompose=False)
    mentors_collapsed: reactive[bool] = reactive(True, recompose=False)
    current_tab: reactive[TabName] = reactive("changespecs", recompose=False)
    axe_running: reactive[bool] = reactive(False, recompose=False)
    hide_reverted: reactive[bool] = reactive(True, recompose=False)
    hide_non_run_agents: reactive[bool] = reactive(True, recompose=False)
    marked_indices: reactive[set[int]] = reactive(set, recompose=False)

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

        # Checkout/tmux mode state (for c/t key sub-commands)
        self._checkout_mode_active: bool = False
        self._tmux_mode_active: bool = False

        # Ancestor/child navigation state
        self._ancestor_mode_active: bool = False
        self._child_mode_active: bool = False
        self._child_key_buffer: str = ""  # Buffer for multi-key child sequences
        self._ancestor_keys: dict[str, str] = {}  # name -> keymap
        self._children_keys: dict[str, str] = {}  # key -> name (for navigation)
        self._all_changespecs: list[ChangeSpec] = []  # Cache for ancestry lookup
        self._hidden_reverted_count: int = 0  # Count of filtered reverted CLs

        # Tab state - track position in each tab
        self._changespecs_last_idx: int = 0
        self._agents_last_idx: int = 0
        self._agents: list[Agent] = []
        self._revived_agents: list[Agent] = []
        self._has_always_visible: bool = False
        self._hidden_count: int = 0

        # Axe state
        self._axe_status: AxeStatus | None = None
        self._axe_metrics: AxeMetrics | None = None
        self._axe_output: str = ""
        self._axe_pinned_to_bottom: bool = True

        # Background command state
        from .bgcmd import BackgroundCommandInfo

        self._axe_current_view: Literal["axe"] | int = "axe"
        self._bgcmd_slots: list[tuple[int, BackgroundCommandInfo]] = []

        # Query history stacks for prev/next navigation
        from ..query_history import load_query_history

        self._query_history = load_query_history()

        # ChangeSpec history stacks for ctrl+o/ctrl+i navigation (session-based)
        from .changespec_history import create_empty_stacks as create_cs_history_stacks

        self._changespec_history = create_cs_history_stacks()

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
                    yield AncestorsChildrenPanel(id="ancestors-children-panel")
                with Vertical(id="detail-container"):
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
            # Axe Tab (hidden by default)
            with Horizontal(id="axe-view", classes="hidden"):
                # Left panel (bgcmd list) - hidden by default, shown when bgcmds exist
                with Vertical(id="bgcmd-list-container", classes="hidden"):
                    yield BgCmdList(id="bgcmd-list-panel")
                # Right panel (dashboard)
                with Vertical(id="axe-container"):
                    yield AxeInfoPanel(id="axe-info-panel")
                    yield AxeDashboard(id="axe-dashboard")
        yield KeybindingFooter(id="keybinding-footer")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the app on mount."""
        # Load revived agents from persistence
        self._load_revived_agents()

        # Load initial changespecs and save as last query
        self._load_changespecs()
        self._restore_last_selection()
        self._save_current_query()

        # Initialize axe status
        self._load_axe_status()

        # Set up auto-refresh timer if enabled
        if self.refresh_interval > 0:
            self._countdown_remaining = self.refresh_interval
            self._countdown_timer = self.set_interval(
                1, self._on_countdown_tick, name="countdown"
            )
            self._refresh_timer = self.set_interval(
                self.refresh_interval, self._on_auto_refresh, name="auto-refresh"
            )

    def _save_current_selection(self) -> None:
        """Save the currently selected ChangeSpec name."""
        from ..last_selection import save_last_selection

        if self.changespecs:
            changespec = self.changespecs[self.current_idx]
            save_last_selection(changespec.name)

    def _restore_last_selection(self) -> None:
        """Restore the previously selected ChangeSpec if it exists."""
        from ..last_selection import load_last_selection

        last_name = load_last_selection()
        if last_name is None:
            return
        for idx, cs in enumerate(self.changespecs):
            if cs.name == last_name:
                self.current_idx = idx
                return

    async def action_quit(self) -> None:
        """Quit the application, saving the current selection."""
        self._save_current_selection()
        self.exit()

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
        axe_view = self.query_one("#axe-view")

        if new_tab == "changespecs":
            changespecs_view.remove_class("hidden")
            agents_view.add_class("hidden")
            axe_view.add_class("hidden")
            self._refresh_display()
        elif new_tab == "agents":
            changespecs_view.add_class("hidden")
            agents_view.remove_class("hidden")
            axe_view.add_class("hidden")
            # Load agents on first access or refresh
            self._load_agents()
        else:  # axe
            changespecs_view.add_class("hidden")
            agents_view.add_class("hidden")
            axe_view.remove_class("hidden")
            # Load axe status
            self._load_axe_status()

        # If help modal is open, refresh it with new tab context
        from .modals import HelpModal

        if isinstance(self.screen, HelpModal):
            self.screen.dismiss(None)
            self.push_screen(
                HelpModal(
                    current_tab=new_tab,
                    active_query=self.canonical_query_string,
                )
            )
