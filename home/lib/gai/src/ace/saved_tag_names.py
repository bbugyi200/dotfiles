"""Persistence for previously used CL tag names."""

import json
from pathlib import Path

_SAVED_TAG_NAMES_FILE = Path.home() / ".gai" / "saved_tag_names.json"


def load_saved_tag_names() -> list[str]:
    """Load saved tag names from disk.

    Returns:
        List of uppercase tag name strings, or empty list if not found.
    """
    if not _SAVED_TAG_NAMES_FILE.exists():
        return []

    try:
        with open(_SAVED_TAG_NAMES_FILE) as f:
            data = json.load(f)
        if isinstance(data, list):
            return [str(name) for name in data]
        return []
    except (OSError, json.JSONDecodeError):
        return []


def save_tag_name(name: str) -> None:
    """Add an uppercase tag name to the saved list (deduplicated).

    Args:
        name: The tag name to save (will be uppercased).
    """
    upper_name = name.upper()
    names = load_saved_tag_names()
    if upper_name not in names:
        names.append(upper_name)
    try:
        _SAVED_TAG_NAMES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_SAVED_TAG_NAMES_FILE, "w") as f:
            json.dump(names, f, indent=2)
    except OSError:
        pass
