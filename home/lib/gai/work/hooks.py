"""Hook execution utilities for running and tracking ChangeSpec hooks."""

import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .changespec import ChangeSpec, HookEntry, HookStatusLine
from .cl_status import HOOK_ZOMBIE_THRESHOLD_SECONDS


def _get_hooks_directory() -> str:
    """Get the path to the hooks output directory (~/.gai/hooks/)."""
    return os.path.expanduser("~/.gai/hooks")


def _ensure_hooks_directory() -> None:
    """Ensure the hooks directory exists."""
    hooks_dir = _get_hooks_directory()
    Path(hooks_dir).mkdir(parents=True, exist_ok=True)


def get_hook_output_path(name: str, timestamp: str) -> str:
    """Get the output file path for a hook run.

    Args:
        name: The ChangeSpec name.
        timestamp: The timestamp in YYmmddHHMMSS format.

    Returns:
        Full path to the hook output file.
    """
    _ensure_hooks_directory()
    hooks_dir = _get_hooks_directory()
    # Replace non-alphanumeric chars with underscore for safe filename
    safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    filename = f"{safe_name}_{timestamp}.txt"
    return os.path.join(hooks_dir, filename)


def _generate_timestamp() -> str:
    """Generate a timestamp in YYmmddHHMMSS format (2-digit year)."""
    eastern = ZoneInfo("America/New_York")
    return datetime.now(eastern).strftime("%y%m%d%H%M%S")


def _format_duration(seconds: float) -> str:
    """Format a duration in seconds as XhYmZs string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted duration string (e.g., "1h2m3s", "1m23s", "45s", "2m0s").
    """
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    remaining = total_seconds % 3600
    minutes = remaining // 60
    secs = remaining % 60
    if hours > 0:
        return f"{hours}h{minutes}m{secs}s"
    if minutes > 0:
        return f"{minutes}m{secs}s"
    return f"{secs}s"


def get_last_history_entry_num(changespec: ChangeSpec) -> int | None:
    """Get the entry number of the last HISTORY entry.

    Args:
        changespec: The ChangeSpec to get the last entry number from.

    Returns:
        The last history entry number (1-based) or None if no history.
    """
    if not changespec.history:
        return None

    return changespec.history[-1].number


def hook_needs_run(hook: HookEntry, last_history_entry_num: int | None) -> bool:
    """Determine if a hook needs to be run.

    A hook needs to run if no status line exists for the current HISTORY entry.

    Args:
        hook: The hook entry to check.
        last_history_entry_num: The number of the last HISTORY entry (1-based).

    Returns:
        True if the hook should be run, False otherwise.
    """
    # If there's no history entry number, don't run (no history means nothing to run)
    if last_history_entry_num is None:
        return False

    # Check if there's a status line for this history entry
    status_line = hook.get_status_line_for_history_entry(last_history_entry_num)
    return status_line is None


def _get_hook_file_age_seconds_from_timestamp(timestamp: str) -> float | None:
    """Get the age of a hook run based on its timestamp.

    Args:
        timestamp: The timestamp in YYmmddHHMMSS format.

    Returns:
        Age in seconds, or None if timestamp can't be parsed.
    """
    try:
        eastern = ZoneInfo("America/New_York")
        hook_time = datetime.strptime(timestamp, "%y%m%d%H%M%S")
        hook_time = hook_time.replace(tzinfo=eastern)
        now = datetime.now(eastern)
        return (now - hook_time).total_seconds()
    except (ValueError, TypeError):
        return None


def _get_hook_file_age_seconds(hook: HookEntry) -> float | None:
    """Get the age of a hook's output file in seconds.

    Uses the latest status line's timestamp.

    Args:
        hook: The hook entry to check.

    Returns:
        Age in seconds, or None if no timestamp available.
    """
    if not hook.timestamp:
        return None

    return _get_hook_file_age_seconds_from_timestamp(hook.timestamp)


