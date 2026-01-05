"""Tests for hook operations, state checking, and file updates."""

import os
import tempfile

from ace.changespec import (
    HookEntry,
    HookStatusLine,
)
from ace.hooks import (
    contract_test_target_command,
    format_timestamp_display,
    get_failing_test_target_hooks,
    get_hook_output_path,
    get_test_target_from_hook,
    has_failing_test_target_hooks,
    has_running_hooks,
    hook_needs_run,
    update_changespec_hooks_field,
)
from ace.hooks.execution import (
    _format_hooks_field,
)
from ace.hooks.queries import expand_test_target_shorthand
from gai_utils import get_gai_directory


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


# Tests for hook_needs_run
def test_hook_needs_run_never_run() -> None:
    """Test that hook needs run if never run before."""
    hook = HookEntry(command="flake8 src")
    # Hook needs run if no status line exists for history entry 1
    assert hook_needs_run(hook, "1") is True


def test_hook_needs_run_no_history_entry() -> None:
    """Test that hook doesn't need run if no history entry number."""
    hook = HookEntry(command="flake8 src")
    # No history entry means no run needed
    assert hook_needs_run(hook, None) is False

    hook2 = _make_hook(
        command="flake8 src",
        commit_entry_num="1",
        timestamp="240601123456",
        status="PASSED",
    )
    assert hook_needs_run(hook2, None) is False  # No history entry


def test_hook_needs_run_stale() -> None:
    """Test that hook needs run if no status line for current history entry."""
    # Hook has status line for history entry 1, but we want entry 2
    hook = _make_hook(
        command="flake8 src",
        commit_entry_num="1",
        timestamp="240601100000",
        status="PASSED",
    )
    assert hook_needs_run(hook, "2") is True  # No status for entry 2


def test_hook_needs_run_up_to_date() -> None:
    """Test that hook doesn't need run if status line exists for current entry."""
    hook = _make_hook(
        command="flake8 src",
        commit_entry_num="1",
        timestamp="240601130000",
        status="PASSED",
    )
    assert hook_needs_run(hook, "1") is False  # Has status for entry 1


def test_hook_needs_run_proposal_entry() -> None:
    """Test hook needs run distinguishes between regular and proposal entries."""
    # Hook has status line for entry "1", but we want entry "1a" (proposal)
    hook = _make_hook(
        command="flake8 src",
        commit_entry_num="1",
        timestamp="240601100000",
        status="PASSED",
    )
    assert hook_needs_run(hook, "1a") is True  # No status for entry 1a
    assert hook_needs_run(hook, "1") is False  # Has status for entry 1


def test_hook_needs_run_same_entry() -> None:
    """Test that hook doesn't need run if status line exists for same entry."""
    hook = _make_hook(
        command="flake8 src",
        commit_entry_num="2",
        timestamp="240601123456",
        status="PASSED",
    )
    assert hook_needs_run(hook, "2") is False  # Has status for entry 2


# Tests for test target hook functions
def test_get_test_target_from_hook_valid() -> None:
    """Test extracting test target from a valid test target hook."""
    hook = _make_hook(command="bb_rabbit_test //foo/bar:test1", status="PASSED")
    assert get_test_target_from_hook(hook) == "//foo/bar:test1"


def test_get_test_target_from_hook_with_spaces() -> None:
    """Test extracting test target from hook with extra spaces."""
    hook = _make_hook(command="bb_rabbit_test  //foo/bar:test1 ", status="PASSED")
    assert get_test_target_from_hook(hook) == "//foo/bar:test1"


def test_get_test_target_from_hook_not_test_target() -> None:
    """Test that non-test target hook returns None."""
    hook = _make_hook(command="flake8 src", status="PASSED")
    assert get_test_target_from_hook(hook) is None


def test_get_failing_test_target_hooks_mixed() -> None:
    """Test getting failing test target hooks from mixed list."""
    hooks = [
        _make_hook(command="bb_rabbit_test //foo:test1", status="FAILED"),
        _make_hook(command="bb_rabbit_test //foo:test2", status="PASSED"),
        _make_hook(command="flake8 src", status="FAILED"),
        _make_hook(command="bb_rabbit_test //bar:test3", status="FAILED"),
    ]
    failing = get_failing_test_target_hooks(hooks)
    assert len(failing) == 2
    assert failing[0].command == "bb_rabbit_test //foo:test1"
    assert failing[1].command == "bb_rabbit_test //bar:test3"


