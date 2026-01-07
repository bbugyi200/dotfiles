"""Comments operations - file updates and project file modifications."""

from ..changespec import (
    CommentEntry,
    changespec_lock,
    is_error_suffix,
    is_running_agent_suffix,
    write_changespec_atomic,
)


def _format_comments_field(comments: list[CommentEntry]) -> list[str]:
    """Format comments as lines for the COMMENTS field.

    Args:
        comments: List of CommentEntry objects.

    Returns:
        List of formatted lines including "COMMENTS:\\n" header.
    """
    if not comments:
        return []

    lines = ["COMMENTS:\n"]
    for comment in comments:
        # Format: [reviewer] path or [reviewer] path - (suffix) or - (!: msg) or - (~: msg) or - (@: msg)
        if comment.suffix:
            # Use suffix_type if available, fall back to message-based detection
            if comment.suffix_type == "error" or (
                comment.suffix_type is None and is_error_suffix(comment.suffix)
            ):
                lines.append(
                    f"  [{comment.reviewer}] {comment.file_path} - (!: {comment.suffix})\n"
                )
            elif comment.suffix_type == "running_agent" or (
                comment.suffix_type is None and is_running_agent_suffix(comment.suffix)
            ):
                lines.append(
                    f"  [{comment.reviewer}] {comment.file_path} - (@: {comment.suffix})\n"
                )
            elif comment.suffix_type == "killed_agent":
                lines.append(
                    f"  [{comment.reviewer}] {comment.file_path} - (~@: {comment.suffix})\n"
                )
            else:
                lines.append(
                    f"  [{comment.reviewer}] {comment.file_path} - ({comment.suffix})\n"
                )
        else:
            lines.append(f"  [{comment.reviewer}] {comment.file_path}\n")

    return lines


def _apply_comments_to_lines(
    lines: list[str],
    changespec_name: str,
    comments: list[CommentEntry] | None,
) -> str:
    """Apply COMMENTS field update to file lines.

    Args:
        lines: Current file lines.
        changespec_name: NAME of the ChangeSpec to update.
        comments: List of CommentEntry objects to write, or None to remove field.

    Returns:
        Updated file content as a string.
    """
    updated_lines: list[str] = []
    in_target_changespec = False
    found_comments = False
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this is a NAME field
        if line.startswith("NAME:"):
            current_name = line.split(":", 1)[1].strip()
            was_in_target = in_target_changespec
            in_target_changespec = current_name == changespec_name

            # If we were in target and didn't find COMMENTS, insert before NAME
            if was_in_target and not found_comments and comments:
                updated_lines.extend(_format_comments_field(comments))
                found_comments = True

            updated_lines.append(line)
            i += 1
            continue

        # If we're in the target ChangeSpec
        if in_target_changespec:
            # Check for COMMENTS field
            if line.startswith("COMMENTS:"):
                found_comments = True
                # Skip old COMMENTS content and write new content (if any)
                if comments:
                    updated_lines.extend(_format_comments_field(comments))
                i += 1
                # Skip old comments content
                while i < len(lines):
                    next_line = lines[i]
                    # Check if still in comments field (2-space indented)
                    if next_line.startswith("  ") and not next_line.startswith("    "):
                        stripped = next_line.strip()
                        # Comment entries start with [
                        if stripped.startswith("["):
                            i += 1
                        else:
                            break
                    else:
                        break
                continue

            # Check for end of ChangeSpec (another field or 2 blank lines)
            if line.strip() == "":
                next_idx = i + 1
                if next_idx < len(lines) and lines[next_idx].strip() == "":
                    # Two blank lines = end of ChangeSpec
                    if not found_comments and comments:
                        updated_lines.extend(_format_comments_field(comments))
                        found_comments = True

        updated_lines.append(line)
        i += 1

    # If we reached end of file while still in target changespec
    if in_target_changespec and not found_comments and comments:
        updated_lines.extend(_format_comments_field(comments))

    return "".join(updated_lines)


