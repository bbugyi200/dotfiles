"""ChangeSpec list widget for the ace TUI."""

from typing import Any

from rich.text import Text
from textual.message import Message
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from ...changespec import (
    ChangeSpec,
    has_any_error_suffix,
    has_any_running_agent,
    has_any_running_process,
    has_ready_to_mail_suffix,
)

_PREFIX_CHAR_COLORS: dict[str, str] = {
    "!": "#FF5F5F",  # Red for error
    "@": "#FFAF00",  # Orange for running agent
    "$": "#D7AF00",  # Darker yellow for running process
}


def _calculate_entry_display_width(changespec: ChangeSpec, is_marked: bool) -> int:
    """Calculate display width of a ChangeSpec entry in terminal cells.

    Args:
        changespec: The ChangeSpec to measure
        is_marked: Whether this ChangeSpec is marked

    Returns:
        Width in terminal cells
    """
    indicator, _ = _get_status_indicator(changespec)
    # Format: "[✓] [{indicator}] {name} ({cl})" (with mark prefix if marked)
    parts = []
    if is_marked:
        parts.append("[✓] ")
    parts.append(f"[{indicator}] ")
    parts.append(changespec.name)
    if changespec.cl:
        parts.append(f" ({changespec.cl})")
    text = Text("".join(parts))
    return text.cell_len


def _get_status_letter_and_color(
    status: str, *, has_ready_to_mail: bool
) -> tuple[str, str]:
    """Map a status string to its letter and natural color.

    Args:
        status: The ChangeSpec status string
        has_ready_to_mail: Whether the status has a ready-to-mail suffix

    Returns:
        Tuple of (letter, color)
    """
    if has_ready_to_mail:
        return "*", "#00D787"
    if "..." in status:
        return "~", "#87AFFF"
    elif status.startswith("Drafted"):
        return "D", "#87D700"
    elif status.startswith("Mailed"):
        return "M", "#00D787"
    elif status.startswith("Submitted"):
        return "S", "#00AF00"
    elif status.startswith("Reverted"):
        return "X", "#808080"
    elif status.startswith("Archived"):
        return "A", "#606060"
    return "W", "#FFD700"


def _get_status_indicator(changespec: ChangeSpec) -> tuple[str, str]:
    """Get a status indicator symbol and letter color for a ChangeSpec.

    Returns:
        Tuple of (indicator, letter_color)
    """
    status = changespec.status
    has_running = has_any_running_agent(changespec)
    has_process = has_any_running_process(changespec)
    has_error = has_any_error_suffix(changespec)
    ready_to_mail = has_ready_to_mail_suffix(status)

    letter, letter_color = _get_status_letter_and_color(
        status, has_ready_to_mail=ready_to_mail
    )

    # Build prefix components
    error_prefix = "!" if has_error else ""
    running_prefix = "@" if has_running else ""
    process_prefix = "$" if has_process else ""
    indicator = f"{error_prefix}{running_prefix}{process_prefix}{letter}"

    return indicator, letter_color


class ChangeSpecList(OptionList):
    """Left sidebar showing list of ChangeSpecs."""

    class SelectionChanged(Message):
        """Message sent when selection changes."""

        def __init__(self, index: int) -> None:
            self.index = index
            super().__init__()

    class WidthChanged(Message):
        """Message sent when optimal width changes."""

        def __init__(self, width: int) -> None:
            self.width = width
            super().__init__()

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the ChangeSpec list."""
        super().__init__(**kwargs)
        self._changespecs: list[ChangeSpec] = []
        self._marked_indices: set[int] = set()
        self._programmatic_update: bool = False

    def update_list(
        self,
        changespecs: list[ChangeSpec],
        current_idx: int,
        marked_indices: set[int] | None = None,
    ) -> None:
        """Update the list with new changespecs.

        Args:
            changespecs: List of ChangeSpecs to display
            current_idx: Index of currently selected ChangeSpec
            marked_indices: Set of indices that are marked
        """
        self._programmatic_update = True
        self._marked_indices = marked_indices or set()
        self._changespecs = changespecs
        self.clear_options()

        max_width = 0
        for i, cs in enumerate(changespecs):
            is_marked = i in self._marked_indices
            option = self._format_changespec_option(
                cs, is_selected=(i == current_idx), is_marked=is_marked
            )
            self.add_option(option)
            width = _calculate_entry_display_width(cs, is_marked=is_marked)
            max_width = max(max_width, width)

        # Add padding for border, scrollbar, visual comfort (~8 cells)
        _PADDING = 8
        optimal_width = max_width + _PADDING
        self.post_message(self.WidthChanged(optimal_width))

        # Highlight the current item
        if changespecs and 0 <= current_idx < len(changespecs):
            self.highlighted = current_idx

        # Clear flag after event loop processes pending events
        self.call_later(self._clear_programmatic_flag)

    def _clear_programmatic_flag(self) -> None:
        """Clear programmatic update flag after event processing."""
        self._programmatic_update = False

    def _format_changespec_option(
        self, changespec: ChangeSpec, is_selected: bool, is_marked: bool
    ) -> Option:
        """Format a ChangeSpec as an option for display.

        Args:
            changespec: The ChangeSpec to format
            is_selected: Whether this is the currently selected item
            is_marked: Whether this item is marked

        Returns:
            An Option for the OptionList
        """
        text = Text()

        # Mark indicator (green checkmark)
        if is_marked:
            text.append("[✓] ", style="bold #00D700")

        # Status indicator
        indicator, letter_color = _get_status_indicator(changespec)
        text.append("[", style=f"bold {letter_color}")
        for ch in indicator:
            text.append(ch, style=f"bold {_PREFIX_CHAR_COLORS.get(ch, letter_color)}")
        text.append("] ", style=f"bold {letter_color}")

        # Name
        name_style = "bold #00D7AF" if is_selected else "#00D7AF"
        text.append(changespec.name, style=name_style)

        # CL number if present
        if changespec.cl:
            text.append(f" ({changespec.cl})", style="#569CD6 dim")

        return Option(text, id=changespec.name)

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Handle option highlight (keyboard navigation)."""
        if self._programmatic_update:
            return  # Skip events from programmatic updates
        if event.option_index is not None:
            self.post_message(self.SelectionChanged(event.option_index))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection (mouse click or Enter)."""
        if event.option_index is not None:
            self.post_message(self.SelectionChanged(event.option_index))