def _calculate_duration_from_timestamps(
    start_timestamp: str, end_timestamp: str
) -> float | None:
    """Calculate duration in seconds between two timestamps.

    Args:
        start_timestamp: Start timestamp in YYmmddHHMMSS format.
        end_timestamp: End timestamp in YYmmddHHMMSS format.

    Returns:
        Duration in seconds, or None if timestamps can't be parsed.
    """
    try:
        eastern = ZoneInfo("America/New_York")
        start_time = datetime.strptime(start_timestamp, "%y%m%d%H%M%S")
        start_time = start_time.replace(tzinfo=eastern)
        end_time = datetime.strptime(end_timestamp, "%y%m%d%H%M%S")
        end_time = end_time.replace(tzinfo=eastern)
        return (end_time - start_time).total_seconds()
    except (ValueError, TypeError):
        return None


def is_hook_zombie(hook: HookEntry) -> bool:
    """Check if a running hook is a zombie (running > 24 hours).

    Args:
        hook: The hook entry to check.

    Returns:
        True if the hook is a zombie, False otherwise.
    """
    if hook.status != "RUNNING":
        return False

    age = _get_hook_file_age_seconds(hook)
    if age is None:
        return False

    return age > HOOK_ZOMBIE_THRESHOLD_SECONDS


