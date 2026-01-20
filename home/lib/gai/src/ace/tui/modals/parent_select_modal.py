"""Parent selection modal for the ace TUI rebase feature."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from .base import OptionListNavigationMixin


class ParentSelectModal(OptionListNavigationMixin, ModalScreen[str | None]):
    """Modal for selecting a new parent ChangeSpec for rebasing."""

    _option_list_id = "parent-list"
    BINDINGS = [*OptionListNavigationMixin.NAVIGATION_BINDINGS]

    def __init__(self, available_parents: list[tuple[str, str]]) -> None:
        """Initialize the parent selection modal.

        Args:
            available_parents: List of (name, status) tuples for eligible parents
        """
        super().__init__()
        self.available_parents = available_parents

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container():
            yield Label("Select New Parent", id="modal-title")
            yield OptionList(
                *[
                    Option(f"{name} ({status})", id=name)
                    for name, status in self.available_parents
                ],
                id="parent-list",
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection."""
        if event.option and event.option.id:
            self.dismiss(event.option.id)
