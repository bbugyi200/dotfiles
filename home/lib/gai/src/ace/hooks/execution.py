"""Hook execution - file updates and background execution."""

import logging
import os
import subprocess
import tempfile

from gai_utils import (
    ensure_gai_directory,
    generate_timestamp,
    make_safe_filename,
    strip_reverted_suffix,
)

from ..changespec import (
    ChangeSpec,
    HookEntry,
    HookStatusLine,
    LockTimeoutError,
    changespec_lock,
    is_error_suffix,
    is_running_agent_suffix,
    parse_commit_entry_id,
    write_changespec_atomic,
)
from .timestamps import (
    calculate_duration_from_timestamps,
    format_duration,
    format_timestamp_display,
    get_hook_file_age_seconds_from_timestamp,
)


def get_hook_output_path(name: str, timestamp: str) -> str:
    """Get the output file path for a hook run.

    Args:
        name: The ChangeSpec name.
        timestamp: The timestamp in YYmmdd_HHMMSS format.

    Returns:
        Full path to the hook output file.
    """
    hooks_dir = ensure_gai_directory("hooks")
    safe_name = make_safe_filename(strip_reverted_suffix(name))
    filename = f"{safe_name}-{timestamp}.txt"
    return os.path.join(hooks_dir, filename)


def _format_hooks_field(hooks: list[HookEntry]) -> list[str]:
    """Format hooks as lines for the HOOKS field.

    Args:
        hooks: List of HookEntry objects.

    Returns:
        List of formatted lines including "HOOKS:\\n" header.
    """
    if not hooks:
        return []

    # Lazy import to avoid circular dependency
    from .queries import contract_test_target_command

    lines = ["HOOKS:\n"]
    for hook in hooks:
        # Contract test target commands to shorthand format
        display_command = contract_test_target_command(hook.command)
        lines.append(f"  {display_command}\n")
        # Output all status lines, sorted by history entry ID (e.g., "1", "1a", "2")
        if hook.status_lines:
            sorted_status_lines = sorted(
                hook.status_lines,
                key=lambda sl: parse_commit_entry_id(sl.commit_entry_num),
            )
            for sl in sorted_status_lines:
                ts_display = format_timestamp_display(sl.timestamp)
                # Build the line parts
                line_parts = [
                    f"      | ({sl.commit_entry_num}) {ts_display} {sl.status}"
                ]
                if sl.duration:
                    line_parts.append(f" ({sl.duration})")
                # Check for suffix (including empty string with running_agent type)
                # or summary (compound suffix format)
                has_suffix = sl.suffix is not None and (
                    sl.suffix or sl.suffix_type == "running_agent"
                )
                has_summary_only = sl.summary and not has_suffix
                if has_suffix or has_summary_only:
                    # Build suffix content based on suffix_type
                    suffix_content = ""
                    if has_suffix:
                        # Use suffix_type if available, fall back to message-based detection
                        # "plain" and "summarize_complete" mean no prefix
                        suffix_val = sl.suffix or ""
                        if sl.suffix_type == "plain":
                            suffix_content = suffix_val
                        elif sl.suffix_type == "summarize_complete":
                            suffix_content = f"%: {suffix_val}" if suffix_val else "%"
                        elif sl.suffix_type == "error" or (
                            sl.suffix_type is None and is_error_suffix(sl.suffix)
                        ):
                            suffix_content = f"!: {suffix_val}"
                        elif sl.suffix_type == "running_agent" or (
                            sl.suffix_type is None
                            and is_running_agent_suffix(sl.suffix)
                        ):
                            # Empty suffix → "@", non-empty → "@: msg"
                            suffix_content = f"@: {suffix_val}" if suffix_val else "@"
                        elif sl.suffix_type == "killed_agent":
                            suffix_content = f"~@: {suffix_val}"
                        elif sl.suffix_type == "running_process":
                            suffix_content = f"$: {suffix_val}"
                        elif sl.suffix_type == "pending_dead_process":
                            suffix_content = f"?$: {suffix_val}"
                        elif sl.suffix_type == "killed_process":
                            suffix_content = f"~$: {suffix_val}"
                        else:
                            suffix_content = suffix_val

                    # Append summary if present (compound suffix format)
                    if sl.summary:
                        if suffix_content:
                            suffix_content = f"{suffix_content} | {sl.summary}"
                        else:
                            suffix_content = sl.summary

                    line_parts.append(f" - ({suffix_content})")
                line_parts.append("\n")
                lines.append("".join(line_parts))

    return lines


