"""Query history and saved queries section builders for the help modal."""

from rich.text import Text

from ....query_history import load_query_history
from ....saved_queries import KEY_ORDER, load_saved_queries
from ...widgets.changespec_detail import build_query_text
from .bindings import CONTENT_WIDTH


def add_saved_queries_section(
    text: Text,
    active_query: str | None,
    content_width: int = CONTENT_WIDTH,
) -> None:
    """Add the saved queries section (CLs tab only).

    Args:
        text: The Text object to append to.
        active_query: The current active query string for highlighting.
        content_width: The content width for formatting.
    """
    queries = load_saved_queries()

    # Section header
    text.append("\n")
    text.append("  \u250c\u2500 ", style="dim #FFD700")
    text.append("Saved Queries", style="bold #FFD700")
    text.append(" ", style="")
    remaining = 50 - len("Saved Queries")
    text.append("\u2500" * remaining + "\u2510", style="dim #FFD700")
    text.append("\n")

    if not queries:
        text.append("  \u2502  ", style="dim #FFD700")
        text.append("No saved queries", style="dim italic")
        text.append(" " * 34, style="")
        text.append(" \u2502", style="dim #FFD700")
        text.append("\n")
    else:
        # Calculate max query lengths:
        # Content area after [slot] and spacing: content_width - 5 = 45 chars
        # Active indicator " ● active": 9 chars
        slot_prefix_width = 5  # "[0]" (3) + "  " (2)
        active_indicator_width = 9  # " ● active"
        max_query_active = content_width - slot_prefix_width - active_indicator_width
        max_query_inactive = content_width - slot_prefix_width

        for slot in KEY_ORDER:
            if slot in queries:
                query = queries[slot]
                is_active = active_query is not None and query == active_query

                text.append("  \u2502  ", style="dim #FFD700")

                # Slot number with styling
                slot_style = "bold #00FF00" if is_active else "#3CB371"
                text.append(f"[{slot}]", style=slot_style)
                text.append("  ", style="")

                # Query with syntax highlighting (truncated if needed)
                max_query_len = max_query_active if is_active else max_query_inactive
                if len(query) > max_query_len:
                    display_query = query[: max_query_len - 3] + "..."
                else:
                    display_query = query

                text.append_text(build_query_text(display_query))

                # Active indicator and padding
                if is_active:
                    padding = max_query_len - len(display_query)
                    if padding > 0:
                        text.append(" " * padding, style="")
                    text.append(" \u25cf active", style="bold #00FF00")
                else:
                    padding = max_query_len - len(display_query)
                    if padding > 0:
                        text.append(" " * padding, style="")

                text.append(" \u2502", style="dim #FFD700")
                text.append("\n")

    # Section footer
    text.append("  \u2514", style="dim #FFD700")
    text.append("\u2500" * 53, style="dim #FFD700")
    text.append("\u2518", style="dim #FFD700")
    text.append("\n")


