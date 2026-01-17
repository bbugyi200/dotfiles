"""Workspace input modal for the ace TUI."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Input, Label


class _WorkspaceInput(Input):
    """Custom Input with readline-style key bindings."""

    BINDINGS = [
        ("ctrl+f", "cursor_right", "Forward"),
        ("ctrl+b", "cursor_left", "Backward"),
    ]


class WorkspaceInputModal(ModalScreen[int | None]):
    """Modal for entering workspace number."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, default_workspace: int = 1) -> None:
        """Initialize the workspace input modal.

        Args:
            default_workspace: Default workspace number to show.
        """
        super().__init__()
        self._default_workspace = default_workspace

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container():
            yield Label("Enter Workspace Number", id="modal-title")
            yield Label(
                "Enter workspace number (1-9). Press Enter to confirm.",
                id="workspace-hint",
            )
            yield _WorkspaceInput(
                value=str(self._default_workspace),
                placeholder="1",
                id="workspace-input",
            )

    def on_mount(self) -> None:
        """Focus the input on mount and select all."""
        workspace_input = self.query_one("#workspace-input", _WorkspaceInput)
        workspace_input.focus()
        workspace_input.action_select_all()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        value = event.value.strip()
        if not value:
            # Use default if empty
            self.dismiss(self._default_workspace)
            return

        try:
            workspace_num = int(value)
            if 1 <= workspace_num <= 9:
                self.dismiss(workspace_num)
            else:
                self.notify("Workspace must be between 1 and 9", severity="error")
        except ValueError:
            self.notify("Please enter a valid number", severity="error")

    def action_cancel(self) -> None:
        """Cancel the modal."""
        self.dismiss(None)
