"""Tests for timestamp handling, suffix detection, and hook command prefixes."""

from ace.changespec import HookEntry
from ace.hooks import (
    calculate_duration_from_timestamps,
    generate_timestamp,
    hook_needs_run,
    is_suffix_stale,
    is_timestamp_suffix,
)


# Tests for is_timestamp_suffix
def test_is_timestamp_suffix_new_format() -> None:
    """Test is_timestamp_suffix returns True for YYmmdd_HHMMSS format."""
    assert is_timestamp_suffix("241225_120000") is True
    assert is_timestamp_suffix("250101_235959") is True


def test_is_timestamp_suffix_old_format() -> None:
    """Test is_timestamp_suffix returns True for YYmmddHHMMSS format."""
    assert is_timestamp_suffix("241225120000") is True
    assert is_timestamp_suffix("250101235959") is True


def test_is_timestamp_suffix_proposal_id() -> None:
    """Test is_timestamp_suffix returns False for proposal IDs."""
    assert is_timestamp_suffix("2a") is False
    assert is_timestamp_suffix("1b") is False
    assert is_timestamp_suffix("3") is False
    assert is_timestamp_suffix("10c") is False


def test_is_timestamp_suffix_exclamation() -> None:
    """Test is_timestamp_suffix returns False for '!' suffix."""
    assert is_timestamp_suffix("!") is False


def test_is_timestamp_suffix_none() -> None:
    """Test is_timestamp_suffix returns False for None."""
    assert is_timestamp_suffix(None) is False


# Tests for is_suffix_stale
def test_is_suffix_stale_not_timestamp() -> None:
    """Test is_suffix_stale returns False for non-timestamp suffixes."""
    assert is_suffix_stale(None) is False
    assert is_suffix_stale("!") is False
    assert is_suffix_stale("2a") is False
    assert is_suffix_stale("1b") is False


def test_is_suffix_stale_recent_timestamp() -> None:
    """Test is_suffix_stale returns False for recent timestamps."""
    # Use generate_timestamp() to get a fresh timestamp
    recent = generate_timestamp()
    assert is_suffix_stale(recent) is False


# Tests for generate_timestamp format
def test_generate_timestamp_format() -> None:
    """Test generate_timestamp returns YYmmdd_HHMMSS format (13 chars, with underscore)."""
    ts = generate_timestamp()
    # Should be 13 chars with underscore at position 6
    assert len(ts) == 13
    assert ts[6] == "_"
    assert ts[:6].isdigit()
    assert ts[7:].isdigit()


# Tests for backward compatible timestamp parsing
def test_calculate_duration_from_timestamps_new_format() -> None:
    """Test calculate_duration_from_timestamps handles new format with underscore."""
    # 1 hour apart
    duration = calculate_duration_from_timestamps("241225_120000", "241225_130000")
    assert duration == 3600.0


def test_calculate_duration_from_timestamps_old_format() -> None:
    """Test calculate_duration_from_timestamps handles old format without underscore."""
    # 1 hour apart
    duration = calculate_duration_from_timestamps("241225120000", "241225130000")
    assert duration == 3600.0


def test_calculate_duration_from_timestamps_mixed_formats() -> None:
    """Test calculate_duration_from_timestamps handles mixed formats."""
    # Old start, new end
    duration = calculate_duration_from_timestamps("241225120000", "241225_130000")
    assert duration == 3600.0
    # New start, old end
    duration = calculate_duration_from_timestamps("241225_120000", "241225130000")
    assert duration == 3600.0


# Tests for HookEntry prefix properties
def test_hook_entry_skip_fix_hook_with_exclamation() -> None:
    """Test skip_fix_hook is True when command starts with '!'."""
    hook = HookEntry(command="!some_command")
    assert hook.skip_fix_hook is True
    assert hook.skip_proposal_runs is False


def test_hook_entry_skip_proposal_runs_with_dollar() -> None:
    """Test skip_proposal_runs is True when command has '$' prefix."""
    hook = HookEntry(command="$some_command")
    assert hook.skip_proposal_runs is True
    assert hook.skip_fix_hook is False


def test_hook_entry_combined_prefixes() -> None:
    """Test both prefixes work together as '!$'."""
    hook = HookEntry(command="!$some_command")
    assert hook.skip_fix_hook is True
    assert hook.skip_proposal_runs is True
    assert hook.display_command == "some_command"
    assert hook.run_command == "some_command"


def test_hook_entry_display_command_strips_all_prefixes() -> None:
    """Test display_command strips both '!' and '$' prefixes."""
    assert HookEntry(command="!cmd").display_command == "cmd"
    assert HookEntry(command="$cmd").display_command == "cmd"
    assert HookEntry(command="!$cmd").display_command == "cmd"
    assert HookEntry(command="cmd").display_command == "cmd"


def test_hook_entry_run_command_strips_all_prefixes() -> None:
    """Test run_command strips both '!' and '$' prefixes."""
    assert HookEntry(command="!cmd").run_command == "cmd"
    assert HookEntry(command="$cmd").run_command == "cmd"
    assert HookEntry(command="!$cmd").run_command == "cmd"
    assert HookEntry(command="cmd").run_command == "cmd"


def test_hook_entry_no_prefix() -> None:
    """Test hook without any prefix."""
    hook = HookEntry(command="some_command")
    assert hook.skip_fix_hook is False
    assert hook.skip_proposal_runs is False
    assert hook.display_command == "some_command"
    assert hook.run_command == "some_command"


def test_hook_needs_run_skips_dollar_prefix_for_proposals() -> None:
    """Test that '$' prefixed hooks are skipped for proposal entries."""
    # Hook with $ prefix should be skipped for proposal entries
    hook_with_dollar = HookEntry(command="$some_command")
    assert hook_needs_run(hook_with_dollar, "1a") is False
    # But should run for regular entries
    assert hook_needs_run(hook_with_dollar, "1") is True


def test_hook_needs_run_runs_exclamation_prefix_for_proposals() -> None:
    """Test that '!' prefixed hooks (without $) run for proposal entries."""
    # Hook with only ! prefix should run for proposal entries
    hook_with_exclamation = HookEntry(command="!some_command")
    assert hook_needs_run(hook_with_exclamation, "1a") is True
    assert hook_needs_run(hook_with_exclamation, "1") is True


def test_hook_needs_run_skips_combined_prefix_for_proposals() -> None:
    """Test that '!$' prefixed hooks are skipped for proposal entries."""
    # Hook with !$ prefix should be skipped for proposal entries (due to $)
    hook_with_both = HookEntry(command="!$some_command")
    assert hook_needs_run(hook_with_both, "1a") is False
    # But should run for regular entries
    assert hook_needs_run(hook_with_both, "1") is True
