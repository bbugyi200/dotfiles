"""Storage for the last selected ChangeSpec."""

from pathlib import Path

_LAST_SELECTION_FILE = Path.home() / ".gai" / "last_selection.txt"


def load_last_selection() -> str | None:
    """Load the last selected ChangeSpec name from disk."""
    if not _LAST_SELECTION_FILE.exists():
        return None
    try:
        content = _LAST_SELECTION_FILE.read_text().strip()
        return content or None
    except OSError:
        return None


def save_last_selection(name: str) -> bool:
    """Save the currently selected ChangeSpec name."""
    try:
        _LAST_SELECTION_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LAST_SELECTION_FILE.write_text(name)
        return True
    except OSError:
        return False