def update_changespec_hooks_field(
    project_file: str,
    changespec_name: str,
    hooks: list[HookEntry],
) -> bool:
    """Update the HOOKS field in the project file.

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        hooks: List of HookEntry objects to write.

    Returns:
        True if update succeeded, False otherwise.
    """
    try:
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()

        # Find the ChangeSpec and update/add HOOKS field
        updated_lines: list[str] = []
        in_target_changespec = False
        current_name = None
        found_hooks = False
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check if this is a NAME field
            if line.startswith("NAME:"):
                current_name = line.split(":", 1)[1].strip()
                was_in_target = in_target_changespec
                in_target_changespec = current_name == changespec_name

                # If we were in target and didn't find HOOKS, insert before NAME
                if was_in_target and not found_hooks and hooks:
                    updated_lines.extend(_format_hooks_field(hooks))
                    found_hooks = True

                updated_lines.append(line)
                i += 1
                continue

            # If we're in the target ChangeSpec
            if in_target_changespec:
                # Check for HOOKS field
                if line.startswith("HOOKS:"):
                    found_hooks = True
                    # Skip old HOOKS content and write new content
                    updated_lines.extend(_format_hooks_field(hooks))
                    i += 1
                    # Skip old hooks content
                    while i < len(lines):
                        next_line = lines[i]
                        # Check if still in hooks field:
                        # - 2-space indented command lines
                        # - 4-space indented status lines (start with ( for new format
                        #   or [ for old format)
                        stripped = next_line.strip()
                        if next_line.startswith("    ") and (
                            stripped.startswith("(") or stripped.startswith("[")
                        ):
                            # Status line (4-space indented, starts with ( or [)
                            i += 1
                        elif (
                            next_line.startswith("  ")
                            and not next_line.startswith("    ")
                            and stripped
                            and not stripped.startswith("(")
                            and not stripped.startswith("[")
                        ):
                            # Command line (2-space indented, not 4-space, not empty)
                            i += 1
                        else:
                            break
                    continue

                # Check for end of ChangeSpec (another field or 2 blank lines)
                if line.strip() == "":
                    next_idx = i + 1
                    if next_idx < len(lines) and lines[next_idx].strip() == "":
                        # Two blank lines = end of ChangeSpec
                        if not found_hooks and hooks:
                            updated_lines.extend(_format_hooks_field(hooks))
                            found_hooks = True

            updated_lines.append(line)
            i += 1

        # If we reached end of file while still in target changespec
        if in_target_changespec and not found_hooks and hooks:
            updated_lines.extend(_format_hooks_field(hooks))

        # Write to temp file then atomically rename
        project_dir = os.path.dirname(project_file)
        fd, temp_path = tempfile.mkstemp(dir=project_dir, prefix=".tmp_", suffix=".gp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.writelines(updated_lines)
            os.replace(temp_path, project_file)
            return True
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    except Exception:
        return False


def format_timestamp_display(timestamp: str) -> str:
    """Format a timestamp for display as [YYmmdd_HHMMSS].

    Args:
        timestamp: Raw timestamp in YYmmddHHMMSS format.

    Returns:
        Formatted timestamp like [YYmmdd_HHMMSS].
    """
    # Insert underscore between date and time parts
    return f"[{timestamp[:6]}_{timestamp[6:]}]"


def _format_hooks_field(hooks: list[HookEntry]) -> list[str]:
    """Format hooks as lines for the HOOKS field.

    Args:
        hooks: List of HookEntry objects.

    Returns:
        List of formatted lines including "HOOKS:\n" header.
    """
    if not hooks:
        return []

    lines = ["HOOKS:\n"]
    for hook in hooks:
        lines.append(f"  {hook.command}\n")
        # Output all status lines, sorted by history entry number
        if hook.status_lines:
            sorted_status_lines = sorted(
                hook.status_lines, key=lambda sl: sl.history_entry_num
            )
            for sl in sorted_status_lines:
                ts_display = format_timestamp_display(sl.timestamp)
                if sl.duration:
                    lines.append(
                        f"    ({sl.history_entry_num}) {ts_display} "
                        f"{sl.status} ({sl.duration})\n"
                    )
                else:
                    lines.append(
                        f"    ({sl.history_entry_num}) {ts_display} {sl.status}\n"
                    )

    return lines


def start_hook_background(
    changespec: ChangeSpec,
    hook: HookEntry,
    workspace_dir: str,
    history_entry_num: int,
) -> tuple[HookEntry, str]:
    """Start a hook command as a background process.

    The hook runs asynchronously. Use check_hook_completion() to check status.

    Args:
        changespec: The ChangeSpec the hook belongs to.
        hook: The hook entry to run.
        workspace_dir: The workspace directory to run the command in.
        history_entry_num: The HISTORY entry number this hook run is associated with.

    Returns:
        Tuple of (updated HookEntry with RUNNING status, output_path).
    """
    timestamp = _generate_timestamp()
    output_path = get_hook_output_path(changespec.name, timestamp)

    # Create wrapper script that:
    # 1. Writes the command at the top of the output file
    # 2. Runs the command
    # 3. Writes end timestamp and exit code at the end
    wrapper_script = f"""#!/bin/bash
echo "=== HOOK COMMAND ==="
echo "{hook.command}"
echo "===================="
echo ""
{hook.command} 2>&1
exit_code=$?
echo ""
# Log end timestamp in YYmmddHHMMSS format (America/New_York timezone)
end_timestamp=$(TZ="America/New_York" date +"%y%m%d%H%M%S")
echo "===HOOK_COMPLETE=== END_TIMESTAMP: $end_timestamp EXIT_CODE: $exit_code"
exit $exit_code
"""
    # Write wrapper script to temp file (don't delete - background process needs it)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sh", delete=False
    ) as wrapper_file:
        wrapper_file.write(wrapper_script)
        wrapper_path = wrapper_file.name

    os.chmod(wrapper_path, 0o755)

    # Start as background process
    with open(output_path, "w") as output_file:
        subprocess.Popen(
            [wrapper_path],
            cwd=workspace_dir,
            stdout=output_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    # Create new status line for this run
    new_status_line = HookStatusLine(
        history_entry_num=history_entry_num,
        timestamp=timestamp,
        status="RUNNING",
        duration=None,
    )

    # Preserve existing status lines and add the new one
    existing_status_lines = list(hook.status_lines) if hook.status_lines else []
    updated_hook = HookEntry(
        command=hook.command,
        status_lines=existing_status_lines + [new_status_line],
    )

    return updated_hook, output_path


def check_hook_completion(
    changespec: ChangeSpec,
    hook: HookEntry,
) -> HookEntry | None:
    """Check if a running hook has completed.

    Reads the hook's output file looking for the completion marker.
    Updates the RUNNING status line with completion status.

    Args:
        changespec: The ChangeSpec the hook belongs to.
        hook: The hook entry to check (must have a RUNNING status line).

    Returns:
        Updated HookEntry with PASSED/FAILED status if complete, None if still running.
    """
    # Find the RUNNING status line (the latest one)
    running_status_line = None
    running_idx = -1
    if hook.status_lines:
        for idx, sl in enumerate(hook.status_lines):
            if sl.status == "RUNNING":
                running_status_line = sl
                running_idx = idx

    if running_status_line is None:
        return None

    output_path = get_hook_output_path(changespec.name, running_status_line.timestamp)

    if not os.path.exists(output_path):
        return None

    try:
        with open(output_path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None

    # Look for completion marker (new format with end timestamp)
    # Format: ===HOOK_COMPLETE=== END_TIMESTAMP: YYmmddHHMMSS EXIT_CODE: N
    marker = "===HOOK_COMPLETE=== END_TIMESTAMP: "
    marker_pos = content.rfind(marker)

    # Also check for old format (for backward compatibility)
    old_marker = "===HOOK_COMPLETE=== EXIT_CODE: "
    old_marker_pos = content.rfind(old_marker)

    if marker_pos == -1 and old_marker_pos == -1:
        # Not complete yet
        return None

    # Parse completion line based on format found
    end_timestamp: str | None = None
    if marker_pos != -1:
        # New format with end timestamp
        try:
            after_marker = content[marker_pos + len(marker) :].strip()
            parts = after_marker.split()
            end_timestamp = parts[0]
            # EXIT_CODE: is at index 1, value at index 2
            exit_code = int(parts[2])
        except (ValueError, IndexError):
            # Couldn't parse, treat as failed with fallback duration
            exit_code = 1
            end_timestamp = None
    else:
        # Old format without end timestamp
        try:
            exit_code_str = (
                content[old_marker_pos + len(old_marker) :].strip().split()[0]
            )
            exit_code = int(exit_code_str)
        except (ValueError, IndexError):
            exit_code = 1
        end_timestamp = None

    # Calculate duration from timestamps (precise) or fallback to file age
    if end_timestamp:
        duration_seconds = _calculate_duration_from_timestamps(
            running_status_line.timestamp, end_timestamp
        )
        if duration_seconds is not None:
            duration = _format_duration(duration_seconds)
        else:
            # Fallback to file age if timestamp parsing fails
            age = _get_hook_file_age_seconds_from_timestamp(
                running_status_line.timestamp
            )
            duration = _format_duration(age) if age is not None else "0s"
    else:
        # Fallback to file age for old format or missing timestamps
        age = _get_hook_file_age_seconds_from_timestamp(running_status_line.timestamp)
        duration = _format_duration(age) if age is not None else "0s"

    # Determine status
    completed_status = "PASSED" if exit_code == 0 else "FAILED"

    # Create updated status line with completion info
    updated_status_line = HookStatusLine(
        history_entry_num=running_status_line.history_entry_num,
        timestamp=running_status_line.timestamp,
        status=completed_status,
        duration=duration,
    )

    # Replace the RUNNING status line with the completed one
    updated_status_lines = list(hook.status_lines) if hook.status_lines else []
    if running_idx >= 0:
        updated_status_lines[running_idx] = updated_status_line

    return HookEntry(
        command=hook.command,
        status_lines=updated_status_lines,
    )


# Test target hook helpers
TEST_TARGET_HOOK_PREFIX = "bb_rabbit_test "


def _is_test_target_hook(hook: HookEntry) -> bool:
    """Check if a hook is a test target hook.

    Args:
        hook: The hook entry to check.

    Returns:
        True if hook command starts with 'bb_rabbit_test ', False otherwise.
    """
    return hook.command.startswith(TEST_TARGET_HOOK_PREFIX)


def get_test_target_from_hook(hook: HookEntry) -> str | None:
    """Extract the test target from a test target hook command.

    Args:
        hook: The hook entry to extract the target from.

    Returns:
        The test target (e.g., '//foo:bar'), or None if not a test target hook.
    """
    if not _is_test_target_hook(hook):
        return None
    return hook.command[len(TEST_TARGET_HOOK_PREFIX) :].strip()


def _create_test_target_hook(test_target: str) -> HookEntry:
    """Create a new test target hook entry for a given target.

    Args:
        test_target: The test target (e.g., '//foo:bar').

    Returns:
        A new HookEntry for the test target with no status lines.
    """
    return HookEntry(command=f"{TEST_TARGET_HOOK_PREFIX}{test_target}")


def get_failing_test_target_hooks(hooks: list[HookEntry]) -> list[HookEntry]:
    """Get all test target hooks that have FAILED status.

    Args:
        hooks: List of all hook entries.

    Returns:
        List of test target hooks with FAILED status.
    """
    return [
        hook for hook in hooks if _is_test_target_hook(hook) and hook.status == "FAILED"
    ]


def has_failing_test_target_hooks(hooks: list[HookEntry] | None) -> bool:
    """Check if there are any test target hooks with FAILED status.

    Args:
        hooks: List of hook entries (can be None).

    Returns:
        True if any test target hook has FAILED status.
    """
    if not hooks:
        return False
    return len(get_failing_test_target_hooks(hooks)) > 0


def get_failing_hooks(hooks: list[HookEntry]) -> list[HookEntry]:
    """Get all hooks that have FAILED status.

    Args:
        hooks: List of all hook entries.

    Returns:
        List of hooks with FAILED status.
    """
    return [hook for hook in hooks if hook.status == "FAILED"]


def has_failing_hooks(hooks: list[HookEntry] | None) -> bool:
    """Check if there are any hooks with FAILED status.

    Args:
        hooks: List of hook entries (can be None).

    Returns:
        True if any hook has FAILED status.
    """
    if not hooks:
        return False
    return len(get_failing_hooks(hooks)) > 0


def has_running_hooks(hooks: list[HookEntry] | None) -> bool:
    """Check if any hooks are currently in RUNNING status.

    Args:
        hooks: List of hook entries (can be None).

    Returns:
        True if any hook has RUNNING status.
    """
    if not hooks:
        return False
    return any(hook.status == "RUNNING" for hook in hooks)


def add_test_target_hooks_to_changespec(
    project_file: str,
    changespec_name: str,
    test_targets: list[str],
    existing_hooks: list[HookEntry] | None = None,
) -> bool:
    """Add test target hooks for targets that don't already have hooks.

    This function adds new hooks for test targets that don't already have
    corresponding hooks in the ChangeSpec.

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        test_targets: List of test targets to add hooks for.
        existing_hooks: Current hooks (if None, assumes empty list).

    Returns:
        True if update succeeded, False otherwise.
    """
    if not test_targets:
        return True

    # Start with existing hooks or empty list
    hooks = list(existing_hooks) if existing_hooks else []

    # Get existing test target commands for comparison
    existing_commands = {hook.command for hook in hooks}

    # Add new hooks for targets that don't exist
    for target in test_targets:
        new_hook = _create_test_target_hook(target)
        if new_hook.command not in existing_commands:
            hooks.append(new_hook)

    return update_changespec_hooks_field(project_file, changespec_name, hooks)


def clear_failed_test_target_hook_status(
    project_file: str,
    changespec_name: str,
    hooks: list[HookEntry],
) -> bool:
    """Clear the most recent status of all FAILED test target hooks.

    This removes the most recent FAILED status line so the hook will be re-run.

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        hooks: Current hooks list.

    Returns:
        True if update succeeded, False otherwise.
    """
    updated_hooks = []
    for hook in hooks:
        if _is_test_target_hook(hook) and hook.status == "FAILED":
            # Remove the most recent status line (which has FAILED status)
            if hook.status_lines:
                latest_sl = hook.latest_status_line
                if latest_sl and latest_sl.status == "FAILED":
                    # Keep all status lines except the latest one
                    remaining_status_lines = [
                        sl
                        for sl in hook.status_lines
                        if sl.history_entry_num != latest_sl.history_entry_num
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
    """Add a single hook command to a ChangeSpec.

    If the hook command already exists, it will not be duplicated.

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        hook_command: The hook command to add.
        existing_hooks: Current hooks (if None, assumes empty list).

    Returns:
        True if update succeeded, False otherwise.
    """
    # Start with existing hooks or empty list
    hooks = list(existing_hooks) if existing_hooks else []

    # Check if hook already exists
    existing_commands = {hook.command for hook in hooks}
    if hook_command in existing_commands:
        return True  # Already exists, nothing to do

    # Add new hook (no status lines yet)
    hooks.append(HookEntry(command=hook_command))

    return update_changespec_hooks_field(project_file, changespec_name, hooks)
