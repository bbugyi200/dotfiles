"""Test target hook utilities - helpers, queries, and mutations."""

from ..changespec import HookEntry, changespec_lock
from .execution import update_changespec_hooks_field, write_hooks_unlocked

# Test target hook helpers
TEST_TARGET_HOOK_PREFIX = "bb_rabbit_test "
TEST_TARGET_SHORTHAND_PREFIX = "//"


def expand_test_target_shorthand(command: str) -> str:
    """Expand shorthand //target to bb_rabbit_test //target.

    Handles ! and $ prefixes (e.g., "!//foo" → "!bb_rabbit_test //foo").

    Args:
        command: The hook command string (may have "!" or "$" prefix).

    Returns:
        Expanded command if shorthand detected, otherwise unchanged command.
    """
    # Extract prefix chars (!, $)
    prefix = ""
    for char in command:
        if char in "!$":
            prefix += char
        else:
            break
    cmd = command[len(prefix) :]

    if cmd.startswith(TEST_TARGET_SHORTHAND_PREFIX):
        return f"{prefix}{TEST_TARGET_HOOK_PREFIX}{cmd}"
    return command


def contract_test_target_command(command: str) -> str:
    """Contract bb_rabbit_test //target to //target.

    Handles ! and $ prefixes (e.g., "!bb_rabbit_test //foo" → "!//foo").

    Args:
        command: The hook command string (may have "!" or "$" prefix).

    Returns:
        Contracted command using shorthand, or unchanged if not a test target hook.
    """
    prefix = ""
    for char in command:
        if char in "!$":
            prefix += char
        else:
            break
    cmd = command[len(prefix) :]

    if cmd.startswith(TEST_TARGET_HOOK_PREFIX):
        target = cmd[len(TEST_TARGET_HOOK_PREFIX) :]
        if target.startswith(TEST_TARGET_SHORTHAND_PREFIX):
            return f"{prefix}{target}"
    return command


def _is_test_target_hook(hook: HookEntry) -> bool:
    """Check if a hook is a test target hook."""
    return hook.command.startswith(TEST_TARGET_HOOK_PREFIX)


def get_test_target_from_hook(hook: HookEntry) -> str | None:
    """Extract the test target from a test target hook command."""
    if not _is_test_target_hook(hook):
        return None
    return hook.command[len(TEST_TARGET_HOOK_PREFIX) :].strip()


def _create_test_target_hook(test_target: str) -> HookEntry:
    """Create a new test target hook entry for a given target."""
    return HookEntry(command=f"{TEST_TARGET_HOOK_PREFIX}{test_target}")


def get_failing_test_target_hooks(hooks: list[HookEntry]) -> list[HookEntry]:
    """Get all test target hooks that have FAILED status."""
    return [
        hook
        for hook in hooks
        if _is_test_target_hook(hook)
        and hook.latest_status_line
        and hook.latest_status_line.status == "FAILED"
    ]


def has_failing_test_target_hooks(hooks: list[HookEntry] | None) -> bool:
    """Check if there are any test target hooks with FAILED status."""
    if not hooks:
        return False
    return len(get_failing_test_target_hooks(hooks)) > 0


def add_test_target_hooks_to_changespec(
    project_file: str,
    changespec_name: str,
    test_targets: list[str],
    existing_hooks: list[HookEntry] | None = None,
) -> bool:
    """Add test target hooks for targets that don't already have hooks."""
    if not test_targets:
        return True

    # If hooks provided, use them directly (caller responsible for freshness)
    if existing_hooks is not None:
        hooks = list(existing_hooks)
        existing_commands = {hook.command for hook in hooks}
        for target in test_targets:
            new_hook = _create_test_target_hook(target)
            if new_hook.command not in existing_commands:
                hooks.append(new_hook)
        return update_changespec_hooks_field(project_file, changespec_name, hooks)

    # Otherwise, acquire lock and read fresh state
    from ..changespec import parse_project_file

    try:
        with changespec_lock(project_file):
            changespecs = parse_project_file(project_file)
            current_hooks: list[HookEntry] = []
            for cs in changespecs:
                if cs.name == changespec_name:
                    current_hooks = list(cs.hooks) if cs.hooks else []
                    break

            existing_commands = {hook.command for hook in current_hooks}
            for target in test_targets:
                new_hook = _create_test_target_hook(target)
                if new_hook.command not in existing_commands:
                    current_hooks.append(new_hook)

            write_hooks_unlocked(project_file, changespec_name, current_hooks)
            return True
    except Exception:
        return False


def clear_failed_test_target_hook_status(
    project_file: str,
    changespec_name: str,
    hooks: list[HookEntry],
) -> bool:
    """Clear the most recent status of all FAILED test target hooks."""
    updated_hooks = []
    for hook in hooks:
        latest = hook.latest_status_line
        if _is_test_target_hook(hook) and latest and latest.status == "FAILED":
            if hook.status_lines:
                latest_sl = hook.latest_status_line
                if latest_sl and latest_sl.status == "FAILED":
                    remaining_status_lines = [
                        sl
                        for sl in hook.status_lines
                        if sl.commit_entry_num != latest_sl.commit_entry_num
                    ]
                    updated_hooks.append(
                        HookEntry(
                            command=hook.command,
                            status_lines=(
                                remaining_status_lines
                                if remaining_status_lines
                                else None
                            ),
                        )
                    )
                else:
                    updated_hooks.append(hook)
            else:
                updated_hooks.append(hook)
        else:
            updated_hooks.append(hook)

    return update_changespec_hooks_field(project_file, changespec_name, updated_hooks)
