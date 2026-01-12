"""Prompt input bar widget for agent workflow in the ace TUI."""

from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Input, Label, Static

if TYPE_CHECKING:
    from ..app import AceApp


class _PromptInput(Input):
    """Custom Input with readline-style key bindings and special handlers."""

    BINDINGS = [
        ("ctrl+f", "cursor_right", "Forward"),
        ("ctrl+b", "cursor_left", "Backward"),
        ("ctrl+g", "open_editor", "Edit in editor"),
        ("ctrl+u", "unix_line_discard", "Clear to start"),
        ("ctrl+e", "end", "End of line"),
    ]

    @property
    def _ace_app(self) -> "AceApp":
        """Get the app as AceApp type."""
        from ..app import AceApp

        assert isinstance(self.app, AceApp)
        return self.app

    def action_unix_line_discard(self) -> None:
        """Clear from cursor to beginning of line."""
        if self.cursor_position > 0:
            self.value = self.value[self.cursor_position :]
            self.cursor_position = 0

    def action_open_editor(self) -> None:
        """Request to open external editor."""
        # Find parent PromptInputBar and post message
        parent = self.parent
        while parent is not None:
            if isinstance(parent, PromptInputBar):
                parent.post_message(PromptInputBar.EditorRequested())
                return
            parent = parent.parent


class PromptInputBar(Static):
    """Prompt input bar for agent workflow, positioned at bottom of screen."""

    class Submitted(Message):
        """Message sent when prompt is submitted."""

        def __init__(self, value: str) -> None:
            """Initialize the message.

            Args:
                value: The prompt value
            """
            super().__init__()
            self.value = value

    class Cancelled(Message):
        """Message sent when input is cancelled."""

        pass

    class EditorRequested(Message):
        """Message sent when user requests external editor (Ctrl+G)."""

        pass

    class HistoryRequested(Message):
        """Message sent when user requests prompt history picker ('.')."""

        pass

    class SnippetRequested(Message):
        """Message sent when user requests snippet modal ('#')."""

        pass

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the prompt input bar.

        Args:
            **kwargs: Additional arguments for Static
        """
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Compose the input bar layout."""
        with Horizontal(id="prompt-input-container"):
            yield Label("Prompt: ", id="prompt-label")
            yield _PromptInput(
                placeholder="Type prompt, '.' for history, '#' for snippets [^G] editor",
                id="prompt-input",
            )
            yield Label("[Esc] cancel", id="prompt-escape-hint", classes="dim-label")

    def on_mount(self) -> None:
        """Focus the input on mount."""
        prompt_input = self.query_one("#prompt-input", _PromptInput)
        prompt_input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        value = event.value.strip()

        # Check for '.' - trigger history picker
        if value == ".":
            self.post_message(self.HistoryRequested())
            return

        # Normal submission
        self.post_message(self.Submitted(value))

    def on_key(self, event: Any) -> None:
        """Handle key events for special triggers."""
        # Check for '#' key to trigger snippet modal
        if event.key == "numbersign" or event.character == "#":
            # Only trigger if this is a fresh '#' press, not part of existing input
            prompt_input = self.query_one("#prompt-input", _PromptInput)
            if prompt_input.has_focus:
                # Post message to open snippet modal
                self.post_message(self.SnippetRequested())
                # Don't stop the event - let '#' be typed into the input

    def action_cancel(self) -> None:
        """Cancel the input bar."""
        self.post_message(self.Cancelled())

    def insert_snippet(self, snippet_name: str) -> None:
        """Insert a snippet reference at the cursor position.

        Args:
            snippet_name: The snippet name to insert (without #)
        """
        prompt_input = self.query_one("#prompt-input", _PromptInput)
        # The '#' was already typed, so just insert the snippet name
        current_value = prompt_input.value
        cursor_pos = prompt_input.cursor_position
        new_value = (
            current_value[:cursor_pos] + snippet_name + current_value[cursor_pos:]
        )
        prompt_input.value = new_value
        prompt_input.cursor_position = cursor_pos + len(snippet_name)
        prompt_input.focus()
