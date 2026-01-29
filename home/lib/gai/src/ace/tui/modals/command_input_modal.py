"""Command input modal for the ace TUI."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Input, Label


class _CommandInput(Input):
    """Custom Input with readline-style key bindings."""

    BINDINGS = [
        ("ctrl+f", "cursor_right", "Forward"),
        ("ctrl+b", "cursor_left", "Backward"),
        ("ctrl+a", "home", "Home"),
        ("ctrl+e", "end", "End"),
    ]


class CommandInputModal(ModalScreen[str | None]):
    """Modal for entering a shell command."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self, project: str, workspace_num: int, cl_name: str | None = None
    ) -> None:
        """Initialize the command input modal.

        Args:
            project: Project name for display.
            workspace_num: Workspace number for display.
            cl_name: Optional CL name for display.
        """
        super().__init__()
        self._project = project
        self._workspace_num = workspace_num
        self._cl_name = cl_name

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container():
            yield Label("Enter Command", id="modal-title")
            # Build context line
            context = f"Project: {self._project}"
            if self._cl_name:
                context += f" | CL: {self._cl_name}"
            context += f" | Workspace: {self._workspace_num}"
            yield Label(context, id="command-context")
            yield Label(
                "Enter shell command to run in background. Press Enter to start.",
                id="command-hint",
            )
            yield _CommandInput(
                placeholder="e.g., make test",
                id="command-input",
            )

    def on_mount(self) -> None:
        """Focus the input on mount."""
        command_input = self.query_one("#command-input", _CommandInput)
        command_input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        command = event.value.strip()
        if command:
            self.dismiss(command)
        else:
            self.notify("Please enter a command", severity="error")

    def action_cancel(self) -> None:
        """Cancel the modal."""
        self.dismiss(None)
