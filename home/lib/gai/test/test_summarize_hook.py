"""Tests for summarize-hook workflow eligibility and behavior."""

from ace.changespec import HookEntry, HookStatusLine
from ace.hooks import get_failing_hooks_for_fix
from ace.hooks.queries import get_failing_hooks_for_summarize


def _make_hook_with_status(
    command: str,
    commit_entry_num: str,
    status: str,
    suffix: str | None = None,
) -> HookEntry:
    """Helper to create a HookEntry with a specific status line."""
    status_line = HookStatusLine(
        commit_entry_num=commit_entry_num,
        timestamp="241228_120000",
        status=status,
        duration="1m23s",
        suffix=suffix,
    )
    return HookEntry(command=command, status_lines=[status_line])


def test_get_failing_hooks_for_summarize_proposal_entry() -> None:
    """Test that proposal entry FAILED hooks are eligible for summarize."""
    hook = _make_hook_with_status(
        command="make test",
        commit_entry_num="2a",  # Proposal entry
        status="FAILED",
        suffix=None,
    )
    result = get_failing_hooks_for_summarize([hook])
    assert len(result) == 1
    assert result[0].command == "make test"


def test_get_failing_hooks_for_summarize_proposal_entry_letter_b() -> None:
    """Test that proposal entries with letter 'b' are also eligible."""
    hook = _make_hook_with_status(
        command="make lint",
        commit_entry_num="3b",  # Proposal entry with 'b'
        status="FAILED",
        suffix=None,
    )
    result = get_failing_hooks_for_summarize([hook])
    assert len(result) == 1
    assert result[0].command == "make lint"


def test_get_failing_hooks_for_summarize_regular_entry() -> None:
    """Test that regular entry FAILED hooks are NOT eligible for summarize."""
    hook = _make_hook_with_status(
        command="make test",
        commit_entry_num="2",  # Regular entry (no letter)
        status="FAILED",
        suffix=None,
    )
    result = get_failing_hooks_for_summarize([hook])
    assert len(result) == 0


def test_get_failing_hooks_for_summarize_with_suffix() -> None:
    """Test that hooks with existing suffix are NOT eligible for summarize."""
    hook = _make_hook_with_status(
        command="make test",
        commit_entry_num="2a",
        status="FAILED",
        suffix="Hook Command Failed",  # Already has suffix
    )
    result = get_failing_hooks_for_summarize([hook])
    assert len(result) == 0


def test_get_failing_hooks_for_summarize_with_timestamp_suffix() -> None:
    """Test that hooks with timestamp suffix (running workflow) are NOT eligible."""
    hook = _make_hook_with_status(
        command="make test",
        commit_entry_num="2a",
        status="FAILED",
        suffix="241228_120500",  # Timestamp suffix = workflow running
    )
    result = get_failing_hooks_for_summarize([hook])
    assert len(result) == 0


def test_get_failing_hooks_for_summarize_passed_status() -> None:
    """Test that PASSED hooks are NOT eligible for summarize."""
    hook = _make_hook_with_status(
        command="make test",
        commit_entry_num="2a",
        status="PASSED",
        suffix=None,
    )
    result = get_failing_hooks_for_summarize([hook])
    assert len(result) == 0


def test_get_failing_hooks_for_summarize_running_status() -> None:
    """Test that RUNNING hooks are NOT eligible for summarize."""
    hook = _make_hook_with_status(
        command="make test",
        commit_entry_num="2a",
        status="RUNNING",
        suffix=None,
    )
    result = get_failing_hooks_for_summarize([hook])
    assert len(result) == 0


def test_get_failing_hooks_for_fix_excludes_proposal_entries() -> None:
    """Test that proposal entry hooks are excluded from fix-hook."""
    hook = _make_hook_with_status(
        command="make test",
        commit_entry_num="2a",  # Proposal entry
        status="FAILED",
        suffix=None,
    )
    result = get_failing_hooks_for_fix([hook])
    assert len(result) == 0


def test_get_failing_hooks_for_fix_regular_entry() -> None:
    """Test that regular entry FAILED hooks are eligible for fix-hook."""
    hook = _make_hook_with_status(
        command="make test",
        commit_entry_num="2",  # Regular entry
        status="FAILED",
        suffix=None,
    )
    result = get_failing_hooks_for_fix([hook])
    assert len(result) == 1
    assert result[0].command == "make test"


def test_get_failing_hooks_for_fix_with_suffix() -> None:
    """Test that hooks with existing suffix are NOT eligible for fix-hook."""
    hook = _make_hook_with_status(
        command="make test",
        commit_entry_num="2",
        status="FAILED",
        suffix="241228_120500",  # Has suffix
    )
    result = get_failing_hooks_for_fix([hook])
    assert len(result) == 0


def test_mixed_hooks_correct_separation() -> None:
    """Test that mixed hooks are correctly separated between fix and summarize."""
    regular_hook = _make_hook_with_status(
        command="make test",
        commit_entry_num="2",  # Regular entry
        status="FAILED",
        suffix=None,
    )
    proposal_hook = _make_hook_with_status(
        command="make lint",
        commit_entry_num="2a",  # Proposal entry
        status="FAILED",
        suffix=None,
    )
    hooks = [regular_hook, proposal_hook]

    fix_result = get_failing_hooks_for_fix(hooks)
    summarize_result = get_failing_hooks_for_summarize(hooks)

    # Regular hook goes to fix-hook
    assert len(fix_result) == 1
    assert fix_result[0].command == "make test"

    # Proposal hook goes to summarize-hook
    assert len(summarize_result) == 1
    assert summarize_result[0].command == "make lint"
