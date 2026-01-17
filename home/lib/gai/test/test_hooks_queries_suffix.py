"""Tests for suffix operations and utility query functions."""

from ace.changespec import (
    HookEntry,
    HookStatusLine,
)


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
