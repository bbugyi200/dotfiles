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
from ..hint_types import EditHooksResult, ViewFilesResult
from ..hints import (
    build_editor_args,
    is_rerun_input,
    parse_edit_hooks_input,
    parse_test_targets,
    parse_view_input,
)
from ..operations import get_available_workflows
from ..query import QueryParseError, evaluate_query, parse_query, to_canonical_string
from ..query.types import QueryExpr
from .modals import (
    QueryEditModal,
    StatusModal,
    WorkflowSelectModal,
)
from .widgets import (
    ChangeSpecDetail,
    ChangeSpecInfoPanel,
    ChangeSpecList,
    HintInputBar,
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

        # Re-render detail with hints for hooks_latest_only
        detail_widget = self.query_one("#detail-panel", ChangeSpecDetail)
        hint_mappings, hook_hint_to_idx = detail_widget.update_display_with_hints(
            changespec, self.canonical_query_string, hints_for="hooks_latest_only"
        )

        # Store state for later processing
        self._hint_mode_active = True
        self._hint_mode_hints_for = "hooks_latest_only"
        self._hint_mappings = hint_mappings
        self._hook_hint_to_idx = hook_hint_to_idx
        self._hint_changespec_name = changespec.name

        # Mount the hint input bar
        detail_container = self.query_one("#detail-container")
        hint_bar = HintInputBar(mode="hooks", id="hint-input-bar")
        detail_container.mount(hint_bar)

    def _apply_hook_changes(
        self,
        changespec: ChangeSpec,
        result: EditHooksResult,
        hook_hint_to_idx: dict[int, int],
    ) -> bool:
        """Apply hook changes based on modal result."""
        if result.action_type == "rerun_delete":
            return self._handle_rerun_delete_hooks(changespec, result, hook_hint_to_idx)
        elif result.action_type == "test_targets":
            return self._add_test_target_hooks(changespec, result.test_targets)
        else:
            return self._add_custom_hook(changespec, result.hook_command)

    def _handle_rerun_delete_hooks(
        self,
        changespec: ChangeSpec,
        result: EditHooksResult,
        hook_hint_to_idx: dict[int, int],
    ) -> bool:
        """Handle rerun/delete hook commands based on hint numbers."""
        from ..changespec import HookEntry
        from ..hooks import get_last_history_entry_id, update_changespec_hooks_field

        if not hook_hint_to_idx:
            self.notify("No hooks with status lines to rerun", severity="warning")
            return False

        last_history_entry_id = get_last_history_entry_id(changespec)
        if last_history_entry_id is None:
            self.notify("No HISTORY entries found", severity="warning")
            return False

        # Get the hook indices for each action
        hook_indices_to_rerun = {hook_hint_to_idx[h] for h in result.hints_to_rerun}
        hook_indices_to_delete = {hook_hint_to_idx[h] for h in result.hints_to_delete}

        # Create updated hooks list
        updated_hooks: list[HookEntry] = []
        for i, hook in enumerate(changespec.hooks or []):
            if i in hook_indices_to_delete:
                continue  # Skip (delete)
            elif i in hook_indices_to_rerun:
                if hook.status_lines:
                    remaining_status_lines = [
                        sl
                        for sl in hook.status_lines
                        if sl.commit_entry_num != last_history_entry_id
                    ]
                    updated_hooks.append(
                        HookEntry(
                            command=hook.command,
                            status_lines=(
                                remaining_status_lines
                                if remaining_status_lines
                                else None
                            ),
                        )
                    )
                else:
                    updated_hooks.append(hook)
            else:
                updated_hooks.append(hook)

        success = update_changespec_hooks_field(
            changespec.file_path, changespec.name, updated_hooks
        )

        if success:
            messages = []
            if result.hints_to_rerun:
                messages.append(
                    f"Cleared status for {len(result.hints_to_rerun)} hook(s)"
                )
            if result.hints_to_delete:
                messages.append(f"Deleted {len(result.hints_to_delete)} hook(s)")
            self.notify("; ".join(messages))
        else:
            self.notify("Error updating hooks", severity="error")

        return success

    def _add_test_target_hooks(
        self, changespec: ChangeSpec, test_targets: list[str]
    ) -> bool:
        """Add bb_rabbit_test hooks for each test target."""
        from ..hooks import add_hook_to_changespec

        added_count = 0
        for target in test_targets:
            hook_command = f"bb_rabbit_test {target}"
            success = add_hook_to_changespec(
                changespec.file_path,
                changespec.name,
                hook_command,
                changespec.hooks,
            )
            if success:
                added_count += 1

        if added_count > 0:
            self.notify(f"Added {added_count} test hook(s)")
            return True
        else:
            self.notify("Hooks already exist", severity="warning")
            return False

    def _add_custom_hook(
        self, changespec: ChangeSpec, hook_command: str | None
    ) -> bool:
        """Add a custom hook command."""
        from ..hooks import add_hook_to_changespec

        if not hook_command:
            return False

        success = add_hook_to_changespec(
            changespec.file_path,
            changespec.name,
            hook_command,
            changespec.hooks,
        )

        if success:
            self.notify(f"Added hook: {hook_command}")
        else:
            self.notify("Error adding hook", severity="error")

        return success

    def action_view_files(self) -> None:
        """View files for the current ChangeSpec."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        # Re-render detail with hints
        detail_widget = self.query_one("#detail-panel", ChangeSpecDetail)
        hint_mappings, _ = detail_widget.update_display_with_hints(
            changespec, self.canonical_query_string, hints_for=None
        )

        if len(hint_mappings) <= 1:  # Only hint 0 (project file)
            self.notify("No files available to view", severity="warning")
            self._refresh_display()  # Restore normal display
            return

        # Store state for later processing
        self._hint_mode_active = True
        self._hint_mode_hints_for = None  # "all" hints
        self._hint_mappings = hint_mappings
        self._hint_changespec_name = changespec.name

        # Mount the hint input bar
        detail_container = self.query_one("#detail-container")
        hint_bar = HintInputBar(mode="view", id="hint-input-bar")
        detail_container.mount(hint_bar)

    def _open_files_in_editor(self, result: ViewFilesResult) -> None:
        """Open files in $EDITOR (requires suspend)."""
        import subprocess

        def run_editor() -> None:
            editor = os.environ.get("EDITOR", "vi")
            editor_args = build_editor_args(
                editor, result.user_input, result.changespec_name, result.files
            )
            subprocess.run(editor_args, check=False)

        with self.suspend():
            run_editor()

    def _view_files_with_pager(self, files: list[str]) -> None:
        """View files using bat/cat with less (requires suspend)."""
        import shlex
        import shutil
        import subprocess

        def run_viewer() -> None:
            viewer = "bat" if shutil.which("bat") else "cat"
            quoted_files = " ".join(shlex.quote(f) for f in files)
            if viewer == "bat":
                cmd = f"bat --color=always {quoted_files} | less -R"
            else:
                cmd = f"cat {quoted_files} | less"
            subprocess.run(cmd, shell=True, check=False)

        with self.suspend():
            run_viewer()

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

    # --- Hint Input Bar Handling ---

    def on_hint_input_bar_submitted(self, event: HintInputBar.Submitted) -> None:
        """Handle hint input submission."""
        self._remove_hint_input_bar()

        if event.mode == "view":
            self._process_view_input(event.value)
        else:
            self._process_hooks_input(event.value)

    def on_hint_input_bar_cancelled(self, event: HintInputBar.Cancelled) -> None:
        """Handle hint input cancellation."""
        self._remove_hint_input_bar()

    def _remove_hint_input_bar(self) -> None:
        """Remove the hint input bar and restore normal display."""
        # Clear hint mode state first
        self._hint_mode_active = False
        self._hint_mode_hints_for = None

        try:
            hint_bar = self.query_one("#hint-input-bar", HintInputBar)
            hint_bar.remove()
        except Exception:
            pass
        self._refresh_display()

    def _process_view_input(self, user_input: str) -> None:
        """Process view files input."""
        if not user_input:
            return

        files, open_in_editor, invalid_hints = parse_view_input(
            user_input, self._hint_mappings
        )

        if invalid_hints:
            self.notify(
                f"Invalid hints: {', '.join(str(h) for h in invalid_hints)}",
                severity="warning",
            )
            return

        if not files:
            self.notify("No valid files selected", severity="warning")
            return

        if open_in_editor:
            result = ViewFilesResult(
                files=files,
                open_in_editor=True,
                user_input=user_input,
                changespec_name=self._hint_changespec_name,
            )
            self._open_files_in_editor(result)
        else:
            self._view_files_with_pager(files)

    def _process_hooks_input(self, user_input: str) -> None:
        """Process edit hooks input."""
        if not user_input:
            return

        changespec = self.changespecs[self.current_idx]

        if is_rerun_input(user_input):
            # Rerun/delete hooks
            hints_to_rerun, hints_to_delete, invalid_hints = parse_edit_hooks_input(
                user_input, self._hint_mappings
            )

            if invalid_hints:
                self.notify(
                    f"Invalid hints: {', '.join(str(h) for h in invalid_hints)}",
                    severity="warning",
                )
                return

            if not hints_to_rerun and not hints_to_delete:
                self.notify("No valid hooks selected", severity="warning")
                return

            result = EditHooksResult(
                action_type="rerun_delete",
                hints_to_rerun=hints_to_rerun,
                hints_to_delete=hints_to_delete,
            )
            success = self._apply_hook_changes(
                changespec, result, self._hook_hint_to_idx
            )
            if success:
                self._reload_and_reposition()

        elif user_input.startswith("//"):
            # Test targets
            targets = parse_test_targets(user_input)
            if not targets:
                self.notify("No test targets provided", severity="warning")
                return

            result = EditHooksResult(
                action_type="test_targets",
                test_targets=targets,
            )
            success = self._apply_hook_changes(
                changespec, result, self._hook_hint_to_idx
            )
            if success:
                self._reload_and_reposition()

        else:
            # Custom hook command
            result = EditHooksResult(
                action_type="custom_hook",
                hook_command=user_input,
            )
            success = self._apply_hook_changes(
                changespec, result, self._hook_hint_to_idx
            )
            if success:
                self._reload_and_reposition()