def _apply_hooks_update(
    lines: list[str],
    changespec_name: str,
    hooks: list[HookEntry],
) -> list[str]:
    """Apply HOOKS field update to file lines.

    Args:
        lines: Current file lines.
        changespec_name: NAME of the ChangeSpec to update.
        hooks: List of HookEntry objects to write.

    Returns:
        Updated lines with HOOKS field modified.
    """
    updated_lines: list[str] = []
    in_target_changespec = False
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
                    # - "      | " prefixed status lines (start with ( after prefix)
                    stripped = next_line.strip()
                    if next_line.startswith("      | ") and (
                        stripped[2:].startswith("(") if len(stripped) > 2 else False
                    ):
                        # Status line ("      | " prefixed, starts with ( after prefix)
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

    return updated_lines


def write_hooks_unlocked(
    project_file: str,
    changespec_name: str,
    hooks: list[HookEntry],
) -> None:
    """Write hooks to file. Must be called while holding the lock.

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        hooks: List of HookEntry objects to write.
    """
    with open(project_file, encoding="utf-8") as f:
        lines = f.readlines()

    updated_lines = _apply_hooks_update(lines, changespec_name, hooks)

    write_changespec_atomic(
        project_file,
        "".join(updated_lines),
        f"Update HOOKS for {changespec_name}",
    )


def update_changespec_hooks_field(
    project_file: str,
    changespec_name: str,
    hooks: list[HookEntry],
) -> bool:
    """Update the HOOKS field in the project file.

    Acquires a lock on the file for the entire read-modify-write cycle.

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        hooks: List of HookEntry objects to write.

    Returns:
        True if update succeeded, False otherwise.
    """
    try:
        with changespec_lock(project_file):
            write_hooks_unlocked(project_file, changespec_name, hooks)
            return True

    except Exception:
        return False


def merge_hook_updates(
    project_file: str,
    changespec_name: str,
    hook_updates: dict[str, HookEntry],
) -> bool:
    """Merge hook status updates with current disk state.

    Acquires a lock and re-reads hooks from disk before writing to avoid
    overwriting hooks added by concurrent processes (e.g., gai commit adding
    test hooks while gai axe is updating hook statuses).

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        hook_updates: Dict mapping hook command -> updated HookEntry.
            Only hooks in this dict will be updated; other hooks on disk
            are preserved unchanged.

    Returns:
        True if update succeeded, False otherwise.
    """
    from ..changespec import parse_project_file

    try:
        with changespec_lock(project_file):
            # Re-read current hooks from disk while holding lock
            changespecs = parse_project_file(project_file)
            current_hooks: list[HookEntry] = []
            for cs in changespecs:
                if cs.name == changespec_name:
                    current_hooks = list(cs.hooks) if cs.hooks else []
                    break

            # Merge: use updated version if available, otherwise keep disk version
            merged_hooks: list[HookEntry] = []
            for hook in current_hooks:
                if hook.command in hook_updates:
                    merged_hooks.append(hook_updates[hook.command])
                else:
                    merged_hooks.append(hook)

            write_hooks_unlocked(project_file, changespec_name, merged_hooks)
            return True

    except LockTimeoutError:
        # Log lock timeout specifically - this is likely due to contention
        logging.warning(
            f"Lock timeout updating hooks for {changespec_name} in {project_file}"
        )
        return False
    except Exception as e:
        # Log unexpected errors
        logging.error(f"Failed to update hooks for {changespec_name}: {e}")
        return False


