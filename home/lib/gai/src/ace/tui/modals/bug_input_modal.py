"""Bug number input modal for the ace TUI."""

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


@dataclass
class BugInputResult:
    """Result from BugInputModal."""

    bug: str | None  # None if skipped/cancelled (stripped of @ suffix)
    cancelled: bool
    is_fixed: bool = False  # True if @ suffix was present


class _BugInput(Input):
    """Custom Input with readline-style key bindings."""

    BINDINGS = [
        ("ctrl+f", "cursor_right", "Forward"),
        ("ctrl+b", "cursor_left", "Backward"),
    ]


class BugInputModal(ModalScreen[BugInputResult | None]):
    """Modal for inputting an optional bug number.

    Returns BugInputResult with bug number if provided, or None if skipped.
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container():
            yield Label("Enter Bug Number (Optional)", id="modal-title")
            yield Label(
                "Leave empty to skip. Use @ suffix for FIXED bugs (e.g., 123@). "
                "Stored as BUG: or FIXED: http://b/<number>",
                id="modal-instructions",
            )
            yield _BugInput(placeholder="e.g., 123456789 or 123456789@", id="bug-input")
            with Horizontal(id="button-row"):
                yield Button("Continue", id="continue", variant="primary")
                yield Button("Skip", id="skip", variant="default")
                yield Button("Cancel", id="cancel", variant="error")

    def on_mount(self) -> None:
        """Focus the input on mount."""
        bug_input = self.query_one("#bug-input", _BugInput)
        bug_input.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "continue":
            self._submit_value()
        elif event.button.id == "skip":
            self.dismiss(BugInputResult(bug=None, cancelled=False))
        else:
            self.dismiss(BugInputResult(bug=None, cancelled=True))

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        self._submit_value()

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
