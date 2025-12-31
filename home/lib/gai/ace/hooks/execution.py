"""Hook execution - file updates and background execution."""

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
    is_error_suffix,
    is_running_agent_suffix,
    parse_commit_entry_id,
)
from .core import (
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
    safe_name = make_safe_filename(name)
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

    lines = ["HOOKS:\n"]
    for hook in hooks:
        lines.append(f"  {hook.command}\n")
        # Output all status lines, sorted by history entry ID (e.g., "1", "1a", "2")
        if hook.status_lines:
            sorted_status_lines = sorted(
                hook.status_lines,
                key=lambda sl: parse_commit_entry_id(sl.commit_entry_num),
            )
            for sl in sorted_status_lines:
                ts_display = format_timestamp_display(sl.timestamp)
                # Build the line parts
                line_parts = [f"    ({sl.commit_entry_num}) {ts_display} {sl.status}"]
                if sl.duration:
                    line_parts.append(f" ({sl.duration})")
                # Check for suffix (including empty string with running_agent type)
                if sl.suffix is not None and (
                    sl.suffix or sl.suffix_type == "running_agent"
                ):
                    # Use suffix_type if available, fall back to message-based detection
                    # "plain" explicitly means no prefix, bypassing auto-detect
                    if sl.suffix_type == "plain":
                        line_parts.append(f" - ({sl.suffix})")
                    elif sl.suffix_type == "error" or (
                        sl.suffix_type is None and is_error_suffix(sl.suffix)
                    ):
                        line_parts.append(f" - (!: {sl.suffix})")
                    elif sl.suffix_type == "running_agent" or (
                        sl.suffix_type is None and is_running_agent_suffix(sl.suffix)
                    ):
                        # Empty suffix → "(@)", non-empty → "(@: msg)"
                        if sl.suffix:
                            line_parts.append(f" - (@: {sl.suffix})")
                        else:
                            line_parts.append(" - (@)")
                    else:
                        line_parts.append(f" - ({sl.suffix})")
                line_parts.append("\n")
                lines.append("".join(line_parts))

    return lines


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

    # Create wrapper script
    wrapper_script = f"""#!/bin/bash
echo "=== HOOK COMMAND ==="
echo "{actual_command}"
echo "===================="
echo ""
{actual_command} 2>&1
exit_code=$?
echo ""
# Log end timestamp in YYmmdd_HHMMSS format (America/New_York timezone)
end_timestamp=$(TZ="America/New_York" date +"%y%m%d_%H%M%S")
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
    # Use empty suffix with running_agent type to get " - (@)" marker
    new_status_line = HookStatusLine(
        commit_entry_num=history_entry_id,
        timestamp=timestamp,
        status="RUNNING",
        duration=None,
        suffix="",
        suffix_type="running_agent",
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
    # Find the FIRST RUNNING status line
    running_status_line = None
    running_idx = -1
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
