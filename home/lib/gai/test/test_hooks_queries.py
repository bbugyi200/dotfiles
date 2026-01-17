"""Tests for hook query functions (fix-hook/summarize-hook workflows)."""

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


# Tests for _apply_hook_suffix_update
def test_apply_hook_suffix_update_basic() -> None:
    """Test applying suffix update to a hook's latest status line."""
    from ace.hooks.queries import _apply_hook_suffix_update

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
        ),
    ]
    updated = _apply_hook_suffix_update(
        hooks, "flake8 src", "my_suffix", suffix_type="error"
    )
    assert len(updated) == 1
    assert updated[0].status_lines is not None
    assert updated[0].status_lines[0].suffix == "my_suffix"
    assert updated[0].status_lines[0].suffix_type == "error"


def test_apply_hook_suffix_update_with_entry_id() -> None:
    """Test applying suffix update to a specific entry ID."""
    from ace.hooks.queries import _apply_hook_suffix_update

    hooks = [
        HookEntry(
            command="flake8 src",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_100000",
                    status="PASSED",
                ),
                HookStatusLine(
                    commit_entry_num="2",
                    timestamp="240601_110000",
                    status="FAILED",
                ),
            ],
        ),
    ]
    updated = _apply_hook_suffix_update(
        hooks, "flake8 src", "suffix_for_entry1", entry_id="1"
    )
    assert updated[0].status_lines is not None
    sl1 = [sl for sl in updated[0].status_lines if sl.commit_entry_num == "1"][0]
    assert sl1.suffix == "suffix_for_entry1"
    sl2 = [sl for sl in updated[0].status_lines if sl.commit_entry_num == "2"][0]
    assert sl2.suffix is None


def test_apply_hook_suffix_update_with_summary() -> None:
    """Test applying suffix update with summary."""
    from ace.hooks.queries import _apply_hook_suffix_update

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
        ),
    ]
    updated = _apply_hook_suffix_update(
        hooks,
        "flake8 src",
        "fix_attempt",
        suffix_type="summarize_complete",
        summary="Brief summary of the issue",
    )
    assert updated[0].status_lines is not None
    sl = updated[0].status_lines[0]
    assert sl.suffix == "fix_attempt"
    assert sl.suffix_type == "summarize_complete"
    assert sl.summary == "Brief summary of the issue"


def test_apply_hook_suffix_update_no_match() -> None:
    """Test that non-matching hooks are unchanged."""
    from ace.hooks.queries import _apply_hook_suffix_update

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
        ),
    ]
    updated = _apply_hook_suffix_update(hooks, "pytest tests", "suffix")
    assert updated[0].status_lines is not None
    assert updated[0].status_lines[0].suffix is None


def test_apply_hook_suffix_update_no_status_lines() -> None:
    """Test applying suffix to hook with no status lines."""
    from ace.hooks.queries import _apply_hook_suffix_update

    hooks = [HookEntry(command="flake8 src")]
    updated = _apply_hook_suffix_update(hooks, "flake8 src", "suffix")
    assert updated[0].command == "flake8 src"
    assert updated[0].status_lines is None


def test_apply_hook_suffix_update_multiple_hooks() -> None:
    """Test applying suffix update when there are multiple hooks."""
    from ace.hooks.queries import _apply_hook_suffix_update

    hooks = [
        HookEntry(
            command="flake8 src",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_100000",
                    status="FAILED",
                )
            ],
        ),
        HookEntry(
            command="pytest tests",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_110000",
                    status="FAILED",
                )
            ],
        ),
    ]
    updated = _apply_hook_suffix_update(hooks, "pytest tests", "my_suffix")
    assert updated[0].status_lines is not None
    assert updated[0].status_lines[0].suffix is None
    assert updated[1].status_lines is not None
    assert updated[1].status_lines[0].suffix == "my_suffix"


# Tests for _apply_clear_hook_suffix
def test_apply_clear_hook_suffix_basic() -> None:
    """Test clearing suffix from a hook's latest status line."""
    from ace.hooks.queries import _apply_clear_hook_suffix

    hooks = [
        HookEntry(
            command="flake8 src",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="FAILED",
                    suffix="some_suffix",
                )
            ],
        ),
    ]
    updated = _apply_clear_hook_suffix(hooks, "flake8 src")
    assert updated[0].status_lines is not None
    assert updated[0].status_lines[0].suffix is None


def test_apply_clear_hook_suffix_multiple_status_lines() -> None:
    """Test that only the latest status line's suffix is cleared."""
    from ace.hooks.queries import _apply_clear_hook_suffix

    hooks = [
        HookEntry(
            command="flake8 src",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_100000",
                    status="PASSED",
                    suffix="old_suffix",
                ),
                HookStatusLine(
                    commit_entry_num="2",
                    timestamp="240601_110000",
                    status="FAILED",
                    suffix="latest_suffix",
                ),
            ],
        ),
    ]
    updated = _apply_clear_hook_suffix(hooks, "flake8 src")
    assert updated[0].status_lines is not None
    sl1 = [sl for sl in updated[0].status_lines if sl.commit_entry_num == "1"][0]
    assert sl1.suffix == "old_suffix"
    sl2 = [sl for sl in updated[0].status_lines if sl.commit_entry_num == "2"][0]
    assert sl2.suffix is None


