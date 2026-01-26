"""Hint input bar widget for the ace TUI."""

from typing import TYPE_CHECKING, Any, Literal

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Input, Label, Static

if TYPE_CHECKING:
    from ..app import AceApp


class _HintInput(Input):
    """Custom Input with readline-style key bindings."""

    BINDINGS = [
        ("ctrl+f", "cursor_right", "Forward"),
        ("ctrl+b", "cursor_left", "Backward"),
        ("ctrl+d", "scroll_detail_down", "Scroll Down"),
        ("ctrl+u", "unix_line_discard", "Clear to start"),
        ("ctrl+e", "end_or_fill_placeholder", "End/Fill"),
    ]

    @property
    def _ace_app(self) -> "AceApp":
        """Get the app as AceApp type."""
        from ..app import AceApp

        assert isinstance(self.app, AceApp)
        return self.app

    def action_scroll_detail_down(self) -> None:
        """Delegate to app's scroll down action."""
        self._ace_app.action_scroll_detail_down()

    def action_unix_line_discard(self) -> None:
        """Scroll detail panel up, or clear line if already at top."""
        from textual.containers import VerticalScroll

        # Check if we can scroll up in the detail panel
        if self._ace_app.current_tab == "changespecs":
            scroll_container = self._ace_app.query_one("#detail-scroll", VerticalScroll)
            if scroll_container.scroll_y > 0:
                self._ace_app.action_scroll_detail_up()
                return

        # At the top (or not on changespecs tab) - clear line
        if self.cursor_position > 0:
            self.value = self.value[self.cursor_position :]
            self.cursor_position = 0

    def action_end_or_fill_placeholder(self) -> None:
        """Fill placeholder if input is empty, otherwise move cursor to end."""
        if not self.value and self.placeholder:
            # Input is empty - fill in the placeholder text
            self.value = self.placeholder
            self.cursor_position = len(self.value)
        else:
            # Input has content - move cursor to end (default Ctrl+e behavior)
            self.action_end()


class HintInputBar(Static):
    """Small input bar for hint selection, positioned below ChangeSpec panel."""

    class Submitted(Message):
        """Message sent when hint input is submitted."""

        def __init__(
            self,
            value: str,
            mode: Literal["view", "hooks", "accept", "failed_hooks", "rewind"],
        ) -> None:
            """Initialize the message.

            Args:
                value: The input value
                mode: The current hint mode ("view", "hooks", "accept", or "failed_hooks")
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

    def __init__(
        self,
        mode: Literal["view", "hooks", "accept", "failed_hooks", "rewind"],
        placeholder: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the hint input bar.

        Args:
            mode: The current hint mode ("view", "hooks", "accept", "failed_hooks", or "rewind")
            placeholder: Optional custom placeholder text (used for "accept" and "rewind" modes)
            **kwargs: Additional arguments for Static
        """
        super().__init__(**kwargs)
        self.mode = mode
        self._custom_placeholder = placeholder

    def compose(self) -> ComposeResult:
        """Compose the input bar layout."""
        with Horizontal(id="hint-input-container"):
            if self.mode == "view":
                yield Label("View: ", id="hint-label")
                yield _HintInput(
                    placeholder="1-5 or 3@ (@ to edit) or 3% (% to copy path)",
                    id="hint-input",
                )
            elif self.mode == "hooks":
                yield Label("Hooks: ", id="hint-label")
                yield _HintInput(
                    placeholder="1-5 or 2@ (@ to delete) or //target or command",
                    id="hint-input",
                )
            elif self.mode == "failed_hooks":
                yield Label("Failed Hooks: ", id="hint-label")
                yield _HintInput(
                    placeholder="1-5 or 1 3 5 (select targets to add as hooks)",
                    id="hint-input",
                )
            elif self.mode == "rewind":
                yield Label("Rewind: ", id="hint-label")
                placeholder = self._custom_placeholder or ""
                yield _HintInput(placeholder=placeholder, id="hint-input")
            else:  # accept mode
                yield Label("Accept: ", id="hint-label")
                placeholder = self._custom_placeholder or ""
                yield _HintInput(placeholder=placeholder, id="hint-input")
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
        elif self.mode == "failed_hooks":
            text.append("Failed Hooks: ", style="bold #87D7FF")
        else:
            text.append("Hooks: ", style="bold #87D7FF")
        return text
