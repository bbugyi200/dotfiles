"""Hook execution utilities for running and tracking ChangeSpec hooks."""

import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .changespec import ChangeSpec, HookEntry
from .cl_status import PRESUBMIT_ZOMBIE_THRESHOLD_SECONDS


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
    """Format a duration in seconds as XmYs string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted duration string (e.g., "1m23s", "45s", "2m0s").
    """
    total_seconds = int(seconds)
    minutes = total_seconds // 60
    secs = total_seconds % 60
    if minutes > 0:
        return f"{minutes}m{secs}s"
    return f"{secs}s"


def get_last_history_diff_timestamp(changespec: ChangeSpec) -> str | None:
    """Extract the timestamp from the last HISTORY entry's DIFF path.

    DIFF paths look like: ~/.gai/diffs/cl_name_YYmmddHHMMSS.diff

    Args:
        changespec: The ChangeSpec to extract the timestamp from.

    Returns:
        The timestamp string (YYmmddHHMMSS) or None if not found.
    """
    if not changespec.history:
        return None

    # Get the last history entry
    last_entry = changespec.history[-1]
    if not last_entry.diff:
        return None

    # Extract timestamp from DIFF path using regex
    # Pattern: _<12 digits>.diff at the end of the path
    match = re.search(r"_(\d{12})\.diff$", last_entry.diff)
    if match:
        return match.group(1)

    return None


def hook_needs_run(hook: HookEntry, last_diff_timestamp: str | None) -> bool:
    """Determine if a hook needs to be run.

    A hook needs to run if:
    1. It has never been run (no timestamp)
    2. Its last run was before the last HISTORY entry's DIFF timestamp

    Args:
        hook: The hook entry to check.
        last_diff_timestamp: The timestamp from the last HISTORY DIFF (YYmmddHHMMSS).

    Returns:
        True if the hook should be run, False otherwise.
    """
    # If hook has never been run, it needs to run
    if not hook.timestamp:
        return True

    # If there's no diff timestamp to compare against, don't run
    # (this means there's no history, so nothing has changed)
    if not last_diff_timestamp:
        return False

    # Compare timestamps (they're in YYmmddHHMMSS format, so string comparison works)
    return hook.timestamp < last_diff_timestamp


def _get_hook_file_age_seconds(hook: HookEntry) -> float | None:
    """Get the age of a hook's output file in seconds.

    Args:
        hook: The hook entry to check.

    Returns:
        Age in seconds, or None if file doesn't exist or no timestamp.
    """
    if not hook.timestamp:
        return None

    # Parse timestamp (YYmmddHHMMSS format)
    try:
        # Convert 2-digit year to 4-digit
        timestamp_str = hook.timestamp
        eastern = ZoneInfo("America/New_York")
        hook_time = datetime.strptime(timestamp_str, "%y%m%d%H%M%S")
        hook_time = hook_time.replace(tzinfo=eastern)
        now = datetime.now(eastern)
        return (now - hook_time).total_seconds()
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

    return age > PRESUBMIT_ZOMBIE_THRESHOLD_SECONDS


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
                        # Check if still in hooks field (2 or 4 space indented)
                        if next_line.startswith("  ") and (
                            not next_line.startswith("  ")
                            or next_line.strip().startswith("|")
                            or (
                                next_line.startswith("  ")
                                and not next_line[2:].startswith(" ")
                            )
                        ):
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


def _format_timestamp_display(timestamp: str) -> str:
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
        if hook.timestamp and hook.status:
            ts_display = _format_timestamp_display(hook.timestamp)
            if hook.duration:
                lines.append(f"    | {ts_display} {hook.status} ({hook.duration})\n")
            else:
                lines.append(f"    | {ts_display} {hook.status}\n")

    return lines


def start_hook_background(
    changespec: ChangeSpec,
    hook: HookEntry,
    workspace_dir: str,
) -> tuple[HookEntry, str]:
    """Start a hook command as a background process.

    The hook runs asynchronously. Use check_hook_completion() to check status.

    Args:
        changespec: The ChangeSpec the hook belongs to.
        hook: The hook entry to run.
        workspace_dir: The workspace directory to run the command in.

    Returns:
        Tuple of (updated HookEntry with RUNNING status, output_path).
    """
    timestamp = _generate_timestamp()
    output_path = get_hook_output_path(changespec.name, timestamp)

    # Create wrapper script that:
    # 1. Writes the command at the top of the output file
    # 2. Runs the command
    # 3. Writes exit code at the end
    wrapper_script = f"""#!/bin/bash
echo "=== HOOK COMMAND ==="
echo "{hook.command}"
echo "===================="
echo ""
{hook.command} 2>&1
exit_code=$?
echo ""
echo "===HOOK_COMPLETE=== EXIT_CODE: $exit_code"
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

    # Return hook with RUNNING status
    updated_hook = HookEntry(
        command=hook.command,
        timestamp=timestamp,
        status="RUNNING",
        duration=None,
    )

    return updated_hook, output_path


def check_hook_completion(
    changespec: ChangeSpec,
    hook: HookEntry,
) -> HookEntry | None:
    """Check if a running hook has completed.

    Reads the hook's output file looking for the completion marker.

    Args:
        changespec: The ChangeSpec the hook belongs to.
        hook: The hook entry to check (must have RUNNING status).

    Returns:
        Updated HookEntry with PASSED/FAILED status if complete, None if still running.
    """
    if not hook.timestamp:
        return None

    output_path = get_hook_output_path(changespec.name, hook.timestamp)

    if not os.path.exists(output_path):
        return None

    try:
        with open(output_path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None

    # Look for completion marker
    marker = "===HOOK_COMPLETE=== EXIT_CODE: "
    marker_pos = content.rfind(marker)
    if marker_pos == -1:
        # Not complete yet
        return None

    # Extract exit code
    try:
        exit_code_str = content[marker_pos + len(marker) :].strip().split()[0]
        exit_code = int(exit_code_str)
    except (ValueError, IndexError):
        # Couldn't parse exit code, treat as failed
        exit_code = 1

    # Calculate duration from hook timestamp
    age = _get_hook_file_age_seconds(hook)
    duration = _format_duration(age) if age is not None else "0s"

    # Determine status
    status = "PASSED" if exit_code == 0 else "FAILED"

    return HookEntry(
        command=hook.command,
        timestamp=hook.timestamp,
        status=status,
        duration=duration,
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
        A new HookEntry for the test target with no status.
    """
    return HookEntry(
        command=f"{TEST_TARGET_HOOK_PREFIX}{test_target}",
        timestamp=None,
        status=None,
        duration=None,
    )


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
    """Clear the status of all FAILED test target hooks.

    This resets FAILED test target hooks so they can be re-run.

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
            # Clear status so it will be re-run
            updated_hooks.append(
                HookEntry(
                    command=hook.command,
                    timestamp=None,
                    status=None,
                    duration=None,
                )
            )
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

    # Add new hook
    hooks.append(
        HookEntry(
            command=hook_command,
            timestamp=None,
            status=None,
            duration=None,
        )
    )

    return update_changespec_hooks_field(project_file, changespec_name, hooks)
