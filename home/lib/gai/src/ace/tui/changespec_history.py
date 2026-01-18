"""Session-based ChangeSpec navigation history (ctrl+o / ctrl+i).

This module provides vim-style jumplist navigation for ChangeSpecs.
History is stored in memory only (session-based, not persisted to disk).
"""

from dataclasses import dataclass, field

# Stack configuration
MAX_STACK_SIZE = 50


@dataclass
class ChangeSpecHistoryEntry:
    """A single entry in the ChangeSpec navigation history.

    Uses (name, file_path) tuple for unique ChangeSpec identification.
    """

    name: str  # ChangeSpec name
    file_path: str  # Path to .gp file
    query: str  # Query string active at selection time


@dataclass
class ChangeSpecHistoryStacks:
    """Data class holding prev and next stacks for ChangeSpec navigation."""

    prev: list[ChangeSpecHistoryEntry] = field(default_factory=list)
    next: list[ChangeSpecHistoryEntry] = field(default_factory=list)


def create_empty_stacks() -> ChangeSpecHistoryStacks:
    """Create a new empty ChangeSpecHistoryStacks instance.

    Returns:
        ChangeSpecHistoryStacks with empty prev and next lists.
    """
    return ChangeSpecHistoryStacks()


def _entry_matches(e1: ChangeSpecHistoryEntry, e2: ChangeSpecHistoryEntry) -> bool:
    """Check if two entries refer to the same ChangeSpec (by name and file_path).

    Args:
        e1: First entry.
        e2: Second entry.

    Returns:
        True if both entries have the same name and file_path.
    """
    return e1.name == e2.name and e1.file_path == e2.file_path


def _remove_matching_entries(
    stack: list[ChangeSpecHistoryEntry], entry: ChangeSpecHistoryEntry
) -> None:
    """Remove all entries from stack that match the given entry (by name/file_path).

    Args:
        stack: The stack to modify (in-place).
        entry: The entry to match against.
    """
    stack[:] = [e for e in stack if not _entry_matches(e, entry)]


def push_to_prev_stack(
    entry: ChangeSpecHistoryEntry, stacks: ChangeSpecHistoryStacks
) -> None:
    """Push an entry to prev stack and clear next stack.

    This is called when user navigates to a different ChangeSpec via:
    - Clicking to select a different CL
    - Navigating via ancestry keys (<, >)

    Args:
        entry: The current ChangeSpec entry being navigated away from.
        stacks: The stacks to modify (in-place).
    """
    # Remove any existing entry with same name/file_path to avoid duplicates
    _remove_matching_entries(stacks.prev, entry)

    # Append to prev stack
    stacks.prev.append(entry)

    # Enforce max size
    if len(stacks.prev) > MAX_STACK_SIZE:
        stacks.prev = stacks.prev[-MAX_STACK_SIZE:]

    # Clear next stack on new navigation
    stacks.next.clear()


def navigate_prev(
    current_entry: ChangeSpecHistoryEntry, stacks: ChangeSpecHistoryStacks
) -> ChangeSpecHistoryEntry | None:
    """Navigate to previous ChangeSpec (ctrl+o).

    Args:
        current_entry: The current ChangeSpec entry (to push to next).
        stacks: The stacks to modify (in-place).

    Returns:
        The previous entry, or None if prev stack is empty.
    """
    if not stacks.prev:
        return None

    # Remove duplicates of current from next stack before pushing
    _remove_matching_entries(stacks.next, current_entry)

    # Push current to next stack
    stacks.next.append(current_entry)

    # Pop from prev stack
    return stacks.prev.pop()


def navigate_next(
    current_entry: ChangeSpecHistoryEntry, stacks: ChangeSpecHistoryStacks
) -> ChangeSpecHistoryEntry | None:
    """Navigate to next ChangeSpec (ctrl+i).

    Args:
        current_entry: The current ChangeSpec entry (to push to prev).
        stacks: The stacks to modify (in-place).

    Returns:
        The next entry, or None if next stack is empty.
    """
    if not stacks.next:
        return None

    # Remove duplicates of current from prev stack before pushing
    _remove_matching_entries(stacks.prev, current_entry)

    # Push current to prev stack
    stacks.prev.append(current_entry)

    # Pop from next stack
    return stacks.next.pop()
