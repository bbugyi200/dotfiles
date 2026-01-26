"""Bug number input modal for the ace TUI with bb_bugs integration."""

from dataclasses import dataclass
from subprocess import TimeoutExpired
from subprocess import run as subprocess_run

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static
from textual.widgets.option_list import Option
from textual.worker import Worker, WorkerState

from .base import FilterInput


@dataclass
class _Bug:
    """A bug from bb_bugs command output."""

    issue: str
    component: str
    created: str
    modified: str
    reporter: str
    assignee: str
    priority: str
    status: str
    summary: str


@dataclass
class BugInputResult:
    """Result from BugInputModal."""

    bug: str | None  # None if skipped/cancelled (stripped of @ suffix)
    cancelled: bool
    is_fixed: bool = False  # True if @ suffix was present


def _parse_bb_bugs_output(output: str) -> list[_Bug]:
    """Parse bb_bugs table output into Bug objects."""
    bugs: list[_Bug] = []
    lines = output.strip().split("\n")

    if len(lines) < 2:
        return bugs

    # Skip header line
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 8:
            continue

        # Columns: issue, component, created, modified, reporter, assignee,
        # priority, status, summary...
        issue = parts[0]
        component = parts[1]
        created = parts[2]
        modified = parts[3]
        reporter = parts[4]
        assignee = parts[5]
        priority = parts[6]
        status = parts[7]
        summary = " ".join(parts[8:]) if len(parts) > 8 else ""

        bugs.append(
            _Bug(
                issue=issue,
                component=component,
                created=created,
                modified=modified,
                reporter=reporter,
                assignee=assignee,
                priority=priority,
                status=status,
                summary=summary,
            )
        )

    return bugs


