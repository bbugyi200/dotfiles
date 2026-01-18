"""Tests for ChangeSpec navigation history (ctrl+o / ctrl+i)."""

from ace.tui.changespec_history import (
    MAX_STACK_SIZE,
    ChangeSpecHistoryEntry,
    ChangeSpecHistoryStacks,
    create_empty_stacks,
    navigate_next,
    navigate_prev,
    push_to_prev_stack,
)


def _make_entry(
    name: str, file_path: str = "/test/project.gp", query: str = "*"
) -> ChangeSpecHistoryEntry:
    """Helper to create a test entry."""
    return ChangeSpecHistoryEntry(name=name, file_path=file_path, query=query)


def test_create_empty_stacks() -> None:
    """Test creating empty stacks."""
    stacks = create_empty_stacks()
    assert stacks.prev == []
    assert stacks.next == []


def test_changespec_history_entry_dataclass() -> None:
    """Test that ChangeSpecHistoryEntry stores all fields."""
    entry = ChangeSpecHistoryEntry(
        name="my-cl",
        file_path="/home/.gai/projects/test/test.gp",
        query="status:WIP",
    )
    assert entry.name == "my-cl"
    assert entry.file_path == "/home/.gai/projects/test/test.gp"
    assert entry.query == "status:WIP"


def test_push_to_prev_clears_next() -> None:
    """Test that pushing to prev clears the next stack."""
    stacks = ChangeSpecHistoryStacks(
        prev=[_make_entry("old")],
        next=[_make_entry("future")],
    )
    push_to_prev_stack(_make_entry("current"), stacks)
    assert len(stacks.prev) == 2
    assert stacks.prev[-1].name == "current"
    assert stacks.next == []


def test_push_to_prev_no_duplicates() -> None:
    """Test that pushing entry removes existing duplicate (by name/file_path)."""
    stacks = ChangeSpecHistoryStacks(
        prev=[
            _make_entry("old"),
            _make_entry("current", query="query1"),
            _make_entry("other"),
        ],
        next=[],
    )
    # Push same name/file_path with different query
    push_to_prev_stack(_make_entry("current", query="query2"), stacks)
    # "current" removed from middle and added to end with new query
    assert len(stacks.prev) == 3
    assert stacks.prev[0].name == "old"
    assert stacks.prev[1].name == "other"
    assert stacks.prev[2].name == "current"
    assert stacks.prev[2].query == "query2"


def test_push_to_prev_different_file_path_not_duplicate() -> None:
    """Test that same name but different file_path is not a duplicate."""
    stacks = ChangeSpecHistoryStacks(
        prev=[_make_entry("same-name", file_path="/project1/test.gp")],
        next=[],
    )
    push_to_prev_stack(_make_entry("same-name", file_path="/project2/test.gp"), stacks)
    # Both entries should exist since they have different file_paths
    assert len(stacks.prev) == 2
    assert stacks.prev[0].file_path == "/project1/test.gp"
    assert stacks.prev[1].file_path == "/project2/test.gp"


def test_push_to_prev_empty_stack() -> None:
    """Test pushing to empty prev stack."""
    stacks = ChangeSpecHistoryStacks(
        prev=[],
        next=[_make_entry("future")],
    )
    push_to_prev_stack(_make_entry("current"), stacks)
    assert len(stacks.prev) == 1
    assert stacks.prev[0].name == "current"
    assert stacks.next == []


def test_navigate_prev_empty() -> None:
    """Test navigating prev when stack is empty."""
    stacks = create_empty_stacks()
    result = navigate_prev(_make_entry("current"), stacks)
    assert result is None
    assert stacks.prev == []
    assert stacks.next == []


def test_navigate_prev_success() -> None:
    """Test successful prev navigation."""
    stacks = ChangeSpecHistoryStacks(
        prev=[_make_entry("old1"), _make_entry("old2")],
        next=[],
    )
    result = navigate_prev(_make_entry("current"), stacks)
    assert result is not None
    assert result.name == "old2"
    assert len(stacks.prev) == 1
    assert stacks.prev[0].name == "old1"
    assert len(stacks.next) == 1
    assert stacks.next[0].name == "current"


def test_navigate_prev_single_item() -> None:
    """Test navigating prev with single item in stack."""
    stacks = ChangeSpecHistoryStacks(
        prev=[_make_entry("only")],
        next=[],
    )
    result = navigate_prev(_make_entry("current"), stacks)
    assert result is not None
    assert result.name == "only"
    assert stacks.prev == []
    assert len(stacks.next) == 1
    assert stacks.next[0].name == "current"


def test_navigate_prev_removes_duplicate_from_next() -> None:
    """Test that navigate_prev removes duplicate from next stack."""
    stacks = ChangeSpecHistoryStacks(
        prev=[_make_entry("old")],
        next=[
            _make_entry("future"),
            _make_entry("current", query="old-query"),
            _make_entry("other"),
        ],
    )
    result = navigate_prev(_make_entry("current", query="new-query"), stacks)
    assert result is not None
    assert result.name == "old"
    assert stacks.prev == []
    # "current" removed from middle of next stack and moved to end
    assert len(stacks.next) == 3
    assert stacks.next[0].name == "future"
    assert stacks.next[1].name == "other"
    assert stacks.next[2].name == "current"
    assert stacks.next[2].query == "new-query"