def _write_comments_unlocked(
    project_file: str,
    changespec_name: str,
    comments: list[CommentEntry] | None,
) -> None:
    """Write COMMENTS field while caller holds lock.

    This is a low-level function that should only be called while
    holding a changespec_lock on the project_file.

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        comments: List of CommentEntry objects to write, or None to remove field.
    """
    with open(project_file, encoding="utf-8") as f:
        lines = f.readlines()

    updated_content = _apply_comments_to_lines(lines, changespec_name, comments)

    commit_msg = (
        f"Update COMMENTS for {changespec_name}"
        if comments
        else f"Remove COMMENTS for {changespec_name}"
    )
    write_changespec_atomic(project_file, updated_content, commit_msg)


def update_changespec_comments_field(
    project_file: str,
    changespec_name: str,
    comments: list[CommentEntry] | None,
) -> bool:
    """Update the COMMENTS field in the project file.

    Acquires a lock for the entire read-modify-write cycle.

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        comments: List of CommentEntry objects to write, or None to remove field.

    Returns:
        True if update succeeded, False otherwise.
    """
    try:
        with changespec_lock(project_file):
            _write_comments_unlocked(project_file, changespec_name, comments)
        return True
    except Exception:
        return False


def add_comment_entry(
    project_file: str,
    changespec_name: str,
    entry: CommentEntry,
    existing_comments: list[CommentEntry] | None = None,
) -> bool:
    """Add a single comment entry to a ChangeSpec.

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        entry: The CommentEntry to add.
        existing_comments: Existing comments list (optional, will be loaded if None).

    Returns:
        True if update succeeded, False otherwise.
    """
    # If comments provided, use them directly (caller responsible for freshness)
    if existing_comments is not None:
        comments = list(existing_comments)
        # Check if entry with same reviewer already exists
        for i, c in enumerate(comments):
            if c.reviewer == entry.reviewer:
                comments[i] = entry
                return update_changespec_comments_field(
                    project_file, changespec_name, comments
                )
        comments.append(entry)
        return update_changespec_comments_field(project_file, changespec_name, comments)

    # Otherwise, acquire lock and read fresh state
    from ..changespec import parse_project_file

    try:
        with changespec_lock(project_file):
            changespecs = parse_project_file(project_file)
            current_comments: list[CommentEntry] = []
            for cs in changespecs:
                if cs.name == changespec_name:
                    current_comments = list(cs.comments) if cs.comments else []
                    break

            # Check if entry with same reviewer already exists
            for i, c in enumerate(current_comments):
                if c.reviewer == entry.reviewer:
                    current_comments[i] = entry
                    _write_comments_unlocked(
                        project_file, changespec_name, current_comments
                    )
                    return True

            current_comments.append(entry)
            _write_comments_unlocked(project_file, changespec_name, current_comments)
            return True
    except Exception:
        return False


def remove_comment_entry(
    project_file: str,
    changespec_name: str,
    reviewer: str,
    existing_comments: list[CommentEntry] | None = None,
) -> bool:
    """Remove a comment entry by reviewer from a ChangeSpec.

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        reviewer: The reviewer identifier to remove.
        existing_comments: Existing comments list (optional, will be loaded if None).

    Returns:
        True if update succeeded, False otherwise.
    """
    # If comments provided, use them directly (caller responsible for freshness)
    if existing_comments is not None:
        if not existing_comments:
            return True  # Nothing to remove
        comments = [c for c in existing_comments if c.reviewer != reviewer]
        if not comments:
            return update_changespec_comments_field(project_file, changespec_name, None)
        return update_changespec_comments_field(project_file, changespec_name, comments)

    # Otherwise, acquire lock and read fresh state
    from ..changespec import parse_project_file

    try:
        with changespec_lock(project_file):
            changespecs = parse_project_file(project_file)
            current_comments: list[CommentEntry] = []
            for cs in changespecs:
                if cs.name == changespec_name:
                    current_comments = list(cs.comments) if cs.comments else []
                    break

            if not current_comments:
                return True  # Nothing to remove

            comments = [c for c in current_comments if c.reviewer != reviewer]
            if not comments:
                _write_comments_unlocked(project_file, changespec_name, None)
            else:
                _write_comments_unlocked(project_file, changespec_name, comments)
            return True
    except Exception:
        return False