def update_hook_status_line_suffix_type(
    project_file: str,
    changespec_name: str,
    hook_command: str,
    commit_entry_num: str,
    new_suffix_type: str,
    hooks: list[HookEntry],
) -> bool:
    """Update the suffix_type of a specific hook status line.

    Args:
        project_file: Path to the project file.
        changespec_name: NAME of the ChangeSpec.
        hook_command: The hook command to find.
        commit_entry_num: The history entry number of the status line.
        new_suffix_type: The new suffix type ("error" or "plain").
        hooks: Current list of HookEntry objects.

    Returns:
        True if update succeeded, False otherwise.
    """
    updated_hooks: list[HookEntry] = []
    found = False

    for hook in hooks:
        if hook.command == hook_command and hook.status_lines:
            updated_status_lines: list[HookStatusLine] = []
            for sl in hook.status_lines:
                # Allow transitioning from "error" to other types, or to "plain" from any type
                if (
                    sl.commit_entry_num == commit_entry_num
                    and sl.suffix
                    and (sl.suffix_type == "error" or new_suffix_type == "plain")
                ):
                    found = True
                    updated_status_lines.append(
                        HookStatusLine(
                            commit_entry_num=sl.commit_entry_num,
                            timestamp=sl.timestamp,
                            status=sl.status,
                            duration=sl.duration,
                            suffix=sl.suffix,
                            suffix_type=new_suffix_type,
                        )
                    )
                else:
                    updated_status_lines.append(sl)
            updated_hooks.append(
                HookEntry(command=hook.command, status_lines=updated_status_lines)
            )
        else:
            updated_hooks.append(hook)

    if not found:
        return False

    return update_changespec_hooks_field(project_file, changespec_name, updated_hooks)


