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


def _get_hook_output_path(name: str, timestamp: str) -> str:
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
            if hook.duration:
                lines.append(
                    f"    | {hook.timestamp}: {hook.status} ({hook.duration})\n"
                )
            else:
                lines.append(f"    | {hook.timestamp}: {hook.status}\n")

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
    output_path = _get_hook_output_path(changespec.name, timestamp)

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

    output_path = _get_hook_output_path(changespec.name, hook.timestamp)

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