def test_navigate_next_empty() -> None:
    """Test navigating next when stack is empty."""
    stacks = create_empty_stacks()
    result = navigate_next(_make_entry("current"), stacks)
    assert result is None
    assert stacks.prev == []
    assert stacks.next == []


def test_navigate_next_success() -> None:
    """Test successful next navigation."""
    stacks = ChangeSpecHistoryStacks(
        prev=[],
        next=[_make_entry("future1"), _make_entry("future2")],
    )
    result = navigate_next(_make_entry("current"), stacks)
    assert result is not None
    assert result.name == "future2"
    assert len(stacks.prev) == 1
    assert stacks.prev[0].name == "current"
    assert len(stacks.next) == 1
    assert stacks.next[0].name == "future1"


def test_navigate_next_single_item() -> None:
    """Test navigating next with single item in stack."""
    stacks = ChangeSpecHistoryStacks(
        prev=[],
        next=[_make_entry("only")],
    )
    result = navigate_next(_make_entry("current"), stacks)
    assert result is not None
    assert result.name == "only"
    assert len(stacks.prev) == 1
    assert stacks.prev[0].name == "current"
    assert stacks.next == []


def test_navigate_next_removes_duplicate_from_prev() -> None:
    """Test that navigate_next removes duplicate from prev stack."""
    stacks = ChangeSpecHistoryStacks(
        prev=[
            _make_entry("old"),
            _make_entry("current", query="old-query"),
            _make_entry("other"),
        ],
        next=[_make_entry("future")],
    )
    result = navigate_next(_make_entry("current", query="new-query"), stacks)
    assert result is not None
    assert result.name == "future"
    # "current" removed from middle of prev stack and moved to end
    assert len(stacks.prev) == 3
    assert stacks.prev[0].name == "old"
    assert stacks.prev[1].name == "other"
    assert stacks.prev[2].name == "current"
    assert stacks.prev[2].query == "new-query"
    assert stacks.next == []


def test_max_stack_size_on_push() -> None:
    """Test that push enforces max size."""
    entries = [_make_entry(f"cl{i}") for i in range(MAX_STACK_SIZE)]
    stacks = ChangeSpecHistoryStacks(prev=entries, next=[])
    push_to_prev_stack(_make_entry("new"), stacks)
    assert len(stacks.prev) == MAX_STACK_SIZE
    # Should keep most recent entries (including the new one)
    assert stacks.prev[-1].name == "new"
    assert stacks.prev[0].name == "cl1"  # cl0 dropped


def test_round_trip_navigation() -> None:
    """Test navigating back and forth preserves entries."""
    stacks = ChangeSpecHistoryStacks(
        prev=[_make_entry("cl1"), _make_entry("cl2")],
        next=[],
    )

    # Navigate back twice
    r1 = navigate_prev(_make_entry("cl3"), stacks)
    assert r1 is not None and r1.name == "cl2"
    r2 = navigate_prev(_make_entry("cl2"), stacks)
    assert r2 is not None and r2.name == "cl1"

    # Navigate forward twice
    r3 = navigate_next(_make_entry("cl1"), stacks)
    assert r3 is not None and r3.name == "cl2"
    r4 = navigate_next(_make_entry("cl2"), stacks)
    assert r4 is not None and r4.name == "cl3"

    # Final state: back where we started
    assert len(stacks.prev) == 2
    assert stacks.prev[0].name == "cl1"
    assert stacks.prev[1].name == "cl2"
    assert stacks.next == []


def test_new_navigation_clears_forward_history() -> None:
    """Test that new navigation clears the forward history."""
    stacks = ChangeSpecHistoryStacks(
        prev=[_make_entry("cl1"), _make_entry("cl2")],
        next=[],
    )

    # Navigate back
    result = navigate_prev(_make_entry("cl3"), stacks)
    assert result is not None and result.name == "cl2"
    assert len(stacks.next) == 1
    assert stacks.next[0].name == "cl3"

    # Make a new navigation (simulates clicking on a different CL after going back)
    push_to_prev_stack(_make_entry("cl2"), stacks)
    assert len(stacks.prev) == 2
    assert stacks.prev[0].name == "cl1"
    assert stacks.prev[1].name == "cl2"
    assert stacks.next == []  # Forward history cleared


def test_query_preserved_in_history() -> None:
    """Test that the query is preserved in history entries."""
    stacks = create_empty_stacks()

    # Push entries with different queries
    push_to_prev_stack(
        ChangeSpecHistoryEntry(name="cl1", file_path="/test.gp", query="status:WIP"),
        stacks,
    )
    push_to_prev_stack(
        ChangeSpecHistoryEntry(
            name="cl2", file_path="/test.gp", query="status:Drafted"
        ),
        stacks,
    )

    # Navigate back and verify query is preserved
    result = navigate_prev(
        ChangeSpecHistoryEntry(name="cl3", file_path="/test.gp", query="*"),
        stacks,
    )
    assert result is not None
    assert result.name == "cl2"
    assert result.query == "status:Drafted"