def start_hook_background(
    changespec: ChangeSpec,
    hook: HookEntry,
    workspace_dir: str,
    history_entry_id: str,
) -> tuple[HookEntry, str]:
    """Start a hook command as a background process.

    The hook runs asynchronously. Use check_hook_completion() to check status.

    Args:
        changespec: The ChangeSpec the hook belongs to.
        hook: The hook entry to run.
        workspace_dir: The workspace directory to run the command in.
        history_entry_id: The HISTORY entry ID this hook run is associated with.

    Returns:
        Tuple of (updated HookEntry with RUNNING status, output_path).
    """
    timestamp = generate_timestamp()
    output_path = get_hook_output_path(changespec.name, timestamp)

    # Get the actual command to run (strips "!" prefix if present)
    actual_command = hook.run_command

    # Create wrapper script with retry logic for transient errors
    wrapper_script = f"""#!/bin/bash

# Retry configuration
MAX_RETRIES=3
RETRY_DELAY=60

# Patterns that trigger retry (grep -E format)
RETRIABLE_PATTERNS=(
    "Per user memory limit reached"
)

echo "=== HOOK COMMAND ==="
echo "{actual_command}"
echo "===================="
echo ""

# Build grep pattern from array
build_pattern() {{
    local IFS='|'
    echo "${{RETRIABLE_PATTERNS[*]}}"
}}

# Check if output contains retriable error
is_retriable() {{
    local output_file="$1"
    local pattern
    pattern=$(build_pattern)
    grep -qE "$pattern" "$output_file" 2>/dev/null
}}

# Execute command with retry logic
attempt=1
while [ $attempt -le $MAX_RETRIES ]; do
    tmp_output=$(mktemp)
    trap "rm -f '$tmp_output'" EXIT

    ( {actual_command} ) > "$tmp_output" 2>&1
    exit_code=$?

    if [ $exit_code -ne 0 ] && [ $attempt -lt $MAX_RETRIES ] && is_retriable "$tmp_output"; then
        echo "=== RETRY ATTEMPT $attempt/$MAX_RETRIES ==="
        echo "Detected retriable error. Waiting ${{RETRY_DELAY}}s before retry..."
        cat "$tmp_output"
        echo ""
        echo "=== WAITING ${{RETRY_DELAY}}s ==="
        rm -f "$tmp_output"
        sleep $RETRY_DELAY
        attempt=$((attempt + 1))
    else
        if [ $attempt -gt 1 ]; then
            echo "=== FINAL ATTEMPT ($attempt/$MAX_RETRIES) ==="
        fi
        cat "$tmp_output"
        rm -f "$tmp_output"
        break
    fi
done

echo ""
# Log end timestamp in YYmmdd_HHMMSS format (America/New_York timezone)
end_timestamp=$(TZ="America/New_York" date +"%y%m%d_%H%M%S")
echo "===HOOK_COMPLETE=== END_TIMESTAMP: $end_timestamp EXIT_CODE: $exit_code"
# Ensure output is flushed to disk before exiting to prevent race condition
# where the parent process sees the process as dead but hasn't read the marker yet
sync
exit $exit_code
"""
    # Write wrapper script to temp file (don't delete - background process needs it)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sh", delete=False
    ) as wrapper_file:
        wrapper_file.write(wrapper_script)
        wrapper_path = wrapper_file.name

    os.chmod(wrapper_path, 0o755)

    # Start as background process and capture PID
    with open(output_path, "w") as output_file:
        process = subprocess.Popen(
            [wrapper_path],
            cwd=workspace_dir,
            stdout=output_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        process_pid = process.pid

    # Create new status line for this run
    # Use PID suffix with running_process type to get " - ($: PID)" marker
    new_status_line = HookStatusLine(
        commit_entry_num=history_entry_id,
        timestamp=timestamp,
        status="RUNNING",
        duration=None,
        suffix=str(process_pid),
        suffix_type="running_process",
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
    target_status_line: HookStatusLine | None = None,
) -> HookEntry | None:
    """Check if a running hook has completed.

    Reads the hook's output file looking for the completion marker.
    Updates the RUNNING status line with completion status.

    Args:
        changespec: The ChangeSpec the hook belongs to.
        hook: The hook entry to check (must have a RUNNING status line).
        target_status_line: Optional specific status line to check. If provided,
            checks this status line's output file instead of the first RUNNING one.
            This is needed when multiple status lines are RUNNING for the same hook.

    Returns:
        Updated HookEntry with PASSED/FAILED status if complete, None if still running.
    """
    # Find the status line to check
    running_status_line = None
    running_idx = -1
    if target_status_line is not None:
        # Use the provided status line
        running_status_line = target_status_line
        if hook.status_lines:
            for idx, sl in enumerate(hook.status_lines):
                if sl is target_status_line:
                    running_idx = idx
                    break
    else:
        # Find the FIRST RUNNING status line (original behavior)
        if hook.status_lines:
            for idx, sl in enumerate(hook.status_lines):
                if sl.status == "RUNNING":
                    running_status_line = sl
                    running_idx = idx
                    break

    if running_status_line is None:
        return None

    output_path = get_hook_output_path(changespec.name, running_status_line.timestamp)

    # If the output file doesn't exist with the current name, try the original name
    if not os.path.exists(output_path):
        original_name = strip_reverted_suffix(changespec.name)
        if original_name != changespec.name:
            output_path = get_hook_output_path(
                original_name, running_status_line.timestamp
            )

    if not os.path.exists(output_path):
        return None

    try:
        with open(output_path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None

    # Look for completion marker with end timestamp
    marker = "===HOOK_COMPLETE=== END_TIMESTAMP: "
    marker_pos = content.rfind(marker)

    if marker_pos == -1:
        return None

    # Parse completion line
    end_timestamp: str | None = None
    try:
        after_marker = content[marker_pos + len(marker) :].strip()
        parts = after_marker.split()
        end_timestamp = parts[0]
        exit_code = int(parts[2])
    except (ValueError, IndexError):
        exit_code = 1
        end_timestamp = None

    # Calculate duration
    if end_timestamp:
        duration_seconds = calculate_duration_from_timestamps(
            running_status_line.timestamp, end_timestamp
        )
        if duration_seconds is not None:
            duration = format_duration(duration_seconds)
        else:
            age = get_hook_file_age_seconds_from_timestamp(
                running_status_line.timestamp
            )
            duration = format_duration(age) if age is not None else "0s"
    else:
        age = get_hook_file_age_seconds_from_timestamp(running_status_line.timestamp)
        duration = format_duration(age) if age is not None else "0s"

    completed_status = "PASSED" if exit_code == 0 else "FAILED"

    # Auto-append summary suffix for hooks with "!" prefix (skip_fix_hook)
    auto_skip_suffix = None
    if completed_status == "FAILED" and hook.skip_fix_hook:
        from summarize_utils import get_file_summary

        auto_skip_suffix = get_file_summary(
            target_file=output_path,
            usage="a hook failure suffix in a HISTORY entry",
            fallback="Hook Command Failed",
        )

    # Create updated status line
    updated_status_line = HookStatusLine(
        commit_entry_num=running_status_line.commit_entry_num,
        timestamp=running_status_line.timestamp,
        status=completed_status,
        duration=duration,
        suffix=auto_skip_suffix,
        suffix_type="error" if auto_skip_suffix else None,
    )

    # Replace the RUNNING status line with the completed one
    updated_status_lines = list(hook.status_lines) if hook.status_lines else []
    if running_idx >= 0:
        updated_status_lines[running_idx] = updated_status_line

    return HookEntry(
        command=hook.command,
        status_lines=updated_status_lines,
    )
