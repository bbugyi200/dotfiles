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

# Mapping of bright colors to dimmer variants for selected items
_DIM_COLOR_MAP: dict[str, str] = {
    "#FF5F5F": "#B03030",  # Red
    "#FFAF00": "#B07800",  # Orange
    "#FFD700": "#B09800",  # Yellow
    "#00D787": "#008060",  # Cyan-green
    "#87D700": "#609000",  # Green
    "#00AF00": "#007800",  # Dark green
    "#87AFFF": "#5070B0",  # Blue
    "#808080": "#505050",  # Gray
    "#00D7AF": "#008878",  # Teal (for name)
    "#5FD7FF": "#3A8FB7",  # Light cyan (for CL)
    "#FFFFFF": "#C0C0C0",  # White
}


def _get_dim_color(color: str) -> str:
    """Get a dimmer variant of a color for selected items.

    Args:
        color: The bright color hex code (e.g., "#FF5F5F")

    Returns:
        The dimmer color hex code, or the original if no mapping exists
    """
    return _DIM_COLOR_MAP.get(color.upper(), color)


def _calculate_entry_display_width(changespec: ChangeSpec) -> int:
    """Calculate display width of a ChangeSpec entry in terminal cells.

    Args:
        changespec: The ChangeSpec to measure

    Returns:
        Width in terminal cells
    """
    indicator, _ = _get_status_indicator(changespec)
    # Format: "[{indicator}] {name} ({cl})"
    parts = [f"[{indicator}] ", changespec.name]
    if changespec.cl:
        parts.append(f" ({changespec.cl})")
    text = Text("".join(parts))
    return text.cell_len


def _get_status_indicator(changespec: ChangeSpec) -> tuple[str, str]:
    """Get a status indicator symbol and color for a ChangeSpec.

    Color priority: error (red) > running_agent (orange) > running_process (yellow) > status-based

    Returns:
        Tuple of (symbol, color)
    """
    status = changespec.status
    has_running = has_any_running_agent(changespec)
    has_process = has_any_running_process(changespec)
    has_error = has_any_error_suffix(changespec)

    # Build prefix components
    error_prefix = "!" if has_error else ""
    running_prefix = "@" if has_running else ""
    process_prefix = "$" if has_process else ""

    # Check for error suffixes in HISTORY/HOOKS/COMMENTS (with status-specific suffix)
    # Red takes priority over orange/yellow
    if has_error:
        if status.startswith("Drafted"):
            return f"{error_prefix}{running_prefix}{process_prefix}D", "#FF5F5F"
        elif status.startswith("Mailed"):
            return f"{error_prefix}{running_prefix}{process_prefix}M", "#FF5F5F"
        return f"{error_prefix}{running_prefix}{process_prefix}", "#FF5F5F"

    # Running agents get orange color (when no error)
    if has_running:
        if has_ready_to_mail_suffix(status):
            return f"{running_prefix}{process_prefix}*", "#FFAF00"
        if "..." in status:
            return f"{running_prefix}{process_prefix}~", "#FFAF00"
        elif status.startswith("Drafted"):
            return f"{running_prefix}{process_prefix}D", "#FFAF00"
        elif status.startswith("Mailed"):
            return f"{running_prefix}{process_prefix}M", "#FFAF00"
        elif status.startswith("Submitted"):
            return f"{running_prefix}{process_prefix}S", "#FFAF00"
        elif status.startswith("Reverted"):
            return f"{running_prefix}{process_prefix}X", "#FFAF00"
        return f"{running_prefix}{process_prefix}", "#FFAF00"

    # Running processes get yellow color (when no error, no running_agent)
    if has_process:
        if has_ready_to_mail_suffix(status):
            return f"{process_prefix}*", "#FFD700"  # Yellow for running process
        if "..." in status:
            return f"{process_prefix}~", "#FFD700"  # Yellow for running process
        elif status.startswith("Drafted"):
            return f"{process_prefix}D", "#FFD700"  # Yellow for running process
        elif status.startswith("Mailed"):
            return f"{process_prefix}M", "#FFD700"  # Yellow for running process
        elif status.startswith("Submitted"):
            return f"{process_prefix}S", "#FFD700"  # Yellow for running process
        elif status.startswith("Reverted"):
            return f"{process_prefix}X", "#FFD700"  # Yellow for running process
        return process_prefix, "#FFD700"  # Yellow for running process

    # Check for READY TO MAIL (no running, no error)
    if has_ready_to_mail_suffix(status):
        return "*", "#00D787"  # Cyan-green for ready to mail

    # Status-based indicators (no running, no error)
    if "..." in status:
        return "~", "#87AFFF"  # Blue for in-progress
    elif status.startswith("Drafted"):
        return "D", "#87D700"  # Green
    elif status.startswith("Mailed"):
        return "M", "#00D787"  # Cyan-green
    elif status.startswith("Submitted"):
        return "S", "#00AF00"  # Dark green
    elif status.startswith("Reverted"):
        return "X", "#808080"  # Gray

    return " ", "#FFFFFF"  # Default


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

    def update_list(self, changespecs: list[ChangeSpec], current_idx: int) -> None:
        """Update the list with new changespecs.

        Args:
            changespecs: List of ChangeSpecs to display
            current_idx: Index of currently selected ChangeSpec
        """
        self._changespecs = changespecs
        self.clear_options()

        max_width = 0
        for i, cs in enumerate(changespecs):
            option = self._format_changespec_option(cs, is_selected=(i == current_idx))
            self.add_option(option)
            width = _calculate_entry_display_width(cs)
            max_width = max(max_width, width)

        # Add padding for border, scrollbar, visual comfort (~8 cells)
        _PADDING = 8
        optimal_width = max_width + _PADDING
        self.post_message(self.WidthChanged(optimal_width))

        # Highlight the current item
        if changespecs and 0 <= current_idx < len(changespecs):
            self.highlighted = current_idx

    def _format_changespec_option(
        self, changespec: ChangeSpec, is_selected: bool
    ) -> Option:
        """Format a ChangeSpec as an option for display.

        Args:
            changespec: The ChangeSpec to format
            is_selected: Whether this is the currently selected item

        Returns:
            An Option for the OptionList
        """
        text = Text()

        # Status indicator
        indicator, color = _get_status_indicator(changespec)
        if is_selected:
            color = _get_dim_color(color)
        text.append(f"[{indicator}] ", style=f"bold {color}")

        # Name - use dimmer color when selected for better readability
        if is_selected:
            name_style = f"bold {_get_dim_color('#00D7AF')}"
        else:
            name_style = "#00D7AF"
        text.append(changespec.name, style=name_style)

        # CL number if present - use dimmer color when selected
        if changespec.cl:
            if is_selected:
                cl_style = _get_dim_color("#5FD7FF")
            else:
                cl_style = "#5FD7FF dim"
            text.append(f" ({changespec.cl})", style=cl_style)

        return Option(text, id=changespec.name)

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Handle option highlight (keyboard navigation)."""
        if event.option_index is not None:
            self.post_message(self.SelectionChanged(event.option_index))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection (mouse click or Enter)."""
        if event.option_index is not None:
            self.post_message(self.SelectionChanged(event.option_index))
