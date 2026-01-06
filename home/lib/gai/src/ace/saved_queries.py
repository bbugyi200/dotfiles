"""Storage for saved search queries."""

import json
from pathlib import Path

# Key order: 0 is first, 9 is last
KEY_ORDER = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
MAX_SAVED_QUERIES = 10

# Cache file locations
_SAVED_QUERIES_FILE = Path.home() / ".gai" / "saved_queries.json"
_LAST_QUERY_FILE = Path.home() / ".gai" / "last_query.txt"


def load_saved_queries() -> dict[str, str]:
    """Load saved queries from disk.

    Returns:
        Dictionary mapping slot number ("0"-"9") to canonical query string.
    """
    if not _SAVED_QUERIES_FILE.exists():
        return {}

    try:
        with open(_SAVED_QUERIES_FILE) as f:
            data = json.load(f)
        # Filter to only valid keys
        return {k: v for k, v in data.items() if k in KEY_ORDER}
    except (OSError, json.JSONDecodeError):
        return {}


def save_query(slot: str, query: str) -> bool:
    """Save a query to a specific slot.

    Args:
        slot: The slot number ("0"-"9")
        query: The canonical query string

    Returns:
        True if saved successfully, False otherwise.
    """
    if slot not in KEY_ORDER:
        return False

    queries = load_saved_queries()
    queries[slot] = query
    return _write_queries(queries)


def delete_query(slot: str) -> bool:
    """Delete a query from a specific slot.

    Args:
        slot: The slot number ("0"-"9")

    Returns:
        True if deleted (or slot was already empty), False on error.
    """
    queries = load_saved_queries()
    if slot in queries:
        del queries[slot]
        return _write_queries(queries)
    return True  # Slot was already empty


def get_next_available_slot(queries: dict[str, str]) -> str | None:
    """Get the next available slot in order 1,2,3...9,0.

    Args:
        queries: Current saved queries dict.

    Returns:
        Slot number string, or None if all slots are full.
    """
    for slot in KEY_ORDER:
        if slot not in queries:
            return slot
    return None


def load_last_query() -> str | None:
    """Load the last used query from disk.

    Returns:
        The last used query string, or None if no saved query exists.
    """
    if not _LAST_QUERY_FILE.exists():
        return None
    try:
        content = _LAST_QUERY_FILE.read_text().strip()
        return content or None
    except OSError:
        return None


def save_last_query(query: str) -> bool:
    """Save the current query as the last used query.

    Args:
        query: The canonical query string to save.

    Returns:
        True if saved successfully, False otherwise.
    """
    try:
        _LAST_QUERY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LAST_QUERY_FILE.write_text(query)
        return True
    except OSError:
        return False


def _write_queries(queries: dict[str, str]) -> bool:
    """Write queries to disk.

    Args:
        queries: Dictionary mapping slot numbers to query strings.

    Returns:
        True if written successfully, False otherwise.
    """
    try:
        _SAVED_QUERIES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_SAVED_QUERIES_FILE, "w") as f:
            json.dump(queries, f, indent=2)
        return True
    except OSError:
        return False
