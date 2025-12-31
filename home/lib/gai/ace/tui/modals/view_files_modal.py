"""View files modal for the ace TUI."""

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from ...hint_types import HintItem, ViewFilesResult
from ...hints import parse_view_input


class _HintInput(Input):
    """Custom Input with readline-style key bindings."""

    BINDINGS = [
        ("ctrl+f", "cursor_right", "Forward"),
        ("ctrl+b", "cursor_left", "Backward"),
    ]


class ViewFilesModal(ModalScreen[ViewFilesResult | None]):
    """Modal for selecting files to view."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("q", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        hints: list[HintItem],
        hint_mappings: dict[int, str],
        changespec_name: str,
    ) -> None:
        """Initialize the view files modal.

        Args:
            hints: List of HintItem objects to display
            hint_mappings: Dict mapping hint numbers to file paths
            changespec_name: The ChangeSpec name (for editor positioning)
        """
        super().__init__()
        self.hints = hints
        self.hint_mappings = hint_mappings
        self.changespec_name = changespec_name

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="view-files-container"):
            yield Label("View Files", id="modal-title")
            yield Static(self._build_hints_display(), id="hints-display")
            yield Label(
                "Enter hint numbers (e.g., '1 2 3@'). Use '@' to open in $EDITOR.",
                id="hint-prompt",
            )
            yield _HintInput(placeholder="0 1 2@", id="hint-input")
            yield Static("", id="error-message")
            with Horizontal(id="button-row"):
                yield Button("View", id="view", variant="primary")
                yield Button("Cancel", id="cancel", variant="default")

    def _build_hints_display(self) -> Text:
        """Build Rich Text display of available hints."""
        text = Text()
        for item in self.hints:
            text.append(f"[{item.hint_number}] ", style="bold #FFFF00")
            text.append(f"{item.display_text}\n", style="#87AFFF")
        # Remove trailing newline
        text.rstrip()
        return text

    def on_mount(self) -> None:
        """Focus the input on mount."""
        hint_input = self.query_one("#hint-input", _HintInput)
        hint_input.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "view":
            self._submit_input()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        self._submit_input()

    def _submit_input(self) -> None:
        """Process and submit the user input."""
        hint_input = self.query_one("#hint-input", Input)
        user_input = hint_input.value.strip()

        if not user_input:
            self.dismiss(None)
            return

        files, open_in_editor, invalid_hints = parse_view_input(
            user_input, self.hint_mappings
        )

        if invalid_hints:
            error_msg = self.query_one("#error-message", Static)
            error_msg.update(
                Text(
                    f"Invalid hints: {', '.join(str(h) for h in invalid_hints)}",
                    style="red",
                )
            )
            return

        if not files:
            error_msg = self.query_one("#error-message", Static)
            error_msg.update(Text("No valid files selected", style="red"))
            return

        self.dismiss(
            ViewFilesResult(
                files=files,
                open_in_editor=open_in_editor,
                user_input=user_input,
                changespec_name=self.changespec_name,
            )
        )

    def action_cancel(self) -> None:
        """Cancel the modal."""
        self.dismiss(None)
