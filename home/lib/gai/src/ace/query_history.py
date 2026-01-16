"""Storage for query history stacks (prev/next navigation)."""

import json
from dataclasses import dataclass
from pathlib import Path

# Stack configuration
MAX_STACK_SIZE = 50
_QUERY_HISTORY_FILE = Path.home() / ".gai" / "query_history.json"


@dataclass
class QueryHistoryStacks:
    """Data class holding prev and next stacks."""

    prev: list[str]  # Most recent at end (append/pop from end)
    next: list[str]  # Most recent at end (append/pop from end)


def load_query_history() -> QueryHistoryStacks:
    """Load query history stacks from disk.

    Returns:
        QueryHistoryStacks with prev and next lists.
    """
    if not _QUERY_HISTORY_FILE.exists():
        return QueryHistoryStacks(prev=[], next=[])

    try:
        with open(_QUERY_HISTORY_FILE) as f:
            data = json.load(f)
        # Validate and truncate if needed
        prev = data.get("prev", [])[-MAX_STACK_SIZE:]
        next_ = data.get("next", [])[-MAX_STACK_SIZE:]
        return QueryHistoryStacks(prev=prev, next=next_)
    except (OSError, json.JSONDecodeError):
        return QueryHistoryStacks(prev=[], next=[])


def save_query_history(stacks: QueryHistoryStacks) -> bool:
    """Save query history stacks to disk.

    Args:
        stacks: The QueryHistoryStacks to save.

    Returns:
        True if saved successfully, False otherwise.
    """
    try:
        _QUERY_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Truncate to max size before saving
        data = {
            "prev": stacks.prev[-MAX_STACK_SIZE:],
            "next": stacks.next[-MAX_STACK_SIZE:],
        }
        with open(_QUERY_HISTORY_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except OSError:
        return False


def _remove_and_append(stack: list[str], query: str) -> None:
    """Remove query from stack if present, then append to end."""
    if query in stack:
        stack.remove(query)  # Removes first occurrence
    stack.append(query)


def push_to_prev_stack(current_query: str, stacks: QueryHistoryStacks) -> None:
    """Push current query to prev stack and clear next stack.

    This is called when user manually changes the query (via / or saved query).

    Args:
        current_query: The query being replaced (to push to prev).
        stacks: The stacks to modify (in-place).
    """
    _remove_and_append(stacks.prev, current_query)
    # Enforce max size
    if len(stacks.prev) > MAX_STACK_SIZE:
        stacks.prev = stacks.prev[-MAX_STACK_SIZE:]
    # Clear next stack on new navigation
    stacks.next.clear()


def navigate_prev(current_query: str, stacks: QueryHistoryStacks) -> str | None:
    """Navigate to previous query.

    Args:
        current_query: The current query (to push to next).
        stacks: The stacks to modify (in-place).

    Returns:
        The previous query, or None if prev stack is empty.
    """
    if not stacks.prev:
        return None

    # Push current to next stack (removing old duplicate if any)
    _remove_and_append(stacks.next, current_query)

    # Pop from prev stack
    return stacks.prev.pop()


def navigate_next(current_query: str, stacks: QueryHistoryStacks) -> str | None:
    """Navigate to next query.

    Args:
        current_query: The current query (to push to prev).
        stacks: The stacks to modify (in-place).

    Returns:
        The next query, or None if next stack is empty.
    """
    if not stacks.next:
        return None

    # Push current to prev stack (removing old duplicate if any)
    _remove_and_append(stacks.prev, current_query)

    # Pop from next stack
    return stacks.next.pop()