def test_get_failing_test_target_hooks_none_failing() -> None:
    """Test that empty list is returned when no failing test target hooks."""
    hooks = [
        _make_hook(command="bb_rabbit_test //foo:test1", status="PASSED"),
        _make_hook(command="flake8 src", status="FAILED"),
    ]
    failing = get_failing_test_target_hooks(hooks)
    assert failing == []


def test_get_failing_test_target_hooks_with_zombie() -> None:
    """Test that only FAILED test targets are returned, not ZOMBIE."""
    hooks = [
        _make_hook(command="bb_rabbit_test //foo:test1", status="FAILED"),
        _make_hook(command="bb_rabbit_test //foo:test2", status="ZOMBIE"),
        _make_hook(command="bb_rabbit_test //foo:test3", status="RUNNING"),
    ]
    failing = get_failing_test_target_hooks(hooks)
    # Only FAILED test target hooks should be returned
    assert len(failing) == 1
    assert failing[0].command == "bb_rabbit_test //foo:test1"


# Tests for has_failing_test_target_hooks
def test_has_failing_test_target_hooks_true() -> None:
    """Test has_failing_test_target_hooks returns True when failing hooks exist."""
    hooks = [
        _make_hook(command="bb_rabbit_test //foo:test1", status="FAILED"),
        _make_hook(command="bb_rabbit_test //foo:test2", status="PASSED"),
    ]
    assert has_failing_test_target_hooks(hooks) is True


def test_has_failing_test_target_hooks_false() -> None:
    """Test has_failing_test_target_hooks returns False when no failing hooks."""
    hooks = [
        _make_hook(command="bb_rabbit_test //foo:test1", status="PASSED"),
        _make_hook(command="flake8 src", status="FAILED"),
    ]
    assert has_failing_test_target_hooks(hooks) is False


def test_has_failing_test_target_hooks_none() -> None:
    """Test has_failing_test_target_hooks returns False for None input."""
    assert has_failing_test_target_hooks(None) is False


def test_has_failing_test_target_hooks_empty() -> None:
    """Test has_failing_test_target_hooks returns False for empty list."""
    assert has_failing_test_target_hooks([]) is False


# Tests for has_running_hooks
def test_has_running_hooks_true() -> None:
    """Test has_running_hooks returns True when running hooks exist."""
    hooks = [
        _make_hook(command="flake8 src", status="RUNNING", timestamp="240601123456"),
        _make_hook(command="mypy src", status="PASSED"),
    ]
    assert has_running_hooks(hooks) is True


def test_has_running_hooks_false() -> None:
    """Test has_running_hooks returns False when no running hooks."""
    hooks = [
        _make_hook(command="flake8 src", status="PASSED"),
        _make_hook(command="mypy src", status="FAILED"),
    ]
    assert has_running_hooks(hooks) is False


def test_has_running_hooks_none() -> None:
    """Test has_running_hooks returns False for None input."""
    assert has_running_hooks(None) is False


def test_has_running_hooks_empty() -> None:
    """Test has_running_hooks returns False for empty list."""
    assert has_running_hooks([]) is False


# Tests for get_hook_output_path
def test_get_hook_output_path_basic() -> None:
    """Test get_hook_output_path returns correct path."""
    path = get_hook_output_path("my_feature", "240601_123456")
    hooks_dir = get_gai_directory("hooks")
    assert path == os.path.join(hooks_dir, "my_feature-240601_123456.txt")


def test_get_hook_output_path_special_chars() -> None:
    """Test get_hook_output_path sanitizes special characters."""
    path = get_hook_output_path("my/feature-test", "240601_123456")
    hooks_dir = get_gai_directory("hooks")
    # Special chars should be replaced with underscore
    assert path == os.path.join(hooks_dir, "my_feature_test-240601_123456.txt")


