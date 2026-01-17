"""Background command list widget for the ace TUI.

Shows a list of running commands (axe + background commands) when
background commands are present.
"""

from typing import Any, Literal

from rich.text import Text
from textual.message import Message
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from ..bgcmd import BackgroundCommandInfo

# Item type: "axe" or slot number (1-9)
ItemType = Literal["axe"] | int


class BgCmdList(OptionList):
    """Left sidebar showing list of running commands."""

    class SelectionChanged(Message):
        """Message sent when selection changes."""

        def __init__(self, item: ItemType) -> None:
            self.item = item
            super().__init__()

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the background command list."""
        super().__init__(**kwargs)
        self._items: list[ItemType] = []
        self._axe_running: bool = False
        self._bgcmd_infos: dict[int, BackgroundCommandInfo] = {}
        self._programmatic_update: bool = False

    def update_list(
        self,
        axe_running: bool,
        bgcmd_slots: list[tuple[int, BackgroundCommandInfo]],
        current_item: ItemType,
    ) -> None:
        """Update the list with current running commands.

        Args:
            axe_running: Whether axe daemon is running.
            bgcmd_slots: List of (slot, info) tuples for running background commands.
            current_item: Currently selected item ("axe" or slot number).
        """
        self._programmatic_update = True
        try:
            self._axe_running = axe_running
            self._items = []
            self._bgcmd_infos = {}

            self.clear_options()

            # Always show axe first
            self._items.append("axe")
            option = self._format_axe_option(
                is_running=axe_running,
                is_selected=(current_item == "axe"),
            )
            self.add_option(option)

            # Add background commands
            for slot, info in sorted(bgcmd_slots, key=lambda x: x[0]):
                self._items.append(slot)
                self._bgcmd_infos[slot] = info
                option = self._format_bgcmd_option(
                    slot=slot,
                    info=info,
                    is_selected=(current_item == slot),
                )
                self.add_option(option)

            # Highlight the current item
            if current_item in self._items:
                idx = self._items.index(current_item)
                self.highlighted = idx
            else:
                self.highlighted = 0  # Default to axe
        finally:
            self._programmatic_update = False

    def _format_axe_option(self, is_running: bool, is_selected: bool) -> Option:
        """Format the axe option for display.

        Args:
            is_running: Whether axe daemon is running.
            is_selected: Whether this is the currently selected item.

        Returns:
            An Option for the OptionList.
        """
        text = Text()

        # Status indicator
        if is_running:
            text.append("[", style="dim")
            text.append("*", style="bold green")
            text.append("] ", style="dim")
        else:
            text.append("[ ] ", style="dim")

        # Label
        label_style = "bold #FFD700" if is_selected else "#FFD700"
        text.append("gai axe", style=label_style)

        return Option(text, id="axe")

    def _format_bgcmd_option(
        self, slot: int, info: BackgroundCommandInfo, is_selected: bool
    ) -> Option:
        """Format a background command option for display.

        Args:
            slot: Slot number (1-9).
            info: Background command information.
            is_selected: Whether this is the currently selected item.

        Returns:
            An Option for the OptionList.
        """
        text = Text()

        # Status indicator (always running if in list)
        text.append("[", style="dim")
        text.append("*", style="bold #00D7AF")
        text.append("] ", style="dim")

        # Slot number
        text.append(f"{slot}: ", style="bold #87D7FF")

        # Command (truncated)
        cmd_display = info.command
        if len(cmd_display) > 25:
            cmd_display = cmd_display[:22] + "..."
        label_style = "bold #00D7AF" if is_selected else "#00D7AF"
        text.append(cmd_display, style=label_style)

        return Option(text, id=str(slot))

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Handle option highlight (keyboard navigation)."""
        if self._programmatic_update:
            return
        if event.option_index is not None and 0 <= event.option_index < len(
            self._items
        ):
            self.post_message(self.SelectionChanged(self._items[event.option_index]))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection (mouse click or Enter)."""
        if event.option_index is not None and 0 <= event.option_index < len(
            self._items
        ):
            self.post_message(self.SelectionChanged(self._items[event.option_index]))
