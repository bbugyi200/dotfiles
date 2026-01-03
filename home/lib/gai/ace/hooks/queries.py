"""Hook queries - test target helpers, workflow queries, and hook mutations."""

from ..changespec import (
    HookEntry,
    HookStatusLine,
    changespec_lock,
)
from .core import is_proposal_entry
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
        hook for hook in hooks if _is_test_target_hook(hook) and hook.status == "FAILED"
    ]


def has_failing_test_target_hooks(hooks: list[HookEntry] | None) -> bool:
    """Check if there are any test target hooks with FAILED status."""
    if not hooks:
        return False
    return len(get_failing_test_target_hooks(hooks)) > 0


def _hook_has_fix_excluded_suffix(hook: HookEntry) -> bool:
    """Check if a hook's latest status line has a suffix that excludes it from fix-hook."""
    sl = hook.latest_status_line
    if sl is None:
        return False
    return sl.suffix is not None


def get_failing_hooks_for_fix(hooks: list[HookEntry]) -> list[HookEntry]:
    """Get failing hooks that are eligible for fix-hook workflow.

    A hook is eligible if:
    - Status is FAILED
    - History entry ID is NOT a proposal (regular entry like "1", "2")
    - No excluded suffix exists

    Note: This only checks the latest status line. Use get_failing_hook_entries_for_fix()
    to check specific entry IDs.
    """
    result: list[HookEntry] = []
    for hook in hooks:
        if hook.status != "FAILED":
            continue
        if _hook_has_fix_excluded_suffix(hook):
            continue
        # Exclude proposal entries - they go to summarize-hook instead
        sl = hook.latest_status_line
        if sl and is_proposal_entry(sl.commit_entry_num):
            continue
        result.append(hook)
    return result


def get_failing_hook_entries_for_fix(
    hooks: list[HookEntry], entry_ids: list[str]
) -> list[tuple[HookEntry, str]]:
    """Get failing hook entries for specific entry IDs that are eligible for fix-hook.

    Unlike get_failing_hooks_for_fix(), this checks ALL specified entry IDs,
    not just the latest status line.

    A hook entry is eligible for fix-hook if:
    - Has a status line for the entry ID with FAILED status
    - The entry ID is NOT a proposal (regular entry like "1", "2", "3")
    - Has suffix_type="summarize_complete" (summary already generated, ready for fix)

    Args:
        hooks: List of hook entries to check.
        entry_ids: List of entry IDs to check (e.g., ["3", "3a"]).

    Returns:
        List of (HookEntry, entry_id) tuples for entries eligible for fix-hook.
    """
    result: list[tuple[HookEntry, str]] = []
    for hook in hooks:
        if not hook.status_lines:
            continue
        for entry_id in entry_ids:
            # Skip proposal entries - they don't get fix-hook
            if is_proposal_entry(entry_id):
                continue
            sl = hook.get_status_line_for_commit_entry(entry_id)
            if sl is None:
                continue
            # Must be FAILED
            if sl.status != "FAILED":
                continue
            # Must have summarize_complete suffix (summary already generated)
            if sl.suffix_type != "summarize_complete":
                continue
            result.append((hook, entry_id))
    return result


def get_failing_hooks_for_summarize(hooks: list[HookEntry]) -> list[HookEntry]:
    """Get failing hooks eligible for summarize-hook workflow.

    A hook is eligible for summarize if:
    - Its latest status line has FAILED status
    - The history entry ID is a proposal (ends with letter like "2a")
    - No suffix exists on the latest status line

    Note: This only checks the latest status line. Use get_failing_hook_entries_for_summarize()
    to check specific entry IDs.

    Args:
        hooks: List of hook entries to check.

    Returns:
        List of HookEntry objects eligible for summarize-hook workflow.
    """
    result: list[HookEntry] = []
    for hook in hooks:
        sl = hook.latest_status_line
        if sl is None:
            continue
        # Must be FAILED
        if sl.status != "FAILED":
            continue
        # Must be a proposal entry (ends with letter)
        if not is_proposal_entry(sl.commit_entry_num):
            continue
        # Must not have a suffix already
        if sl.suffix is not None:
            continue
        result.append(hook)
    return result


def get_failing_hook_entries_for_summarize(
    hooks: list[HookEntry], entry_ids: list[str]
) -> list[tuple[HookEntry, str]]:
    """Get failing hook entries for specific entry IDs that are eligible for summarize.

    Unlike get_failing_hooks_for_summarize(), this checks ALL specified entry IDs,
    not just the latest status line.

    A hook entry is eligible for summarize if:
    - Has a status line for the entry ID with FAILED status
    - No suffix exists on that status line

    Note: Both proposal entries (like "2a") AND non-proposal entries (like "2")
    are eligible for summarize. Non-proposal entries will proceed to fix-hook
    after summarize completes.

    Args:
        hooks: List of hook entries to check.
        entry_ids: List of entry IDs to check (e.g., ["3", "3a"]).

    Returns:
        List of (HookEntry, entry_id) tuples for entries eligible for summarize-hook.
    """
    result: list[tuple[HookEntry, str]] = []
    for hook in hooks:
        if not hook.status_lines:
            continue
        for entry_id in entry_ids:
            sl = hook.get_status_line_for_commit_entry(entry_id)
            if sl is None:
                continue
            # Must be FAILED
            if sl.status != "FAILED":
                continue
            # Must not have a suffix already
            if sl.suffix is not None:
                continue
            result.append((hook, entry_id))
    return result


def has_failing_hooks_for_fix(hooks: list[HookEntry] | None) -> bool:
    """Check if there are any hooks eligible for fix-hook workflow."""
    if not hooks:
        return False
    return len(get_failing_hooks_for_fix(hooks)) > 0


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
        if _is_test_target_hook(hook) and hook.status == "FAILED":
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