class BugInputModal(ModalScreen[BugInputResult | None]):
    """Modal for inputting an optional bug number with bb_bugs integration.

    Returns BugInputResult with bug number if provided, or None if skipped.
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+n", "next_option", "Next"),
        ("ctrl+p", "prev_option", "Previous"),
    ]

    def __init__(self) -> None:
        """Initialize the bug input modal."""
        super().__init__()
        self._bugs: list[_Bug] = []
        self._filtered_bugs: list[_Bug] = []
        self._has_selected_bug: bool = False
        self._loading: bool = True
        self._load_error: str | None = None
        self._current_worker: Worker[list[_Bug]] | None = None

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="bug-modal-container"):
            yield Label("Enter Bug Number (Optional)", id="modal-title")
            yield Label(
                "Leave empty to skip. Use @ suffix for FIXED bugs (e.g., 123@). "
                "Stored as BUG: or FIXED: http://b/<number>",
                id="modal-instructions",
            )
            yield FilterInput(
                placeholder="Type to filter or enter bug ID...", id="bug-input"
            )
            yield Label("Loading bugs...", id="bug-status")
            yield OptionList(id="bug-list")
            yield Static(
                "^n/^p: navigate • Enter: select/submit • Esc: cancel",
                id="bug-hints",
            )
            with Horizontal(id="button-row"):
                yield Button("Continue", id="continue", variant="primary")
                yield Button("Skip", id="skip", variant="default")
                yield Button("Cancel", id="cancel", variant="error")

    def on_mount(self) -> None:
        """Focus the input and start loading bugs on mount."""
        bug_input = self.query_one("#bug-input", FilterInput)
        bug_input.focus()
        # Start async bug loading
        self._current_worker = self.run_worker(self._fetch_bugs, thread=True)

    def _fetch_bugs(self) -> list[_Bug]:
        """Fetch bugs from bb_bugs command (runs in background thread)."""
        try:
            result = subprocess_run(
                ["bb_bugs"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise RuntimeError(f"bb_bugs failed: {result.stderr}")
            return _parse_bb_bugs_output(result.stdout)
        except TimeoutExpired as e:
            raise RuntimeError("bb_bugs timed out") from e
        except FileNotFoundError as e:
            raise RuntimeError("bb_bugs command not found") from e

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker completion."""
        if event.worker != self._current_worker:
            return

        if event.state == WorkerState.SUCCESS:
            self._bugs = event.worker.result or []
            self._filtered_bugs = self._bugs.copy()
            self._loading = False
            self._update_bug_list()
            self._update_status_label()
        elif event.state == WorkerState.ERROR:
            self._loading = False
            self._load_error = str(event.worker.error)
            self._update_status_label()

    def _update_status_label(self) -> None:
        """Update the status label based on loading state."""
        status = self.query_one("#bug-status", Label)
        if self._loading:
            status.update("Loading bugs...")
        elif self._load_error:
            status.update(f"Error: {self._load_error}")
        else:
            count = len(self._filtered_bugs)
            total = len(self._bugs)
            if count == total:
                status.update(f"{count} bug(s) found")
            else:
                status.update(f"{count} of {total} bug(s) matching")

    def _update_bug_list(self) -> None:
        """Update the OptionList with filtered bugs."""
        option_list = self.query_one("#bug-list", OptionList)
        option_list.clear_options()
        for bug in self._filtered_bugs:
            option_list.add_option(Option(self._create_bug_label(bug), id=bug.issue))
        # Clear highlight - no bug selected initially
        option_list.highlighted = None

    def _create_bug_label(self, bug: _Bug) -> Text:
        """Create styled text for a bug option (summary only)."""
        text = Text()
        summary = bug.summary
        # Truncate long summaries
        if len(summary) > 80:
            summary = summary[:77] + "..."
        text.append(summary)
        return text

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input change - filter the bug list by summary."""
        filter_text = event.value.strip().lower()

        # Reset selection state when user types (unless they just selected a bug)
        if self._has_selected_bug:
            # Check if input still matches a bug ID
            input_value = event.value.strip().rstrip("@")
            if not any(b.issue == input_value for b in self._bugs):
                self._has_selected_bug = False

        # Filter bugs by summary only (case-insensitive)
        if filter_text:
            self._filtered_bugs = [
                bug for bug in self._bugs if filter_text in bug.summary.lower()
            ]
        else:
            self._filtered_bugs = self._bugs.copy()

        self._update_bug_list()
        self._update_status_label()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        """Handle Enter key - two-phase behavior."""
        bug_input = self.query_one("#bug-input", FilterInput)

        if self._has_selected_bug:
            # Phase 2: Submit the selected bug ID
            self._submit_value()
        else:
            # Phase 1: Select highlighted bug (if any)
            option_list = self.query_one("#bug-list", OptionList)
            highlighted = option_list.highlighted
            if highlighted is not None and 0 <= highlighted < len(self._filtered_bugs):
                # Replace input with bug ID
                selected_bug = self._filtered_bugs[highlighted]
                bug_input.value = selected_bug.issue
                bug_input.cursor_position = len(selected_bug.issue)
                self._has_selected_bug = True
            else:
                # No selection - submit whatever is in the input (even if empty)
                self._submit_value()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection (Enter or click on list item)."""
        if event.option and event.option.id:
            bug_input = self.query_one("#bug-input", FilterInput)
            bug_id = str(event.option.id)
            bug_input.value = bug_id
            bug_input.cursor_position = len(bug_id)
            self._has_selected_bug = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "continue":
            self._submit_value()
        elif event.button.id == "skip":
            self.dismiss(BugInputResult(bug=None, cancelled=False))
        else:
            self.dismiss(BugInputResult(bug=None, cancelled=True))

    def _submit_value(self) -> None:
        """Validate and submit the input value."""
        bug_input = self.query_one("#bug-input", Input)
        value = bug_input.value.strip()

        # Check for @ suffix indicating FIXED bug
        is_fixed = value.endswith("@")
        if is_fixed:
            value = value[:-1]  # Strip the @ suffix

        self.dismiss(
            BugInputResult(
                bug=value if value else None, cancelled=False, is_fixed=is_fixed
            )
        )

    def action_cancel(self) -> None:
        """Cancel the modal."""
        self.dismiss(BugInputResult(bug=None, cancelled=True))

    def action_next_option(self) -> None:
        """Move to next bug option."""
        if self._filtered_bugs:
            self.query_one("#bug-list", OptionList).action_cursor_down()

    def action_prev_option(self) -> None:
        """Move to previous bug option."""
        if self._filtered_bugs:
            self.query_one("#bug-list", OptionList).action_cursor_up()