def add_query_history_section(text: Text, border_color: str = "#FFD700") -> None:
    """Add the query history stacks section (CLs tab only).

    Shows last 5 entries from each stack with visual indicators.

    Args:
        text: The Text object to append to.
        border_color: Color for the border characters.
    """
    stacks = load_query_history()

    # Section header
    text.append("\n")
    text.append("  \u250c\u2500 ", style=f"dim {border_color}")
    text.append("Query History", style=f"bold {border_color}")
    text.append(" ", style="")
    remaining = 50 - len("Query History")
    text.append("\u2500" * remaining + "\u2510", style=f"dim {border_color}")
    text.append("\n")

    # Show last 5 from prev stack (most recent first = reversed)
    max_display = 5
    prev_display = list(reversed(stacks.prev[-max_display:]))
    next_display = list(reversed(stacks.next[-max_display:]))
    prev_total = len(stacks.prev)
    next_total = len(stacks.next)

    if not prev_display and not next_display:
        text.append("  \u2502  ", style=f"dim {border_color}")
        text.append("No query history", style="dim italic")
        text.append(" " * 34, style="")
        text.append(" \u2502", style=f"dim {border_color}")
        text.append("\n")
    else:
        # Prev stack section
        if prev_display:
            # Stack header with count
            count_str = f"\u27e8{len(prev_display)}/{prev_total}\u27e9"
            header_text = "\u25c0 PREVIOUS (^)"
            header_padding = 50 - len(header_text) - len(count_str)
            text.append("  \u2502  ", style=f"dim {border_color}")
            text.append(header_text, style="bold #87D7FF")
            text.append(" " * header_padding, style="")
            text.append(count_str, style="dim #87D7FF")
            text.append(" \u2502", style=f"dim {border_color}")
            text.append("\n")

            # Dashed separator
            text.append("  \u2502  ", style=f"dim {border_color}")
            text.append("\u2504" * 50, style="dim #87D7FF")
            text.append(" \u2502", style=f"dim {border_color}")
            text.append("\n")

            for i, query in enumerate(prev_display):
                is_first = i == 0
                dim_level = 0 if i < 2 else (1 if i < 4 else 2)
                _add_history_entry(text, query, is_first, "^", dim_level, border_color)

            # Spacing after prev section if next section follows
            if next_display:
                text.append("  \u2502", style=f"dim {border_color}")
                text.append(" " * 52, style="")
                text.append(" \u2502", style=f"dim {border_color}")
                text.append("\n")

        # Next stack section
        if next_display:
            # Stack header with count
            count_str = f"\u27e8{len(next_display)}/{next_total}\u27e9"
            header_text = "\u25b6 NEXT (_)"
            header_padding = 50 - len(header_text) - len(count_str)
            text.append("  \u2502  ", style=f"dim {border_color}")
            text.append(header_text, style="bold #87D7FF")
            text.append(" " * header_padding, style="")
            text.append(count_str, style="dim #87D7FF")
            text.append(" \u2502", style=f"dim {border_color}")
            text.append("\n")

            # Dashed separator
            text.append("  \u2502  ", style=f"dim {border_color}")
            text.append("\u2504" * 50, style="dim #87D7FF")
            text.append(" \u2502", style=f"dim {border_color}")
            text.append("\n")

            for i, query in enumerate(next_display):
                is_first = i == 0
                dim_level = 0 if i < 2 else (1 if i < 4 else 2)
                _add_history_entry(text, query, is_first, "_", dim_level, border_color)

    # Section footer
    text.append("  \u2514", style=f"dim {border_color}")
    text.append("\u2500" * 53, style=f"dim {border_color}")
    text.append("\u2518", style=f"dim {border_color}")
    text.append("\n")


def _add_history_entry(
    text: Text,
    query: str,
    is_first: bool,
    nav_key: str,
    dim_level: int,
    border_color: str,
) -> None:
    """Add a single history entry line.

    Args:
        text: The Text object to append to.
        query: The query string.
        is_first: Whether this is the first (most recent) entry in the stack.
        nav_key: The navigation key hint ("^" or "_").
        dim_level: Dimming level (0=bright, 1=slightly dim, 2=dim).
        border_color: Color for the border characters.
    """
    text.append("  \u2502  ", style=f"dim {border_color}")

    # Indicator (keymap for first entry, bullet for others)
    if is_first:
        text.append(f"[{nav_key}] ", style="#3CB371")
    else:
        text.append("\u25b8 ", style="white")

    # Query with syntax highlighting (truncated if needed)
    # First entries use [^]/[_] (4 chars) vs bullet (2 chars), so 2 less space
    content_width = 46 if is_first else 48

    if len(query) > content_width:
        display_query = query[: content_width - 3] + "..."
    else:
        display_query = query

    # Apply dimming based on level
    if dim_level <= 1:
        # Full syntax highlighting for recent entries
        query_text = build_query_text(display_query)
        text.append_text(query_text)
    else:
        # Dim plain text for oldest entries
        text.append(display_query, style="dim #888888")

    # Padding and right border
    padding = content_width - len(display_query)
    if padding > 0:
        text.append(" " * padding, style="")
    text.append(" \u2502", style=f"dim {border_color}")
    text.append("\n")
