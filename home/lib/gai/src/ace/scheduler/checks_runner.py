"""Background periodic checks for the axe scheduler (is_cl_submitted, critique_comments).

This module provides non-blocking execution of CL status and comment checks,
following the same pattern as hooks (subprocess.Popen + file-based polling).
"""

import os
import re
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from gai_utils import generate_timestamp
from status_state_machine import transition_changespec_status

from ..changespec import ChangeSpec, CommentEntry, is_plain_suffix
from ..cl_status import is_parent_submitted
from ..comments import (
    generate_comments_timestamp,
    get_comments_file_path,
    is_timestamp_suffix,
    remove_comment_entry,
    update_changespec_comments_field,
)
from ..sync_cache import update_last_checked

# Type alias for log callback
LogCallback = Callable[[str, str], None]

# Check type - must be defined before constants
CheckType = Literal["cl_submitted", "reviewer_comments", "author_comments"]

# Check type constants
CHECK_TYPE_CL_SUBMITTED: CheckType = "cl_submitted"
CHECK_TYPE_REVIEWER_COMMENTS: CheckType = "reviewer_comments"
CHECK_TYPE_AUTHOR_COMMENTS: CheckType = "author_comments"

# Completion marker (consistent with hooks/workflows)
CHECK_COMPLETE_MARKER = "===CHECK_COMPLETE=== "

# Exit code meanings for critique_comments command
_CRITIQUE_COMMENTS_EXIT_CODES: dict[int, str] = {
    1: "usage error",
    2: "missing dependency",
    3: "invalid CL number",
    4: "RPC failure",
    5: "JSON parsing failure",
}


@dataclass
class _PendingCheck:
    """Represents a pending background check."""

    changespec_name: str
    check_type: CheckType
    timestamp: str
    output_path: str


def _get_checks_directory() -> str:
    """Get the path to the checks output directory (~/.gai/checks/)."""
    return os.path.expanduser("~/.gai/checks")


def _ensure_checks_directory() -> None:
    """Ensure the checks directory exists."""
    checks_dir = _get_checks_directory()
    Path(checks_dir).mkdir(parents=True, exist_ok=True)


def _get_check_output_path(name: str, check_type: CheckType, timestamp: str) -> str:
    """Get the output file path for a check run.

    Args:
        name: The ChangeSpec name.
        check_type: The type of check.
        timestamp: The timestamp in YYmmdd_HHMMSS format.

    Returns:
        Full path to the check output file.
    """
    _ensure_checks_directory()
    checks_dir = _get_checks_directory()
    # Replace non-alphanumeric chars with underscore for safe filename
    safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    filename = f"{safe_name}-{check_type}-{timestamp}.txt"
    return os.path.join(checks_dir, filename)


def _extract_cl_number(cl_url: str | None) -> str | None:
    """Extract the CL number from a CL URL.

    Args:
        cl_url: The CL URL in the format http://cl/123456789

    Returns:
        The CL number as a string, or None if the URL is invalid or None.
    """
    if not cl_url:
        return None

    # Match http://cl/<number> or https://cl/<number>
    match = re.match(r"https?://cl/(\d+)", cl_url)
    if match:
        return match.group(1)

    return None


