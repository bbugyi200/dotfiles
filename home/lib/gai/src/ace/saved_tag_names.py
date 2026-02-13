"""Persistence for previously used CL tag names and values."""

import json
from pathlib import Path

_SAVED_TAG_NAMES_FILE = Path.home() / ".gai" / "saved_tag_names.json"


def load_saved_tags() -> dict[str, str]:
    """Load saved tags (name→value) from disk.

    Handles both legacy list format (converts to dict with empty values)
    and new dict format.

    Returns:
        Dict mapping uppercase tag names to their last-used values.
    """
    if not _SAVED_TAG_NAMES_FILE.exists():
        return {}

    try:
        with open(_SAVED_TAG_NAMES_FILE) as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
        if isinstance(data, list):
            # Legacy format: convert list to dict with empty values
            return {str(name): "" for name in data}
        return {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_tag(name: str, value: str = "") -> None:
    """Save a tag name and its value.

    Args:
        name: The tag name to save (will be uppercased).
        value: The tag value to associate with the name.
    """
    upper_name = name.upper()
    tags = load_saved_tags()
    tags[upper_name] = value
    try:
        _SAVED_TAG_NAMES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_SAVED_TAG_NAMES_FILE, "w") as f:
            json.dump(tags, f, indent=2)
    except OSError:
        pass
