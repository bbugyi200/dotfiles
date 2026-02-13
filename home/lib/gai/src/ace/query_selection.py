"""Persistent mapping from query string to selected ChangeSpec name."""

import json
from pathlib import Path

MAX_SELECTIONS = 200
_QUERY_SELECTION_FILE = Path.home() / ".gai" / "query_selections.json"


def load_query_selections() -> dict[str, str]:
    """Load query-to-selection mapping from disk.

    Returns:
        Dict mapping canonical query strings to ChangeSpec names.
    """
    if not _QUERY_SELECTION_FILE.exists():
        return {}

    try:
        with open(_QUERY_SELECTION_FILE) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except (OSError, json.JSONDecodeError):
        return {}


def save_query_selections(selections: dict[str, str]) -> bool:
    """Save query-to-selection mapping to disk, trimming oldest entries.

    Uses pop+re-insert to keep recently-used entries at the end so
    trimming discards the least-recently-used entries.

    Args:
        selections: Dict mapping canonical query strings to ChangeSpec names.

    Returns:
        True if saved successfully, False otherwise.
    """
    try:
        _QUERY_SELECTION_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Trim oldest entries if over limit (keep most recent at end)
        if len(selections) > MAX_SELECTIONS:
            keys = list(selections.keys())
            for key in keys[: len(keys) - MAX_SELECTIONS]:
                del selections[key]
        with open(_QUERY_SELECTION_FILE, "w") as f:
            json.dump(selections, f, indent=2)
        return True
    except OSError:
        return False