# Tests for format_timestamp_display
def test_format_timestamp_display_basic() -> None:
    """Test formatting timestamp for display."""
    result = format_timestamp_display("240601_123456")
    # Format: [YYmmdd_HHMMSS]
    assert result == "[240601_123456]"


def test_format_timestamp_display_short() -> None:
    """Test formatting short timestamp."""
    result = format_timestamp_display("2406")
    # Should handle short timestamps gracefully
    assert "[2406]" == result


# Tests for _format_hooks_field
def test_format_hooks_field_basic() -> None:
    """Test formatting hooks field for writing."""
    hooks = [
        HookEntry(command="flake8 src"),
        _make_hook(
            command="pytest tests",
            timestamp="240601_123456",
            status="PASSED",
            duration="1m23s",
        ),
    ]
    result = _format_hooks_field(hooks)
    # Result is a list of lines
    result_str = "".join(result)
    assert "HOOKS:" in result_str
    assert "  flake8 src" in result_str
    assert "  pytest tests" in result_str
    # Format includes (N) prefix and wrapped timestamp
    assert "(1) [240601_123456] PASSED (1m23s)" in result_str


def test_format_hooks_field_running_no_duration() -> None:
    """Test formatting hooks field with RUNNING status (no duration)."""
    hooks = [
        _make_hook(
            command="pytest tests",
            timestamp="240601_123456",
            status="RUNNING",
            duration=None,
        ),
    ]
    result = _format_hooks_field(hooks)
    result_str = "".join(result)
    assert "  pytest tests" in result_str
    # Format includes (N) prefix and wrapped timestamp
    assert "(1) [240601_123456] RUNNING" in result_str
    # Should not have duration
    assert "RUNNING (" not in result_str


def test_format_hooks_field_empty() -> None:
    """Test formatting empty hooks list."""
    result = _format_hooks_field([])
    assert result == []


# Tests for update_changespec_hooks_field
def test_update_changespec_hooks_field_basic() -> None:
    """Test updating hooks field in a project file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(
            """## ChangeSpec
NAME: test_cl
DESCRIPTION:
  Test description
STATUS: Drafted
HOOKS:
  old_command
      | (1) [240601_100000] PASSED (1m0s)
"""
        )
        f.flush()
        file_path = f.name

    try:
        # Update hooks
        new_hooks = [
            _make_hook(
                command="new_command",
                timestamp="240601_123456",
                status="FAILED",
                duration="2m30s",
            ),
        ]
        success = update_changespec_hooks_field(file_path, "test_cl", new_hooks)
        assert success is True

        # Verify the file was updated
        with open(file_path) as f:
            content = f.read()
        assert "new_command" in content
        # Format with (N) prefix and wrapped timestamp
        assert "(1) [240601_123456] FAILED (2m30s)" in content
        # Old hook should be gone
        assert "old_command" not in content
    finally:
        os.unlink(file_path)


def test_update_changespec_hooks_field_clear_status() -> None:
    """Test clearing hook status (for rerun)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(
            """## ChangeSpec
NAME: test_cl
DESCRIPTION:
  Test description
STATUS: Drafted
HOOKS:
  my_command
      | (1) [240601_100000] FAILED (1m0s)
"""
        )
        f.flush()
        file_path = f.name

    try:
        # Clear hook status (simulating rerun) - no status lines
        new_hooks = [HookEntry(command="my_command")]
        success = update_changespec_hooks_field(file_path, "test_cl", new_hooks)
        assert success is True

        # Verify status was cleared
        with open(file_path) as f:
            content = f.read()
        assert "my_command" in content
        # Status line should be gone
        assert "[240601_100000]" not in content
        assert "FAILED" not in content
    finally:
        os.unlink(file_path)


def test_update_changespec_hooks_field_delete_hook() -> None:
    """Test deleting a hook entirely."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(
            """## ChangeSpec
NAME: test_cl
DESCRIPTION:
  Test description
STATUS: Drafted
HOOKS:
  hook1
      | (1) [240601_100000] PASSED (1m0s)
  hook2
      | (1) [240601_100000] FAILED (2m0s)
