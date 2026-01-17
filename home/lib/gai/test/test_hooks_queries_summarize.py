"""Tests for summarize-hook workflow query functions."""

from ace.changespec import (
    HookEntry,
    HookStatusLine,
)


def _make_hook(
    command: str,
    commit_entry_num: str = "1",
    timestamp: str | None = None,
    status: str | None = None,
    duration: str | None = None,
) -> HookEntry:
    """Helper function to create a HookEntry with a status line."""
    if timestamp is None and status is None:
        return HookEntry(command=command)
    status_line = HookStatusLine(
        commit_entry_num=commit_entry_num,
        timestamp=timestamp or "",
        status=status or "",
        duration=duration,
    )
    return HookEntry(command=command, status_lines=[status_line])


# Tests for get_failing_hooks_for_summarize
def test_get_failing_hooks_for_summarize_basic() -> None:
    """Test getting failing hooks eligible for summarize-hook workflow."""
    from ace.hooks.queries import get_failing_hooks_for_summarize

    hook = HookEntry(
        command="flake8 src",
        status_lines=[
            HookStatusLine(
                commit_entry_num="2a",
                timestamp="240601_123456",
                status="FAILED",
            )
        ],
    )
    result = get_failing_hooks_for_summarize([hook])
    assert len(result) == 1
    assert result[0].command == "flake8 src"


def test_get_failing_hooks_for_summarize_excludes_non_proposal() -> None:
    """Test that non-proposal entries are excluded from summarize-hook."""
    from ace.hooks.queries import get_failing_hooks_for_summarize

    hook = HookEntry(
        command="flake8 src",
        status_lines=[
            HookStatusLine(
                commit_entry_num="2",
                timestamp="240601_123456",
                status="FAILED",
            )
        ],
    )
    result = get_failing_hooks_for_summarize([hook])
    assert len(result) == 0


def test_get_failing_hooks_for_summarize_excludes_with_suffix() -> None:
    """Test that hooks with suffix are excluded from summarize-hook."""
    from ace.hooks.queries import get_failing_hooks_for_summarize

    hook = HookEntry(
        command="flake8 src",
        status_lines=[
            HookStatusLine(
                commit_entry_num="2a",
                timestamp="240601_123456",
                status="FAILED",
                suffix="already processed",
            )
        ],
    )
    result = get_failing_hooks_for_summarize([hook])
    assert len(result) == 0


def test_get_failing_hooks_for_summarize_excludes_non_failed() -> None:
    """Test that non-FAILED statuses are excluded from summarize-hook."""
    from ace.hooks.queries import get_failing_hooks_for_summarize

    hooks = [
        HookEntry(
            command="flake8 src",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="2a",
                    timestamp="240601_123456",
                    status="PASSED",
                )
            ],
        ),
        HookEntry(
            command="mypy src",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="2a",
                    timestamp="240601_123456",
                    status="RUNNING",
                )
            ],
        ),
    ]
    result = get_failing_hooks_for_summarize(hooks)
    assert len(result) == 0


def test_get_failing_hooks_for_summarize_no_status_lines() -> None:
    """Test that hooks with no status_lines are excluded from summarize."""
    from ace.hooks.queries import get_failing_hooks_for_summarize

    hooks = [HookEntry(command="flake8 src")]
    result = get_failing_hooks_for_summarize(hooks)
    assert len(result) == 0


# Tests for get_failing_hook_entries_for_summarize
def test_get_failing_hook_entries_for_summarize_basic() -> None:
    """Test getting failing hook entries for summarize workflow."""
    from ace.hooks.queries import get_failing_hook_entries_for_summarize

    hook = HookEntry(
        command="flake8 src",
        status_lines=[
            HookStatusLine(
                commit_entry_num="3a",
                timestamp="240601_123456",
                status="FAILED",
            )
        ],
    )
    result = get_failing_hook_entries_for_summarize([hook], ["3a"])
    assert len(result) == 1
    assert result[0][0].command == "flake8 src"
    assert result[0][1] == "3a"


def test_get_failing_hook_entries_for_summarize_includes_non_proposal() -> None:
    """Test that non-proposal entries ARE included in summarize."""
    from ace.hooks.queries import get_failing_hook_entries_for_summarize

    hook = HookEntry(
        command="flake8 src",
        status_lines=[
            HookStatusLine(
                commit_entry_num="3",
                timestamp="240601_123456",
                status="FAILED",
            )
        ],
    )
    result = get_failing_hook_entries_for_summarize([hook], ["3"])
    assert len(result) == 1


def test_get_failing_hook_entries_for_summarize_excludes_with_suffix() -> None:
    """Test that entries with suffix are excluded from summarize."""
    from ace.hooks.queries import get_failing_hook_entries_for_summarize

    hook = HookEntry(
        command="flake8 src",
        status_lines=[
            HookStatusLine(
                commit_entry_num="3a",
                timestamp="240601_123456",
                status="FAILED",
                suffix="already processed",
            )
        ],
    )
    result = get_failing_hook_entries_for_summarize([hook], ["3a"])
    assert len(result) == 0


def test_get_failing_hook_entries_for_summarize_multiple() -> None:
    """Test summarize with multiple hooks and entry IDs."""
    from ace.hooks.queries import get_failing_hook_entries_for_summarize

    hooks = [
        HookEntry(
            command="flake8 src",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="2a",
                    timestamp="240601_100000",
                    status="FAILED",
                ),
            ],
        ),
        HookEntry(
            command="pytest tests",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="3",
                    timestamp="240601_110000",
                    status="FAILED",
                ),
            ],
        ),
    ]
    result = get_failing_hook_entries_for_summarize(hooks, ["2a", "3"])
    assert len(result) == 2


def test_get_failing_hook_entries_for_summarize_no_status_lines() -> None:
    """Test that hooks with no status_lines return empty results for summarize."""
    from ace.hooks.queries import get_failing_hook_entries_for_summarize

    hooks = [HookEntry(command="flake8 src")]
    result = get_failing_hook_entries_for_summarize(hooks, ["1", "2"])
    assert len(result) == 0


def test_get_failing_hook_entries_for_summarize_entry_not_found() -> None:
    """Test that missing entry IDs are handled correctly for summarize."""
    from ace.hooks.queries import get_failing_hook_entries_for_summarize

    hooks = [
        HookEntry(
            command="flake8 src",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="FAILED",
                )
            ],
        )
    ]
    result = get_failing_hook_entries_for_summarize(hooks, ["2"])
    assert len(result) == 0


def test_get_failing_hook_entries_for_summarize_passed_status() -> None:
    """Test that PASSED hooks are excluded from summarize."""
    from ace.hooks.queries import get_failing_hook_entries_for_summarize

    hooks = [
        HookEntry(
            command="flake8 src",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="PASSED",
                )
            ],
        )
    ]
    result = get_failing_hook_entries_for_summarize(hooks, ["1"])
    assert len(result) == 0
