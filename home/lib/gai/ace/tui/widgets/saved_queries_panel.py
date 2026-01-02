"""Widget for displaying saved search queries."""

from typing import Any

from rich.text import Text
from textual.widgets import Static

from ...saved_queries import KEY_ORDER, load_saved_queries

# Maximum length for displayed queries before truncation
_MAX_QUERY_DISPLAY_LENGTH = 30


class SavedQueriesPanel(Static):
    """Panel showing saved search queries."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the saved queries panel."""
        super().__init__(**kwargs)

    def refresh_queries(self) -> None:
        """Refresh the display with current saved queries."""
        queries = load_saved_queries()

        if not queries:
            self.update("")
            self.display = False
            return

        self.display = True
        text = Text()
        text.append("Saved Queries ", style="dim italic #87D7FF")
        text.append("» ", style="dim #808080")

        parts: list[str] = []
        for slot in KEY_ORDER:
            if slot in queries:
                query = queries[slot]
                # Truncate long queries for display
                if len(query) > _MAX_QUERY_DISPLAY_LENGTH:
                    display_query = query[: _MAX_QUERY_DISPLAY_LENGTH - 3] + "..."
                else:
                    display_query = query
                parts.append(f"[{slot}] {display_query}")

        text.append(" | ".join(parts), style="#D7D7AF")
        self.update(text)
