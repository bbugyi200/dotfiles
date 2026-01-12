"""CL name input modal for the ace TUI."""

from typing import Literal

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class _CLNameInput(Input):
    """Custom Input with readline-style key bindings."""

    BINDINGS = [
        ("ctrl+f", "cursor_right", "Forward"),
        ("ctrl+b", "cursor_left", "Backward"),
    ]


class CLNameInputModal(ModalScreen[str | None]):
    """Modal for inputting a new CL name.

    For project selections, the CL name is required.
    For existing CL selections, it's optional (empty = add proposal to existing CL).
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        selection_type: Literal["project", "cl"],
        selected_cl_name: str | None = None,
    ) -> None:
        """Initialize the CL name input modal.

        Args:
            selection_type: Whether user selected a "project" or "cl"
            selected_cl_name: The name of the selected CL (if selection_type is "cl")
        """
        super().__init__()
        self.selection_type = selection_type
        self.selected_cl_name = selected_cl_name

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container():
            yield Label("Enter New CL Name", id="modal-title")

            # Show different instructions based on selection type
            if self.selection_type == "project":
                yield Label(
                    "Required: Enter a name for the new ChangeSpec",
                    id="modal-instructions",
                )
            else:
                yield Label(
                    f"Optional: Leave empty to add proposal to '{self.selected_cl_name}'",
                    id="modal-instructions",
                )

            yield _CLNameInput(placeholder="new_cl_name", id="cl-name-input")
            with Horizontal(id="button-row"):
                yield Button("Continue", id="apply", variant="primary")
                yield Button("Cancel", id="cancel", variant="default")

    def on_mount(self) -> None:
        """Focus the input on mount."""
        cl_input = self.query_one("#cl-name-input", _CLNameInput)
        cl_input.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "apply":
            self._submit_value()
        else:
            self.dismiss(None)

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        self._submit_value()

    def _submit_value(self) -> None:
        """Validate and submit the input value."""
        cl_input = self.query_one("#cl-name-input", Input)
        value = cl_input.value.strip()

        # For projects, CL name is required
        if self.selection_type == "project" and not value:
            # Show error - don't dismiss
            self.notify("CL name is required for projects", severity="error")
            return

        # Return value or None if empty
        self.dismiss(value if value else None)

    def action_cancel(self) -> None:
        """Cancel the modal."""
        self.dismiss(None)
