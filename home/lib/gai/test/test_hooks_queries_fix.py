"""Tests for fix-hook workflow query functions."""

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


# Tests for get_failing_hooks_for_fix
def test_get_failing_hooks_for_fix_basic() -> None:
    """Test getting failing hooks eligible for fix-hook workflow."""
    from ace.hooks.queries import get_failing_hooks_for_fix

    hooks = [
        _make_hook(command="flake8 src", status="FAILED"),
        _make_hook(command="pytest tests", status="PASSED"),
        _make_hook(command="mypy src", status="FAILED"),
    ]
    failing = get_failing_hooks_for_fix(hooks)
    assert len(failing) == 2
    assert failing[0].command == "flake8 src"
    assert failing[1].command == "mypy src"


def test_get_failing_hooks_for_fix_excludes_proposals() -> None:
    """Test that proposal entries (like '2a') are excluded from fix-hook."""
    from ace.hooks.queries import get_failing_hooks_for_fix

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
    failing = get_failing_hooks_for_fix([hook])
    assert len(failing) == 0


def test_get_failing_hooks_for_fix_excludes_hooks_with_suffix() -> None:
    """Test that hooks with suffix are excluded from fix-hook."""
    from ace.hooks.queries import get_failing_hooks_for_fix

    hook = HookEntry(
        command="flake8 src",
        status_lines=[
            HookStatusLine(
                commit_entry_num="1",
                timestamp="240601_123456",
                status="FAILED",
                suffix="running_agent",
            )
        ],
    )
    failing = get_failing_hooks_for_fix([hook])
    assert len(failing) == 0


def test_get_failing_hooks_for_fix_includes_regular_entries() -> None:
    """Test that regular entries (not proposals) are included in fix-hook."""
    from ace.hooks.queries import get_failing_hooks_for_fix

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
    failing = get_failing_hooks_for_fix([hook])
    assert len(failing) == 1
    assert failing[0].command == "flake8 src"


def test_get_failing_hooks_for_fix_no_status_lines() -> None:
    """Test that hooks with no status_lines are handled correctly for fix."""
    from ace.hooks.queries import get_failing_hooks_for_fix

    hooks = [HookEntry(command="flake8 src")]
    result = get_failing_hooks_for_fix(hooks)
    assert len(result) == 0


# Tests for get_failing_hook_entries_for_fix
def test_get_failing_hook_entries_for_fix_basic() -> None:
    """Test getting failing hook entries for specific entry IDs."""
    from ace.hooks.queries import get_failing_hook_entries_for_fix

    hook = HookEntry(
        command="flake8 src",
        status_lines=[
            HookStatusLine(
                commit_entry_num="3",
                timestamp="240601_123456",
                status="FAILED",
                suffix="summary text",
                suffix_type="summarize_complete",
            )
        ],
    )
    result = get_failing_hook_entries_for_fix([hook], ["3"])
    assert len(result) == 1
    assert result[0][0].command == "flake8 src"
    assert result[0][1] == "3"


def test_get_failing_hook_entries_for_fix_excludes_proposals() -> None:
    """Test that proposal entry IDs are excluded from fix-hook."""
    from ace.hooks.queries import get_failing_hook_entries_for_fix

    hook = HookEntry(
        command="flake8 src",
        status_lines=[
            HookStatusLine(
                commit_entry_num="3a",
                timestamp="240601_123456",
                status="FAILED",
                suffix="summary",
                suffix_type="summarize_complete",
            )
        ],
    )
    result = get_failing_hook_entries_for_fix([hook], ["3a"])
    assert len(result) == 0


def test_get_failing_hook_entries_for_fix_requires_summarize_complete() -> None:
    """Test that only entries with summarize_complete suffix are included."""
    from ace.hooks.queries import get_failing_hook_entries_for_fix

    hook = HookEntry(
        command="flake8 src",
        status_lines=[
            HookStatusLine(
                commit_entry_num="3",
                timestamp="240601_123456",
                status="FAILED",
                suffix="running",
                suffix_type="running_agent",
            )
        ],
    )
    result = get_failing_hook_entries_for_fix([hook], ["3"])
    assert len(result) == 0


def test_get_failing_hook_entries_for_fix_requires_suffix() -> None:
    """Test that entries without suffix are excluded from fix-hook."""
    from ace.hooks.queries import get_failing_hook_entries_for_fix

    hook = HookEntry(
        command="flake8 src",
        status_lines=[
            HookStatusLine(
                commit_entry_num="3",
                timestamp="240601_123456",
                status="FAILED",
                suffix_type="summarize_complete",
                suffix=None,
            )
        ],
    )
    result = get_failing_hook_entries_for_fix([hook], ["3"])
    assert len(result) == 0