def add_hook_to_changespec(
    project_file: str,
    changespec_name: str,
    hook_command: str,
    existing_hooks: list[HookEntry] | None = None,
) -> bool:
    """Add a single hook command to a ChangeSpec."""
    # If hooks provided, use them directly (caller responsible for freshness)
    if existing_hooks is not None:
        hooks = list(existing_hooks)
        existing_commands = {hook.command for hook in hooks}
        if hook_command in existing_commands:
            return True
        hooks.append(HookEntry(command=hook_command))
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
            if hook_command in existing_commands:
                return True

            current_hooks.append(HookEntry(command=hook_command))
            write_hooks_unlocked(project_file, changespec_name, current_hooks)
            return True
    except Exception:
        return False


def _apply_hook_suffix_update(
    hooks: list[HookEntry],
    hook_command: str,
    suffix: str,
    entry_id: str | None = None,
    suffix_type: str | None = None,
    summary: str | None = None,
) -> list[HookEntry]:
    """Apply suffix update to hooks list and return updated hooks."""
    updated_hooks = []
    for hook in hooks:
        if hook.command == hook_command:
            if hook.status_lines:
                updated_status_lines = []
                # Determine which status line to update
                if entry_id is not None:
                    target_sl = hook.get_status_line_for_commit_entry(entry_id)
                else:
                    target_sl = hook.latest_status_line
                for sl in hook.status_lines:
                    if sl is target_sl:
                        updated_status_lines.append(
                            HookStatusLine(
                                commit_entry_num=sl.commit_entry_num,
                                timestamp=sl.timestamp,
                                status=sl.status,
                                duration=sl.duration,
                                suffix=suffix,
                                suffix_type=suffix_type,
                                summary=summary,
                            )
                        )
                    else:
                        updated_status_lines.append(sl)
                updated_hooks.append(
                    HookEntry(
                        command=hook.command,
                        status_lines=updated_status_lines,
                    )
                )
            else:
                updated_hooks.append(hook)
        else:
            updated_hooks.append(hook)
    return updated_hooks


def set_hook_suffix(
    project_file: str,
    changespec_name: str,
    hook_command: str,
    suffix: str,
    hooks: list[HookEntry] | None = None,
    entry_id: str | None = None,
    suffix_type: str | None = None,
    summary: str | None = None,
) -> bool:
    """Set a suffix on a status line of a specific hook.

    Args:
        project_file: Path to the project file.
        changespec_name: Name of the ChangeSpec.
        hook_command: The hook command to update.
        suffix: The suffix to set.
        hooks: List of current hook entries. If None, re-reads from disk to avoid
               overwriting hooks added by concurrent processes.
        entry_id: If provided, set suffix on this specific entry's status line.
                  If None, set suffix on the latest status line (backward compatible).
        suffix_type: Optional suffix type ("error", "running_agent", "summarize_complete").
                     If None, the suffix type is inferred from the suffix value using
                     is_error_suffix() and is_running_agent_suffix() checks.
        summary: Optional summary from summarize_hook workflow. If provided, creates
                 a compound suffix format: (SUFFIX | SUMMARY).
    """
    # If hooks provided, use them directly (caller responsible for freshness)
    if hooks is not None:
        updated_hooks = _apply_hook_suffix_update(
            hooks, hook_command, suffix, entry_id, suffix_type, summary
        )
        return update_changespec_hooks_field(
            project_file, changespec_name, updated_hooks
        )

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
            if not current_hooks:
                return False

            updated_hooks = _apply_hook_suffix_update(
                current_hooks, hook_command, suffix, entry_id, suffix_type, summary
            )
            write_hooks_unlocked(project_file, changespec_name, updated_hooks)
            return True
    except Exception:
        return False


def _apply_clear_hook_suffix(
    hooks: list[HookEntry], hook_command: str
) -> list[HookEntry]:
    """Apply clear suffix update to hooks list and return updated hooks."""
    updated_hooks = []
    for hook in hooks:
        if hook.command == hook_command:
            if hook.status_lines:
                updated_status_lines = []
                latest_sl = hook.latest_status_line
                for sl in hook.status_lines:
                    if sl is latest_sl and sl.suffix is not None:
                        updated_status_lines.append(
                            HookStatusLine(
                                commit_entry_num=sl.commit_entry_num,
                                timestamp=sl.timestamp,
                                status=sl.status,
                                duration=sl.duration,
                                suffix=None,
                            )
                        )
                    else:
                        updated_status_lines.append(sl)
                updated_hooks.append(
                    HookEntry(
                        command=hook.command,
                        status_lines=updated_status_lines,
                    )
                )
            else:
                updated_hooks.append(hook)
        else:
            updated_hooks.append(hook)
    return updated_hooks


def clear_hook_suffix(
    project_file: str,
    changespec_name: str,
    hook_command: str,
    hooks: list[HookEntry] | None = None,
) -> bool:
    """Clear the suffix from the latest status line of a specific hook.

    Args:
        project_file: Path to the project file.
        changespec_name: Name of the ChangeSpec.
        hook_command: The hook command to update.
        hooks: List of current hook entries. If None, re-reads from disk to avoid
               overwriting hooks added by concurrent processes.
    """
    # If hooks provided, use them directly (caller responsible for freshness)
    if hooks is not None:
        updated_hooks = _apply_clear_hook_suffix(hooks, hook_command)
        return update_changespec_hooks_field(
            project_file, changespec_name, updated_hooks
        )

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
            if not current_hooks:
                return False

            updated_hooks = _apply_clear_hook_suffix(current_hooks, hook_command)
            write_hooks_unlocked(project_file, changespec_name, updated_hooks)
            return True
    except Exception:
        return False
