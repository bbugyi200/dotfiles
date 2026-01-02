"""Storage for saved search queries."""

import json
from pathlib import Path

# Key order: 1 is first, 0 is last (10th)
KEY_ORDER = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
MAX_SAVED_QUERIES = 10

# Cache file location
_SAVED_QUERIES_FILE = Path.home() / ".gai" / "saved_queries.json"


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
