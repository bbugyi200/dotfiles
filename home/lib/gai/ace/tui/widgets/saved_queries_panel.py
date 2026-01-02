"""Widget for displaying saved search queries."""

from typing import Any

from rich.text import Text
from textual.widgets import Static

from ...saved_queries import KEY_ORDER, load_saved_queries
from .changespec_detail import build_query_text

# Maximum length for displayed queries before truncation
_MAX_QUERY_DISPLAY_LENGTH = 30


class SavedQueriesPanel(Static):
    """Panel showing saved search queries."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the saved queries panel."""
        super().__init__(**kwargs)

    def refresh_queries(self, active_query: str | None = None) -> None:
        """Refresh the display with current saved queries.

        Args:
            active_query: The currently active canonical query string.
        """
        queries = load_saved_queries()

        if not queries:
            self.update("")
            self.display = False
            return

        self.display = True
        text = Text()
        text.append("Saved Queries ", style="dim italic #87D7FF")
        text.append("» ", style="dim #808080")

        first = True
        for slot in KEY_ORDER:
            if slot in queries:
                if not first:
                    text.append(" | ", style="dim #808080")
                first = False

                # Slot number: bright green bold if active, dark green otherwise
                query = queries[slot]
                is_active = active_query is not None and query == active_query
                slot_style = "bold #00FF00" if is_active else "#228B22"
                text.append(f"[{slot}] ", style=slot_style)

                # Query with syntax highlighting (truncated if needed)
                query = queries[slot]
                if len(query) > _MAX_QUERY_DISPLAY_LENGTH:
                    display_query = query[: _MAX_QUERY_DISPLAY_LENGTH - 3] + "..."
                else:
                    display_query = query
                text.append_text(build_query_text(display_query))

        self.update(text)
