"""Status selection modal for the ace TUI."""

import os
import sys

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)

from ace.status import get_available_statuses

from .base import OptionListNavigationMixin


class StatusModal(OptionListNavigationMixin, ModalScreen[str | None]):
    """Modal for selecting a new status."""

    _option_list_id = "status-list"
    BINDINGS = [*OptionListNavigationMixin.NAVIGATION_BINDINGS]

    def __init__(self, current_status: str) -> None:
        """Initialize the status modal.

        Args:
            current_status: The current status value
        """
        super().__init__()
        self.current_status = current_status
        self.available_statuses = get_available_statuses(current_status)

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container():
            yield Label("Select New Status", id="modal-title")
            yield OptionList(
                *[Option(status, id=status) for status in self.available_statuses],
                id="status-list",
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection."""
        if event.option and event.option.id:
            self.dismiss(str(event.option.id))
