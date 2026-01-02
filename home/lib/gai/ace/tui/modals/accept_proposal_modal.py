"""Accept proposal modal for the ace TUI."""

from accept_workflow.parsing import (
    expand_shorthand_proposals,
    parse_proposal_entries,
)
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from ...changespec import ChangeSpec
from ...hooks.core import get_last_accepted_history_entry_id


class _ProposalInput(Input):
    """Custom Input with readline-style key bindings."""

    BINDINGS = [
        ("ctrl+f", "cursor_right", "Forward"),
        ("ctrl+b", "cursor_left", "Backward"),
    ]


class AcceptProposalModal(ModalScreen[list[tuple[str, str | None]] | None]):
    """Modal for accepting proposals."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, changespec: ChangeSpec) -> None:
        """Initialize the accept proposal modal.

        Args:
            changespec: The ChangeSpec containing proposals
        """
        super().__init__()
        self.changespec = changespec
        self._last_accepted_base = get_last_accepted_history_entry_id(changespec)

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container():
            yield Label("Accept Proposals", id="modal-title")
            with VerticalScroll(id="proposals-display"):
                yield Static(self._format_proposals_display(), id="proposals-list")
            yield Static(self._format_help_text(), id="help-text")
            yield _ProposalInput(
                placeholder="e.g., a b(msg) or 2a 2b(msg)", id="proposal-input"
            )
            yield Static("", id="error-message")
            with Horizontal(id="button-row"):
                yield Button("Accept", id="accept", variant="primary")
                yield Button("Cancel", id="cancel", variant="default")

    def _format_proposals_display(self) -> str:
        """Format the available proposals for display."""
        if not self.changespec.commits:
            return "No proposals available"

        lines: list[str] = []
        for entry in self.changespec.commits:
            if entry.is_proposed:
                display_id = entry.display_number
                note = entry.note or ""
                if note:
                    lines.append(f"  ({display_id}) {note}")
                else:
                    lines.append(f"  ({display_id})")

        if not lines:
            return "No proposals available"

        return "Available:\n" + "\n".join(lines)

    def _format_help_text(self) -> str:
        """Format help text showing syntax options."""
        if self._last_accepted_base:
            return (
                f"Syntax: a | a(msg) | 2a | a b c\n"
                f"Shorthand expands to base: {self._last_accepted_base}"
            )
        return "Syntax: 2a | 2a(msg) | 2a 2b 2c"

    def on_mount(self) -> None:
        """Focus the input on mount."""
        proposal_input = self.query_one("#proposal-input", _ProposalInput)
        proposal_input.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "accept":
            self._submit()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        self._submit()

    def _submit(self) -> None:
        """Validate and submit the input."""
        proposal_input = self.query_one("#proposal-input", Input)
        error_label = self.query_one("#error-message", Static)

        input_value = proposal_input.value.strip()
        if not input_value:
            error_label.update("[red]Please enter proposal IDs[/red]")
            return

        args = input_value.split()

        # Try to expand shorthand and parse
        expanded = expand_shorthand_proposals(args, self._last_accepted_base)
        if expanded is None:
            if self._last_accepted_base is None:
                error_label.update(
                    "[red]No accepted commits - cannot use shorthand (a b c)[/red]"
                )
            else:
                error_label.update("[red]Invalid format[/red]")
            return

        entries = parse_proposal_entries(expanded)
        if entries is None:
            error_label.update("[red]Invalid proposal format[/red]")
            return

        self.dismiss(entries)

    def action_cancel(self) -> None:
        """Cancel the modal."""
        self.dismiss(None)