def test_apply_clear_hook_suffix_no_match() -> None:
    """Test that non-matching hooks are unchanged."""
    from ace.hooks.queries import _apply_clear_hook_suffix

    hooks = [
        HookEntry(
            command="flake8 src",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="FAILED",
                    suffix="should_remain",
                )
            ],
        ),
    ]
    updated = _apply_clear_hook_suffix(hooks, "pytest tests")
    assert updated[0].status_lines is not None
    assert updated[0].status_lines[0].suffix == "should_remain"


def test_apply_clear_hook_suffix_no_suffix() -> None:
    """Test clearing when there's no suffix to clear."""
    from ace.hooks.queries import _apply_clear_hook_suffix

    hooks = [
        HookEntry(
            command="flake8 src",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="FAILED",
                    suffix=None,
                )
            ],
        ),
    ]
    updated = _apply_clear_hook_suffix(hooks, "flake8 src")
    assert updated[0].status_lines is not None
    assert updated[0].status_lines[0].suffix is None


def test_apply_clear_hook_suffix_no_status_lines() -> None:
    """Test clearing suffix on hook with no status lines."""
    from ace.hooks.queries import _apply_clear_hook_suffix

    hooks = [HookEntry(command="flake8 src")]
    updated = _apply_clear_hook_suffix(hooks, "flake8 src")
    assert updated[0].command == "flake8 src"
    assert updated[0].status_lines is None


def test_apply_clear_hook_suffix_multiple_hooks() -> None:
    """Test clearing suffix when there are multiple hooks."""
    from ace.hooks.queries import _apply_clear_hook_suffix

    hooks = [
        HookEntry(
            command="flake8 src",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_100000",
                    status="FAILED",
                    suffix="suffix_to_keep",
                )
            ],
        ),
        HookEntry(
            command="pytest tests",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_110000",
                    status="FAILED",
                    suffix="suffix_to_clear",
                )
            ],
        ),
    ]
    updated = _apply_clear_hook_suffix(hooks, "pytest tests")
    assert updated[0].status_lines is not None
    assert updated[0].status_lines[0].suffix == "suffix_to_keep"
    assert updated[1].status_lines is not None
    assert updated[1].status_lines[0].suffix is None


# Tests for is_proposal_entry
def test_is_proposal_entry_true() -> None:
    """Test that entries ending with a letter are proposals."""
    from ace.hooks.history import is_proposal_entry

    assert is_proposal_entry("1a") is True
    assert is_proposal_entry("2b") is True
    assert is_proposal_entry("10c") is True
    assert is_proposal_entry("99z") is True


def test_is_proposal_entry_false() -> None:
    """Test that entries ending with a digit are not proposals."""
    from ace.hooks.history import is_proposal_entry

    assert is_proposal_entry("1") is False
    assert is_proposal_entry("2") is False
    assert is_proposal_entry("10") is False
    assert is_proposal_entry("99") is False


def test_is_proposal_entry_empty() -> None:
    """Test that empty string is not a proposal."""
    from ace.hooks.history import is_proposal_entry

    assert is_proposal_entry("") is False


# Tests for _is_test_target_hook
def test_is_test_target_hook_true() -> None:
    """Test that bb_rabbit_test commands are identified as test target hooks."""
    from ace.hooks.queries import _is_test_target_hook

    hook = HookEntry(command="bb_rabbit_test //foo:test")
    assert _is_test_target_hook(hook) is True


def test_is_test_target_hook_false() -> None:
    """Test that non-test commands are not identified as test target hooks."""
    from ace.hooks.queries import _is_test_target_hook

    hook = HookEntry(command="flake8 src")
    assert _is_test_target_hook(hook) is False

    hook2 = HookEntry(command="pytest tests")
    assert _is_test_target_hook(hook2) is False


# Tests for _create_test_target_hook
def test_create_test_target_hook() -> None:
    """Test creating a test target hook from a target string."""
    from ace.hooks.queries import _create_test_target_hook

    hook = _create_test_target_hook("//foo/bar:test")
    assert hook.command == "bb_rabbit_test //foo/bar:test"
    assert hook.status_lines is None


# Tests for _hook_has_fix_excluded_suffix
def test_hook_has_fix_excluded_suffix_true() -> None:
    """Test that hooks with suffix are identified as excluded."""
    from ace.hooks.queries import _hook_has_fix_excluded_suffix

    hook = HookEntry(
        command="flake8 src",
        status_lines=[
            HookStatusLine(
                commit_entry_num="1",
                timestamp="240601_123456",
                status="FAILED",
                suffix="some_suffix",
            )
        ],
    )
    assert _hook_has_fix_excluded_suffix(hook) is True


def test_hook_has_fix_excluded_suffix_false_no_suffix() -> None:
    """Test that hooks without suffix are not excluded."""
    from ace.hooks.queries import _hook_has_fix_excluded_suffix

    hook = HookEntry(
        command="flake8 src",
        status_lines=[
            HookStatusLine(
                commit_entry_num="1",
                timestamp="240601_123456",
                status="FAILED",
            )
        ],
    )
    assert _hook_has_fix_excluded_suffix(hook) is False


def test_hook_has_fix_excluded_suffix_false_no_status_lines() -> None:
    """Test that hooks with no status_lines are not excluded."""
    from ace.hooks.queries import _hook_has_fix_excluded_suffix

    hook = HookEntry(command="flake8 src")
    assert _hook_has_fix_excluded_suffix(hook) is False
