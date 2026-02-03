"""Base classes and mixins for ace TUI modals."""

from textual import events
from textual.widgets import Input, OptionList


class CopyModeForwardingMixin:
    """Mixin that forwards copy-mode keys (%) to the app.

    This allows the %s (and other %) copy shortcuts to work even when
    a modal is open.
    """

    def on_key(self, event: events.Key) -> None:
        """Forward copy-mode keys to the app."""
        from ..app import AceApp

        app = self.app  # type: ignore[attr-defined]
        if not isinstance(app, AceApp):
            return

        # If % is pressed, start copy mode
        if event.key == "percent_sign":
            app.action_start_copy_mode()
            event.prevent_default()
            event.stop()
            return

        # If copy mode is active, forward the key
        if app._copy_mode_active:
            if app._handle_copy_key(event.key):
                event.prevent_default()
                event.stop()


class FilterInput(Input):
    """Input widget with readline-style key bindings for modal filtering."""

    BINDINGS = [
        ("ctrl+f", "cursor_right", "Forward"),
        ("ctrl+b", "cursor_left", "Backward"),
    ]


class OptionListNavigationMixin:
    """Mixin providing vim-style navigation bindings for modals with OptionList.

    Subclasses must define `_option_list_id` as a class attribute containing
    the DOM ID of the OptionList widget (without the '#' prefix).

    Example:
        class MyModal(OptionListNavigationMixin, ModalScreen[str | None]):
            _option_list_id = "my-list"
            BINDINGS = [*OptionListNavigationMixin.NAVIGATION_BINDINGS]
    """

    _option_list_id: str

    NAVIGATION_BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("q", "cancel", "Cancel"),
        ("j", "next_option", "Next"),
        ("k", "prev_option", "Previous"),
        ("down", "next_option", "Next"),
        ("up", "prev_option", "Previous"),
        ("ctrl+n", "next_option", "Next"),
        ("ctrl+p", "prev_option", "Previous"),
    ]

    def action_cancel(self) -> None:
        """Cancel the modal."""
        self.dismiss(None)  # type: ignore[attr-defined]

    def action_next_option(self) -> None:
        """Move to next option in the list."""
        self.query_one(f"#{self._option_list_id}", OptionList).action_cursor_down()  # type: ignore[attr-defined]

    def action_prev_option(self) -> None:
        """Move to previous option in the list."""
        self.query_one(f"#{self._option_list_id}", OptionList).action_cursor_up()  # type: ignore[attr-defined]