def test_get_failing_hook_entries_for_fix_multiple_entries() -> None:
    """Test checking multiple entry IDs across multiple hooks."""
    from ace.hooks.queries import get_failing_hook_entries_for_fix

    hooks = [
        HookEntry(
            command="flake8 src",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="2",
                    timestamp="240601_100000",
                    status="FAILED",
                    suffix="summary1",
                    suffix_type="summarize_complete",
                ),
                HookStatusLine(
                    commit_entry_num="3",
                    timestamp="240601_110000",
                    status="PASSED",
                ),
            ],
        ),
        HookEntry(
            command="pytest tests",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="2",
                    timestamp="240601_120000",
                    status="FAILED",
                    suffix="summary2",
                    suffix_type="summarize_complete",
                ),
            ],
        ),
    ]
    result = get_failing_hook_entries_for_fix(hooks, ["2", "3"])
    assert len(result) == 2
    commands = [r[0].command for r in result]
    assert "flake8 src" in commands
    assert "pytest tests" in commands


def test_get_failing_hook_entries_for_fix_no_status_lines() -> None:
    """Test that hooks with no status_lines return empty results."""
    from ace.hooks.queries import get_failing_hook_entries_for_fix

    hooks = [HookEntry(command="flake8 src")]
    result = get_failing_hook_entries_for_fix(hooks, ["1", "2"])
    assert len(result) == 0


def test_get_failing_hook_entries_for_fix_entry_not_found() -> None:
    """Test that missing entry IDs are handled correctly."""
    from ace.hooks.queries import get_failing_hook_entries_for_fix

    hooks = [
        HookEntry(
            command="flake8 src",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="FAILED",
                    suffix="summary",
                    suffix_type="summarize_complete",
                )
            ],
        )
    ]
    result = get_failing_hook_entries_for_fix(hooks, ["2"])
    assert len(result) == 0


def test_get_failing_hook_entries_for_fix_passed_status() -> None:
    """Test that PASSED hooks are excluded from fix."""
    from ace.hooks.queries import get_failing_hook_entries_for_fix

    hooks = [
        HookEntry(
            command="flake8 src",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="PASSED",
                    suffix="summary",
                    suffix_type="summarize_complete",
                )
            ],
        )
    ]
    result = get_failing_hook_entries_for_fix(hooks, ["1"])
    assert len(result) == 0


# Tests for has_failing_hooks_for_fix
def test_has_failing_hooks_for_fix_true() -> None:
    """Test has_failing_hooks_for_fix returns True when eligible hooks exist."""
    from ace.hooks.queries import has_failing_hooks_for_fix

    hooks = [_make_hook(command="flake8 src", status="FAILED")]
    assert has_failing_hooks_for_fix(hooks) is True


def test_has_failing_hooks_for_fix_false_no_failing() -> None:
    """Test has_failing_hooks_for_fix returns False when no failing hooks."""
    from ace.hooks.queries import has_failing_hooks_for_fix

    hooks = [_make_hook(command="flake8 src", status="PASSED")]
    assert has_failing_hooks_for_fix(hooks) is False


def test_has_failing_hooks_for_fix_false_none() -> None:
    """Test has_failing_hooks_for_fix returns False for None input."""
    from ace.hooks.queries import has_failing_hooks_for_fix

    assert has_failing_hooks_for_fix(None) is False


def test_has_failing_hooks_for_fix_false_empty() -> None:
    """Test has_failing_hooks_for_fix returns False for empty list."""
    from ace.hooks.queries import has_failing_hooks_for_fix

    assert has_failing_hooks_for_fix([]) is False


def test_get_failing_hooks_for_fix_excludes_skip_fix_hook() -> None:
    """Test that hooks with ! prefix (skip_fix_hook) are excluded."""
    from ace.hooks.queries import get_failing_hooks_for_fix

    hook = HookEntry(
        command="!bb_hg_presubmit",
        status_lines=[
            HookStatusLine(
                commit_entry_num="1",
                timestamp="240601_123456",
                status="FAILED",
            )
        ],
    )
    failing = get_failing_hooks_for_fix([hook])
    assert len(failing) == 0


def test_get_failing_hook_entries_for_fix_excludes_skip_fix_hook() -> None:
    """Test that hooks with ! prefix (skip_fix_hook) are excluded from fix."""
    from ace.hooks.queries import get_failing_hook_entries_for_fix

    hook = HookEntry(
        command="!bb_hg_presubmit",
        status_lines=[
            HookStatusLine(
                commit_entry_num="3",
                timestamp="240601_123456",
                status="FAILED",
                suffix="summary text",
                suffix_type="summarize_complete",
            )
        ],
    )
    result = get_failing_hook_entries_for_fix([hook], ["3"])
    assert len(result) == 0


def test_has_failing_hooks_for_fix_false_skip_fix_hook() -> None:
    """Test has_failing_hooks_for_fix returns False for ! prefixed hooks."""
    from ace.hooks.queries import has_failing_hooks_for_fix

    hooks = [
        HookEntry(
            command="!bb_hg_presubmit",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="FAILED",
                )
            ],
        )
    ]
    assert has_failing_hooks_for_fix(hooks) is False