def set_comment_suffix(
    project_file: str,
    changespec_name: str,
    reviewer: str,
    suffix: str,
    comments: list[CommentEntry],
    suffix_type: str | None = None,
) -> bool:
    """Set a suffix on a specific comment entry.

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        reviewer: The reviewer identifier to update.
        suffix: The suffix to set.
        comments: Current list of CommentEntry objects.
        suffix_type: The suffix type ("error", "running_agent", or None).

    Returns:
        True if update succeeded, False otherwise.
    """
    updated_comments = []
    for comment in comments:
        if comment.reviewer == reviewer:
            updated_comments.append(
                CommentEntry(
                    reviewer=comment.reviewer,
                    file_path=comment.file_path,
                    suffix=suffix,
                    suffix_type=suffix_type,
                )
            )
        else:
            updated_comments.append(comment)

    return update_changespec_comments_field(
        project_file, changespec_name, updated_comments
    )


def clear_comment_suffix(
    project_file: str,
    changespec_name: str,
    reviewer: str,
    comments: list[CommentEntry],
) -> bool:
    """Clear the suffix from a specific comment entry.

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        reviewer: The reviewer identifier to update.
        comments: Current list of CommentEntry objects.

    Returns:
        True if update succeeded, False otherwise.
    """
    updated_comments = []
    for comment in comments:
        if comment.reviewer == reviewer and comment.suffix is not None:
            updated_comments.append(
                CommentEntry(
                    reviewer=comment.reviewer,
                    file_path=comment.file_path,
                    suffix=None,
                )
            )
        else:
            updated_comments.append(comment)

    return update_changespec_comments_field(
        project_file, changespec_name, updated_comments
    )


def update_comment_suffix_type(
    project_file: str,
    changespec_name: str,
    reviewer: str,
    new_suffix_type: str,
    comments: list[CommentEntry],
) -> bool:
    """Update the suffix_type of a specific comment entry.

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        reviewer: The reviewer identifier to update.
        new_suffix_type: The new suffix type ("error" only).
        comments: Current list of CommentEntry objects.

    Returns:
        True if update succeeded, False otherwise.
    """
    updated_comments: list[CommentEntry] = []
    found = False

    for comment in comments:
        if (
            comment.reviewer == reviewer
            and comment.suffix
            and comment.suffix_type == "error"
        ):
            found = True
            updated_comments.append(
                CommentEntry(
                    reviewer=comment.reviewer,
                    file_path=comment.file_path,
                    suffix=comment.suffix,
                    suffix_type=new_suffix_type,
                )
            )
        else:
            updated_comments.append(comment)

    if not found:
        return False

    return update_changespec_comments_field(
        project_file, changespec_name, updated_comments
    )


def mark_comment_agents_as_killed(
    comments: list[CommentEntry],
    killed_agents: list[tuple[CommentEntry, int]],
) -> list[CommentEntry]:
    """Update comment entries to mark killed agent processes.

    Changes suffix_type from "running_agent" to "killed_agent" for
    the specified comment entries.

    Args:
        comments: List of all CommentEntry objects.
        killed_agents: List of (comment_entry, pid) from kill operation.

    Returns:
        Updated list of CommentEntry objects with modified suffix_type.
    """
    # Build lookup set of (reviewer, suffix) for killed agents
    killed_lookup: set[tuple[str, str]] = {
        (comment.reviewer, comment.suffix or "") for comment, pid in killed_agents
    }

    updated_comments: list[CommentEntry] = []
    for comment in comments:
        if (comment.reviewer, comment.suffix or "") in killed_lookup:
            # Create new comment entry with killed_agent type
            updated_comment = CommentEntry(
                reviewer=comment.reviewer,
                file_path=comment.file_path,
                suffix=comment.suffix,
                suffix_type="killed_agent",
            )
            updated_comments.append(updated_comment)
        else:
            updated_comments.append(comment)

    return updated_comments
