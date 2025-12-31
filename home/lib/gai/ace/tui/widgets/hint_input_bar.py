"""Hint input bar widget for the ace TUI."""

from typing import Any, Literal

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Input, Label, Static


class _HintInput(Input):
    """Custom Input with readline-style key bindings."""

    BINDINGS = [
        ("ctrl+f", "cursor_right", "Forward"),
        ("ctrl+b", "cursor_left", "Backward"),
    ]


class HintInputBar(Static):
    """Small input bar for hint selection, positioned below ChangeSpec panel."""

    class Submitted(Message):
        """Message sent when hint input is submitted."""

        def __init__(self, value: str, mode: Literal["view", "hooks"]) -> None:
            """Initialize the message.

            Args:
                value: The input value
                mode: The current hint mode ("view" or "hooks")
            """
            super().__init__()
            self.value = value
            self.mode = mode

    class Cancelled(Message):
        """Message sent when hint input is cancelled."""

        pass

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, mode: Literal["view", "hooks"], **kwargs: Any) -> None:
        """Initialize the hint input bar.

        Args:
            mode: The current hint mode ("view" or "hooks")
            **kwargs: Additional arguments for Static
        """
        super().__init__(**kwargs)
        self.mode = mode

    def compose(self) -> ComposeResult:
        """Compose the input bar layout."""
        with Horizontal(id="hint-input-container"):
            if self.mode == "view":
                yield Label("View: ", id="hint-label")
                yield _HintInput(
                    placeholder="1 2 3@ (@ to open in $EDITOR)", id="hint-input"
                )
            else:
                yield Label("Hooks: ", id="hint-label")
                yield _HintInput(
                    placeholder="1 2@ (@ to delete) or //target or command",
                    id="hint-input",
                )
            yield Label("[Esc] cancel", id="hint-escape-hint", classes="dim-label")

    def on_mount(self) -> None:
        """Focus the input on mount."""
        hint_input = self.query_one("#hint-input", _HintInput)
        hint_input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        self.post_message(self.Submitted(event.value.strip(), self.mode))

    def action_cancel(self) -> None:
        """Cancel the input bar."""
        self.post_message(self.Cancelled())

    def _build_prompt_text(self) -> Text:
        """Build the prompt text."""
        text = Text()
        if self.mode == "view":
            text.append("View: ", style="bold #87D7FF")
        else:
            text.append("Hooks: ", style="bold #87D7FF")
        return text
