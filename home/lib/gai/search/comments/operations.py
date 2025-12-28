"""Comments operations - file updates and project file modifications."""

import os
import subprocess
import tempfile

from ..changespec import CommentEntry, is_error_suffix
from .core import get_comments_file_path


def save_critique_comments(name: str, timestamp: str) -> str | None:
    """Run critique_comments and save output to a JSON file.

    Args:
        name: The ChangeSpec name (used for getting workspace).
        timestamp: The timestamp for the filename.

    Returns:
        Path to the saved comments file, or None if no comments.
    """
    try:
        result = subprocess.run(
            ["critique_comments", name],
            capture_output=True,
            text=True,
        )

        # If there's no output, there are no comments
        output = result.stdout.strip()
        if not output:
            return None

        # Save the comments to a file
        file_path = get_comments_file_path(name, "critique", timestamp)
        with open(file_path, "w") as f:
            f.write(output)

        # Return path with ~ for home directory
        from pathlib import Path

        return file_path.replace(str(Path.home()), "~")

    except Exception:
        return None


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
        # Format: [reviewer] path or [reviewer] path - (suffix) or - (!: msg) or - (~: msg)
        if comment.suffix:
            # Use suffix_type if available, fall back to message-based detection
            if comment.suffix_type == "error" or (
                comment.suffix_type is None and is_error_suffix(comment.suffix)
            ):
                lines.append(
                    f"  [{comment.reviewer}] {comment.file_path} - (!: {comment.suffix})\n"
                )
            elif comment.suffix_type == "acknowledged":
                lines.append(
                    f"  [{comment.reviewer}] {comment.file_path} - (~: {comment.suffix})\n"
                )
            else:
                lines.append(
                    f"  [{comment.reviewer}] {comment.file_path} - ({comment.suffix})\n"
                )
        else:
            lines.append(f"  [{comment.reviewer}] {comment.file_path}\n")

    return lines


def update_changespec_comments_field(
    project_file: str,
    changespec_name: str,
    comments: list[CommentEntry] | None,
) -> bool:
    """Update the COMMENTS field in the project file.

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        comments: List of CommentEntry objects to write, or None to remove field.

    Returns:
        True if update succeeded, False otherwise.
    """
    try:
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()

        # Find the ChangeSpec and update/add COMMENTS field
        updated_lines: list[str] = []
        in_target_changespec = False
        current_name = None
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
                        if next_line.startswith("  ") and not next_line.startswith(
                            "    "
                        ):
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
    if existing_comments is None:
        from ..changespec import parse_project_file

        changespecs = parse_project_file(project_file)
        for cs in changespecs:
            if cs.name == changespec_name:
                existing_comments = cs.comments
                break

    comments = list(existing_comments) if existing_comments else []

    # Check if entry with same reviewer already exists
    for i, c in enumerate(comments):
        if c.reviewer == entry.reviewer:
            # Replace existing entry
            comments[i] = entry
            return update_changespec_comments_field(
                project_file, changespec_name, comments
            )

    # Add new entry
    comments.append(entry)
    return update_changespec_comments_field(project_file, changespec_name, comments)


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
    if existing_comments is None:
        from ..changespec import parse_project_file

        changespecs = parse_project_file(project_file)
        for cs in changespecs:
            if cs.name == changespec_name:
                existing_comments = cs.comments
                break

    if not existing_comments:
        return True  # Nothing to remove

    comments = [c for c in existing_comments if c.reviewer != reviewer]

    # If no comments left, remove the field entirely
    if not comments:
        return update_changespec_comments_field(project_file, changespec_name, None)

    return update_changespec_comments_field(project_file, changespec_name, comments)


def set_comment_suffix(
    project_file: str,
    changespec_name: str,
    reviewer: str,
    suffix: str,
    comments: list[CommentEntry],
) -> bool:
    """Set a suffix on a specific comment entry.

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        reviewer: The reviewer identifier to update.
        suffix: The suffix to set.
        comments: Current list of CommentEntry objects.

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
        new_suffix_type: The new suffix type ("acknowledged" or "error").
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
