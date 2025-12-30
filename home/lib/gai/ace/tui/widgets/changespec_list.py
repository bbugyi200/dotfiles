"""ChangeSpec list widget for the ace TUI."""

from typing import Any

from rich.text import Text
from textual.message import Message
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from ...changespec import ChangeSpec, has_ready_to_mail_suffix
from ...comments import is_timestamp_suffix


def _has_running_agent(changespec: ChangeSpec) -> bool:
    """Check if ChangeSpec has any running agents (CRS or fix-hook).

    Returns:
        True if running agents are detected, False otherwise.
    """
    # Check COMMENTS for timestamp suffix (CRS running)
    if changespec.comments:
        for comment in changespec.comments:
            if comment.suffix and is_timestamp_suffix(comment.suffix):
                return True
    # Check HOOKS for RUNNING status
    if changespec.hooks:
        for hook in changespec.hooks:
            if hook.status_lines:
                for sl in hook.status_lines:
                    if sl.status == "RUNNING":
                        return True
    return False


def _get_status_indicator(changespec: ChangeSpec) -> tuple[str, str]:
    """Get a status indicator symbol and color for a ChangeSpec.

    Returns:
        Tuple of (symbol, color)
    """
    status = changespec.status
    has_running = _has_running_agent(changespec)
    has_error = " - (!: " in status

    # Build prefix components
    error_prefix = "!" if has_error else ""
    running_prefix = "@" if has_running else ""

    # Check for error suffixes in status (with status-specific suffix)
    if has_error:
        if status.startswith("Drafted"):
            return f"{error_prefix}{running_prefix}D", "#FF5F5F"  # Red for errors
        elif status.startswith("Mailed"):
            return f"{error_prefix}{running_prefix}M", "#FF5F5F"  # Red for errors
        return f"{error_prefix}{running_prefix}", "#FF5F5F"  # Red for errors

    # Check for READY TO MAIL
    if has_ready_to_mail_suffix(status):
        return f"{running_prefix}*", "#00D787"  # Cyan-green for ready to mail

    # Status-based indicators
    if "..." in status:
        return f"{running_prefix}~", "#87AFFF"  # Blue for in-progress
    elif status.startswith("Drafted"):
        return f"{running_prefix}D", "#87D700"  # Green
    elif status.startswith("Mailed"):
        return f"{running_prefix}M", "#00D787"  # Cyan-green
    elif status.startswith("Submitted"):
        return f"{running_prefix}S", "#00AF00"  # Dark green
    elif status.startswith("Reverted"):
        return f"{running_prefix}X", "#808080"  # Gray

    return running_prefix or " ", "#FFFFFF"  # Default


class ChangeSpecList(OptionList):
    """Left sidebar showing list of ChangeSpecs."""

    class SelectionChanged(Message):
        """Message sent when selection changes."""

        def __init__(self, index: int) -> None:
            self.index = index
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

        for i, cs in enumerate(changespecs):
            option = self._format_changespec_option(cs, is_selected=(i == current_idx))
            self.add_option(option)

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
        text.append(f"[{indicator}] ", style=f"bold {color}")

        # Name
        name_style = "bold #00D7AF" if is_selected else "#00D7AF"
        text.append(changespec.name, style=name_style)

        # CL number if present
        if changespec.cl:
            text.append(f" ({changespec.cl})", style="#5FD7FF dim")

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