def start_cl_submitted_check(
    changespec: ChangeSpec,
    workspace_dir: str | None,
    log: LogCallback,
) -> str | None:
    """Start is_cl_submitted check as a background process.

    Args:
        changespec: The ChangeSpec to check.
        workspace_dir: The workspace directory to run the command in.
        log: Logging callback.

    Returns:
        Update message if check was started, None if failed.
    """
    cl_number = _extract_cl_number(changespec.cl)
    if not cl_number:
        return None

    timestamp = generate_timestamp()
    output_path = _get_check_output_path(
        changespec.name, CHECK_TYPE_CL_SUBMITTED, timestamp
    )

    # Create wrapper script
    wrapper_script = f"""#!/bin/bash
is_cl_submitted {cl_number}
exit_code=$?
echo ""
echo "{CHECK_COMPLETE_MARKER}EXIT_CODE: $exit_code"
exit $exit_code
"""

    # Write wrapper script to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sh", delete=False
    ) as wrapper_file:
        wrapper_file.write(wrapper_script)
        wrapper_path = wrapper_file.name

    os.chmod(wrapper_path, 0o755)

    # Start as background process
    try:
        with open(output_path, "w") as output_file:
            subprocess.Popen(
                [wrapper_path],
                cwd=workspace_dir,
                stdout=output_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        return "Started cl_submitted check"
    except Exception as e:
        log(f"Failed to start cl_submitted check for {changespec.name}: {e}", "red")
        return None


def start_reviewer_comments_check(
    changespec: ChangeSpec,
    workspace_dir: str,
    log: LogCallback,
) -> str | None:
    """Start critique_comments check for reviewer comments as a background process.

    Args:
        changespec: The ChangeSpec to check.
        workspace_dir: The workspace directory to run the command in.
        log: Logging callback.

    Returns:
        Update message if check was started, None if failed.
    """
    timestamp = generate_timestamp()
    output_path = _get_check_output_path(
        changespec.name, CHECK_TYPE_REVIEWER_COMMENTS, timestamp
    )

    # Create wrapper script - captures output and writes completion marker
    wrapper_script = f"""#!/bin/bash
critique_comments {changespec.name} 2>&1
exit_code=$?
echo ""
echo "{CHECK_COMPLETE_MARKER}EXIT_CODE: $exit_code"
exit $exit_code
"""

    # Write wrapper script to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sh", delete=False
    ) as wrapper_file:
        wrapper_file.write(wrapper_script)
        wrapper_path = wrapper_file.name

    os.chmod(wrapper_path, 0o755)

    # Start as background process
    try:
        with open(output_path, "w") as output_file:
            subprocess.Popen(
                [wrapper_path],
                cwd=workspace_dir,
                stdout=output_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        return "Started reviewer_comments check"
    except Exception as e:
        log(
            f"Failed to start reviewer_comments check for {changespec.name}: {e}",
            "red",
        )
        return None


def start_author_comments_check(
    changespec: ChangeSpec,
    workspace_dir: str,
    log: LogCallback,
) -> str | None:
    """Start critique_comments --me check for author comments as a background process.

    Args:
        changespec: The ChangeSpec to check.
        workspace_dir: The workspace directory to run the command in.
        log: Logging callback.

    Returns:
        Update message if check was started, None if failed.
    """
    timestamp = generate_timestamp()
    output_path = _get_check_output_path(
        changespec.name, CHECK_TYPE_AUTHOR_COMMENTS, timestamp
    )

    # Create wrapper script - captures output and writes completion marker
    wrapper_script = f"""#!/bin/bash
critique_comments --me {changespec.name} 2>&1
exit_code=$?
echo ""
echo "{CHECK_COMPLETE_MARKER}EXIT_CODE: $exit_code"
exit $exit_code
"""

    # Write wrapper script to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sh", delete=False
    ) as wrapper_file:
        wrapper_file.write(wrapper_script)
        wrapper_path = wrapper_file.name

    os.chmod(wrapper_path, 0o755)

    # Start as background process
    try:
        with open(output_path, "w") as output_file:
            subprocess.Popen(
                [wrapper_path],
                cwd=workspace_dir,
                stdout=output_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        return "Started author_comments check"
    except Exception as e:
        log(
            f"Failed to start author_comments check for {changespec.name}: {e}",
            "red",
        )
        return None


def _get_pending_checks(changespec: ChangeSpec) -> list[_PendingCheck]:
    """Get all pending background checks for a ChangeSpec.

    Scans ~/.gai/checks/ for files matching this changespec's name.

    Args:
        changespec: The ChangeSpec to find checks for.

    Returns:
        List of _PendingCheck objects.
    """
    checks_dir = _get_checks_directory()
    if not os.path.exists(checks_dir):
        return []

    # Create safe name pattern
    safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", changespec.name)
    pending: list[_PendingCheck] = []

    for filename in os.listdir(checks_dir):
        # Parse filename: <safe_name>-<check_type>-<timestamp>.txt
        if not filename.endswith(".txt"):
            continue

        # Match pattern: <safe_name>-<check_type>-<timestamp>.txt
        pattern = rf"^{re.escape(safe_name)}-(\w+)-(\d{{6}}_\d{{6}})\.txt$"
        match = re.match(pattern, filename)
        if match:
            check_type_str = match.group(1)
            timestamp = match.group(2)

            # Validate check type
            if check_type_str in (
                CHECK_TYPE_CL_SUBMITTED,
                CHECK_TYPE_REVIEWER_COMMENTS,
                CHECK_TYPE_AUTHOR_COMMENTS,
            ):
                pending.append(
                    _PendingCheck(
                        changespec_name=changespec.name,
                        check_type=check_type_str,  # type: ignore[arg-type]
                        timestamp=timestamp,
                        output_path=os.path.join(checks_dir, filename),
                    )
                )

    return pending


def _parse_check_completion(output_path: str) -> tuple[bool, int, str]:
    """Parse a check output file for completion status.

    Args:
        output_path: Path to the output file.

    Returns:
        Tuple of (is_complete, exit_code, content_before_marker).
    """
    if not os.path.exists(output_path):
        return False, -1, ""

    try:
        with open(output_path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return False, -1, ""

    # Look for completion marker
    marker_pos = content.rfind(CHECK_COMPLETE_MARKER)
    if marker_pos == -1:
        return False, -1, ""

    # Parse exit code
    try:
        after_marker = content[marker_pos + len(CHECK_COMPLETE_MARKER) :].strip()
        # Format: "EXIT_CODE: <code>"
        if after_marker.startswith("EXIT_CODE:"):
            exit_code = int(after_marker.split(":")[1].strip().split()[0])
        else:
            exit_code = 1
    except (ValueError, IndexError):
        exit_code = 1

    # Get content before marker (the actual command output)
    content_before = content[:marker_pos].strip()

    return True, exit_code, content_before


def _handle_cl_submitted_completion(
    changespec: ChangeSpec,
    exit_code: int,
    log: LogCallback,
) -> str | None:
    """Handle completed is_cl_submitted check.

    Args:
        changespec: The ChangeSpec to update.
        exit_code: The exit code from the check (0 = submitted).
        log: Logging callback.

    Returns:
        Update message if status changed, None otherwise.
    """
    # Update the last_checked timestamp
    update_last_checked(changespec.name)

    # Exit code 0 means submitted
    if exit_code == 0 and is_parent_submitted(changespec):
        from ..sync_cache import clear_cache_entry

        success, old_status, _ = transition_changespec_status(
            changespec.file_path,
            changespec.name,
            "Submitted",
            validate=False,
        )

        if success:
            clear_cache_entry(changespec.name)
            return f"Status changed {old_status} -> Submitted"

    return None


def _handle_reviewer_comments_completion(
    changespec: ChangeSpec,
    exit_code: int,
    content: str,
    log: LogCallback,
) -> list[str]:
    """Handle completed critique_comments check for reviewer comments.

    Args:
        changespec: The ChangeSpec to update.
        exit_code: The exit code from the check.
        content: The command output (comment content).
        log: Logging callback.

    Returns:
        List of update messages.
    """
    updates: list[str] = []

    # Check if command failed
    if exit_code != 0:
        meaning = _CRITIQUE_COMMENTS_EXIT_CODES.get(exit_code, "unknown error")
        log(
            f"critique_comments failed for {changespec.name}: {meaning} "
            f"(exit code {exit_code})",
            "red",
        )
        return updates

    has_comments = bool(content)

    # Find existing [reviewer] entry
    existing_reviewer_entry: CommentEntry | None = None
    if changespec.comments:
        for entry in changespec.comments:
            if entry.reviewer == "critique":
                existing_reviewer_entry = entry
                break

    if has_comments:
        # If no existing entry, create a new one with the comments file
        if existing_reviewer_entry is None:
            timestamp = generate_comments_timestamp()
            file_path = get_comments_file_path(changespec.name, "critique", timestamp)

            # Save output to file
            with open(file_path, "w") as f:
                f.write(content)

            # Add the new entry (shorten path with ~ for home directory)
            display_path = file_path.replace(str(Path.home()), "~")
            new_entry = CommentEntry(
                reviewer="critique",
                file_path=display_path,
                suffix=None,
            )
            new_comments = list(changespec.comments) if changespec.comments else []
            new_comments.append(new_entry)
            update_changespec_comments_field(
                changespec.file_path,
                changespec.name,
                new_comments,
            )
            updates.append("Added [reviewer] comment entry")
    else:
        # No comments - clear the [reviewer] entry if it exists and:
        # - has no suffix, OR
        # - has a plain suffix (commit reference like "7d")
        if existing_reviewer_entry is not None and (
            existing_reviewer_entry.suffix is None
            or is_plain_suffix(existing_reviewer_entry.suffix)
        ):
            remove_comment_entry(
                changespec.file_path,
                changespec.name,
                "critique",
                changespec.comments,
            )
            updates.append("Removed [critique] comment entry (no comments)")

    return updates


def _handle_author_comments_completion(
    changespec: ChangeSpec,
    exit_code: int,
    content: str,
    log: LogCallback,
) -> list[str]:
    """Handle completed critique_comments --me check for author comments.

    Args:
        changespec: The ChangeSpec to update.
        exit_code: The exit code from the check.
        content: The command output (comment content).
        log: Logging callback.

    Returns:
        List of update messages.
    """
    updates: list[str] = []

    # Check if command failed
    if exit_code != 0:
        meaning = _CRITIQUE_COMMENTS_EXIT_CODES.get(exit_code, "unknown error")
        log(
            f"critique_comments --me failed for {changespec.name}: {meaning} "
            f"(exit code {exit_code})",
            "red",
        )
        return updates

    has_comments = bool(content)

    # Find existing [critique:me] entry
    existing_author_entry: CommentEntry | None = None
    if changespec.comments:
        for entry in changespec.comments:
            if entry.reviewer == "critique:me":
                existing_author_entry = entry
                break

    if has_comments:
        # If no existing entry, create a new one with the comments file
        if existing_author_entry is None:
            timestamp = generate_comments_timestamp()
            file_path = get_comments_file_path(
                changespec.name, "critique_me", timestamp
            )

            # Save output to file
            with open(file_path, "w") as f:
                f.write(content)

            # Start with existing comments (minus any [critique] entries)
            new_comments = []
            removed_reviewer = False
            if changespec.comments:
                for entry in changespec.comments:
                    if entry.reviewer == "critique":
                        removed_reviewer = True
                    else:
                        new_comments.append(entry)

            if removed_reviewer:
                updates.append(
                    "Removed [critique] entry (critique:me comments take precedence)"
                )

            # Add the new [critique:me] entry
            display_path = file_path.replace(str(Path.home()), "~")
            new_entry = CommentEntry(
                reviewer="critique:me",
                file_path=display_path,
                suffix=None,
            )
            new_comments.append(new_entry)
            update_changespec_comments_field(
                changespec.file_path,
                changespec.name,
                new_comments,
            )
            updates.append("Added [critique:me] comment entry")
    else:
        # No comments - clear [critique:me] entry if it exists and CRS is not running
        if existing_author_entry is not None and not is_timestamp_suffix(
            existing_author_entry.suffix
        ):
            remove_comment_entry(
                changespec.file_path,
                changespec.name,
                "critique:me",
                changespec.comments,
            )
            updates.append("Removed [critique:me] comment entry (no comments)")

    return updates


def _cleanup_check_file(output_path: str) -> None:
    """Remove completed check output file."""
    try:
        os.remove(output_path)
    except OSError:
        pass


def check_pending_checks(
    changespec: ChangeSpec,
    log: LogCallback,
) -> list[str]:
    """Poll for completion of pending background checks.

    Scans for pending checks, processes any that have completed,
    and returns update messages.

    Args:
        changespec: The ChangeSpec to check.
        log: Logging callback.

    Returns:
        List of update messages.
    """
    updates: list[str] = []
    pending = _get_pending_checks(changespec)

    for check in pending:
        is_complete, exit_code, content = _parse_check_completion(check.output_path)

        if not is_complete:
            continue

        # Handle completion based on check type
        if check.check_type == CHECK_TYPE_CL_SUBMITTED:
            update = _handle_cl_submitted_completion(changespec, exit_code, log)
            if update:
                updates.append(update)
        elif check.check_type == CHECK_TYPE_REVIEWER_COMMENTS:
            check_updates = _handle_reviewer_comments_completion(
                changespec, exit_code, content, log
            )
            updates.extend(check_updates)
        elif check.check_type == CHECK_TYPE_AUTHOR_COMMENTS:
            check_updates = _handle_author_comments_completion(
                changespec, exit_code, content, log
            )
            updates.extend(check_updates)

        # Cleanup the output file
        _cleanup_check_file(check.output_path)

    return updates


def has_pending_check(changespec: ChangeSpec, check_type: CheckType) -> bool:
    """Check if a specific check type is already pending for a ChangeSpec.

    Args:
        changespec: The ChangeSpec to check.
        check_type: The type of check to look for.

    Returns:
        True if a check of this type is pending, False otherwise.
    """
    pending = _get_pending_checks(changespec)
    return any(check.check_type == check_type for check in pending)