"""
        )
        f.flush()
        file_path = f.name

    try:
        # Delete hook1, keep hook2
        new_hooks = [
            _make_hook(
                command="hook2",
                timestamp="240601100000",
                status="FAILED",
                duration="2m0s",
            ),
        ]
        success = update_changespec_hooks_field(file_path, "test_cl", new_hooks)
        assert success is True

        # Verify hook1 was deleted
        with open(file_path) as f:
            content = f.read()
        assert "hook1" not in content
        assert "hook2" in content
    finally:
        os.unlink(file_path)


# Tests for expand_test_target_shorthand
def test_expand_test_target_shorthand_basic() -> None:
    """Test expansion of basic shorthand syntax."""
    assert expand_test_target_shorthand("//foo:test") == "bb_rabbit_test //foo:test"
    assert (
        expand_test_target_shorthand("//bar:baz_test")
        == "bb_rabbit_test //bar:baz_test"
    )


def test_expand_test_target_shorthand_with_bang_prefix() -> None:
    """Test expansion with ! prefix."""
    assert expand_test_target_shorthand("!//foo:test") == "!bb_rabbit_test //foo:test"


def test_expand_test_target_shorthand_with_dollar_prefix() -> None:
    """Test expansion with $ prefix."""
    assert expand_test_target_shorthand("$//foo:test") == "$bb_rabbit_test //foo:test"


def test_expand_test_target_shorthand_with_combined_prefixes() -> None:
    """Test expansion with combined !$ prefixes."""
    assert expand_test_target_shorthand("!$//foo:test") == "!$bb_rabbit_test //foo:test"


def test_expand_test_target_shorthand_already_expanded() -> None:
    """Test that already expanded commands are unchanged."""
    assert (
        expand_test_target_shorthand("bb_rabbit_test //foo:test")
        == "bb_rabbit_test //foo:test"
    )


def test_expand_test_target_shorthand_non_test_command() -> None:
    """Test that non-test commands are unchanged."""
    assert expand_test_target_shorthand("some_other_command") == "some_other_command"
    assert expand_test_target_shorthand("flake8 src") == "flake8 src"


# Tests for contract_test_target_command
def test_contract_test_target_command_basic() -> None:
    """Test contraction of basic test target command."""
    assert contract_test_target_command("bb_rabbit_test //foo:test") == "//foo:test"
    assert (
        contract_test_target_command("bb_rabbit_test //bar:baz_test")
        == "//bar:baz_test"
    )


def test_contract_test_target_command_with_bang_prefix() -> None:
    """Test contraction with ! prefix."""
    assert contract_test_target_command("!bb_rabbit_test //foo:test") == "!//foo:test"


def test_contract_test_target_command_with_dollar_prefix() -> None:
    """Test contraction with $ prefix."""
    assert contract_test_target_command("$bb_rabbit_test //foo:test") == "$//foo:test"


def test_contract_test_target_command_with_combined_prefixes() -> None:
    """Test contraction with combined !$ prefixes."""
    assert contract_test_target_command("!$bb_rabbit_test //foo:test") == "!$//foo:test"


def test_contract_test_target_command_already_contracted() -> None:
    """Test that already contracted commands are unchanged."""
    assert contract_test_target_command("//foo:test") == "//foo:test"


def test_contract_test_target_command_non_double_slash_target() -> None:
    """Test that bb_rabbit_test without // target is not contracted."""
    # If target doesn't start with //, don't contract
    assert (
        contract_test_target_command("bb_rabbit_test some_target")
        == "bb_rabbit_test some_target"
    )


def test_contract_test_target_command_non_test_command() -> None:
    """Test that non-test commands are unchanged."""
    assert contract_test_target_command("some_other_command") == "some_other_command"
    assert contract_test_target_command("flake8 src") == "flake8 src"


# Tests for round-trip expansion and contraction
def test_expand_contract_roundtrip() -> None:
    """Test that expanding then contracting returns the original shorthand."""
    original = "//foo:test"
    expanded = expand_test_target_shorthand(original)
    contracted = contract_test_target_command(expanded)
    assert contracted == original


def test_expand_contract_roundtrip_with_prefix() -> None:
    """Test round-trip with ! prefix."""
    original = "!//foo:test"
    expanded = expand_test_target_shorthand(original)
    contracted = contract_test_target_command(expanded)
    assert contracted == original
