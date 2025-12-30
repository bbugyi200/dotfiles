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

from ..changespec import ChangeSpec, find_all_changespecs, has_ready_to_mail_suffix
from ..operations import get_available_workflows
from ..query import QueryParseError, evaluate_query, parse_query, to_canonical_string
from ..query.types import QueryExpr
from .modals import QueryEditModal, StatusModal, WorkflowSelectModal
from .widgets import (
    ChangeSpecDetail,
    ChangeSpecInfoPanel,
    ChangeSpecList,
    KeybindingFooter,
    SearchQueryPanel,
)


class AceApp(App[None]):
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

    # --- Status Actions ---

    def action_change_status(self) -> None:
        """Open status change modal."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        def on_dismiss(new_status: str | None) -> None:
            if new_status:
                self._apply_status_change(changespec, new_status)

        self.push_screen(StatusModal(changespec.status), on_dismiss)

    def _apply_status_change(self, changespec: ChangeSpec, new_status: str) -> None:
        """Apply a status change to a ChangeSpec."""
        from status_state_machine import (
            remove_ready_to_mail_suffix,
            transition_changespec_status,
        )

        from ..revert import revert_changespec
        from ..status import STATUS_REVERTED

        # Special handling for "Reverted" status
        if new_status == STATUS_REVERTED:
            # Need to suspend for revert workflow
            def run_revert() -> tuple[bool, str | None]:
                from rich.console import Console

                console = Console()
                return revert_changespec(changespec, console)

            with self.suspend():
                success, error_msg = run_revert()

            if not success:
                self.notify(f"Error reverting: {error_msg}", severity="error")
            self._reload_and_reposition()
            return

        # Remove READY TO MAIL suffix if present before transitioning
        remove_ready_to_mail_suffix(changespec.file_path, changespec.name)

        # Update the status in the project file
        success, old_status, error_msg = transition_changespec_status(
            changespec.file_path,
            changespec.name,
            new_status,
            validate=False,
        )

        if success:
            self.notify(f"Status updated: {old_status} -> {new_status}")
        else:
            self.notify(f"Error: {error_msg}", severity="error")

        self._reload_and_reposition()

    # --- Workflow Actions ---

    def action_run_workflow(self) -> None:
        """Run a workflow on the current ChangeSpec."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]
        workflows = get_available_workflows(changespec)

        if not workflows:
            self.notify("No workflows available", severity="warning")
            return

        if len(workflows) == 1:
            # Single workflow, run directly
            self._run_workflow(changespec, 0)
        else:
            # Multiple workflows, show selection modal

            def on_dismiss(workflow_idx: int | None) -> None:
                if workflow_idx is not None:
                    self._run_workflow(changespec, workflow_idx)

            self.push_screen(WorkflowSelectModal(workflows), on_dismiss)

    def _run_workflow(self, changespec: ChangeSpec, workflow_index: int) -> None:
        """Run a specific workflow."""
        from ..handlers import handle_run_workflow

        def run_handler() -> tuple[list[ChangeSpec], int]:
            from ._workflow_context import WorkflowContext

            ctx = WorkflowContext()
            return handle_run_workflow(
                ctx,  # type: ignore[arg-type]
                changespec,
                self.changespecs,
                self.current_idx,
                workflow_index,
            )

        with self.suspend():
            try:
                new_changespecs, new_idx = run_handler()
            except Exception as e:
                self.notify(f"Workflow error: {e}", severity="error")
                self._reload_and_reposition()
                return

        self._reload_and_reposition()

    def action_run_query(self) -> None:
        """Run a query on the current ChangeSpec."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        from ..handlers import handle_run_query

        def run_handler() -> None:
            from ._workflow_context import WorkflowContext

            ctx = WorkflowContext()
            handle_run_query(ctx, changespec)  # type: ignore[arg-type]

        with self.suspend():
            run_handler()

        self._reload_and_reposition()

    # --- Tool Actions ---

    def action_show_diff(self) -> None:
        """Show diff for the current ChangeSpec."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        from ..handlers import handle_show_diff

        def run_handler() -> None:
            from ._workflow_context import WorkflowContext

            ctx = WorkflowContext()
            handle_show_diff(ctx, changespec)  # type: ignore[arg-type]

        with self.suspend():
            run_handler()

    def action_mail(self) -> None:
        """Mail the current ChangeSpec."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        if not has_ready_to_mail_suffix(changespec.status):
            self.notify("ChangeSpec is not ready to mail", severity="warning")
            return

        from ..handlers import handle_mail

        def run_handler() -> tuple[list[ChangeSpec], int]:
            from ._workflow_context import WorkflowContext

            ctx = WorkflowContext()
            return handle_mail(ctx, changespec, self.changespecs, self.current_idx)  # type: ignore[arg-type]

        with self.suspend():
            run_handler()

        self._reload_and_reposition()

    def action_findreviewers(self) -> None:
        """Find reviewers for the current ChangeSpec."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        if not has_ready_to_mail_suffix(changespec.status):
            self.notify("ChangeSpec is not ready to mail", severity="warning")
            return

        from ..handlers import handle_findreviewers

        def run_handler() -> None:
            from ._workflow_context import WorkflowContext

            ctx = WorkflowContext()
            handle_findreviewers(ctx, changespec)  # type: ignore[arg-type]

        with self.suspend():
            run_handler()

    def action_edit_hooks(self) -> None:
        """Edit hooks for the current ChangeSpec."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        from ..handlers import handle_edit_hooks

        def run_handler() -> tuple[list[ChangeSpec], int]:
            from ._workflow_context import WorkflowContext

            ctx = WorkflowContext()
            return handle_edit_hooks(
                ctx,  # type: ignore[arg-type]
                changespec,
                self.changespecs,
                self.current_idx,
            )

        with self.suspend():
            run_handler()

        self._reload_and_reposition()

    def action_view_files(self) -> None:
        """View files for the current ChangeSpec."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        from ..workflow.actions import handle_view

        def run_handler() -> None:
            from ._workflow_context import WorkflowContext

            ctx = WorkflowContext()
            handle_view(ctx, changespec)  # type: ignore[arg-type]

        with self.suspend():
            run_handler()

    def action_accept_proposal(self) -> None:
        """Accept a proposal for the current ChangeSpec."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        # Check if there are proposed entries
        if not changespec.commits or not any(e.is_proposed for e in changespec.commits):
            self.notify("No proposals to accept", severity="warning")
            return

        from ..workflow.actions import handle_accept_proposal

        def run_handler() -> tuple[list[ChangeSpec], int]:
            from ._workflow_context import WorkflowContext

            ctx = WorkflowContext()
            # For now, prompt in suspended mode for which proposal
            # The user input "a 2a" pattern needs interactive input
            return handle_accept_proposal(
                ctx,  # type: ignore[arg-type]
                changespec,
                self.changespecs,
                self.current_idx,
                "a",
            )

        with self.suspend():
            run_handler()

        self._reload_and_reposition()

    def action_refresh(self) -> None:
        """Refresh the ChangeSpec list."""
        self._reload_and_reposition()
        self.notify("Refreshed")

    def action_edit_query(self) -> None:
        """Edit the search query."""
        current_canonical = self.canonical_query_string

        def on_dismiss(new_query: str | None) -> None:
            if new_query:
                try:
                    new_parsed = parse_query(new_query)
                    new_canonical = to_canonical_string(new_parsed)
                    # Only update if the canonical form changed
                    if new_canonical != current_canonical:
                        self.query_string = new_query
                        self.parsed_query = new_parsed
                        self._load_changespecs()
                        self.notify("Query updated")
                except QueryParseError as e:
                    self.notify(f"Invalid query: {e}", severity="error")

        self.push_screen(QueryEditModal(current_canonical), on_dismiss)

    # --- List Selection Handling ---

    def on_change_spec_list_selection_changed(
        self, event: ChangeSpecList.SelectionChanged
    ) -> None:
        """Handle selection change in the list widget."""
        if 0 <= event.index < len(self.changespecs):
            self.current_idx = event.index
