"""Mentor field operations - writing and updating MENTORS entries."""

from .changespec import (
    MentorEntry,
    MentorStatusLine,
    changespec_lock,
    is_error_suffix,
    is_running_agent_suffix,
    parse_project_file,
    write_changespec_atomic,
)


def _format_mentors_field(mentors: list[MentorEntry]) -> list[str]:
    """Format mentors as lines for the MENTORS field.

    Args:
        mentors: List of MentorEntry objects.

    Returns:
        List of formatted lines including "MENTORS:\n" header.
    """
    if not mentors:
        return []

    lines = ["MENTORS:\n"]
    for entry in mentors:
        # Format entry header: (<id>) <profile1> [<profile2> ...]
        profiles_str = " ".join(entry.profiles)
        lines.append(f"  ({entry.entry_id}) {profiles_str}\n")

        # Format status lines
        if entry.status_lines:
            for sl in entry.status_lines:
                # Build the line parts
                line_parts = [
                    f"      | {sl.profile_name}:{sl.mentor_name} - {sl.status}"
                ]

                # Add suffix
                if sl.suffix is not None or sl.duration is not None:
                    suffix_content = ""
                    if sl.suffix is not None and sl.suffix != "":
                        # Use suffix_type if available
                        if sl.suffix_type == "error" or (
                            sl.suffix_type is None and is_error_suffix(sl.suffix)
                        ):
                            suffix_content = f"!: {sl.suffix}"
                        elif sl.suffix_type == "running_agent" or (
                            sl.suffix_type is None
                            and is_running_agent_suffix(sl.suffix)
                        ):
                            suffix_content = f"@: {sl.suffix}" if sl.suffix else "@"
                        else:
                            suffix_content = sl.suffix
                    elif sl.duration:
                        # Plain duration suffix
                        suffix_content = sl.duration

                    if suffix_content:
                        line_parts.append(f" - ({suffix_content})")

                line_parts.append("\n")
                lines.append("".join(line_parts))

    return lines


def _apply_mentors_update(
    lines: list[str],
    changespec_name: str,
    mentors: list[MentorEntry],
) -> list[str]:
    """Apply MENTORS field update to file lines.

    Args:
        lines: Current file lines.
        changespec_name: NAME of the ChangeSpec to update.
        mentors: List of MentorEntry objects to write.

    Returns:
        Updated lines with MENTORS field modified.
    """
    updated_lines: list[str] = []
    in_target_changespec = False
    found_mentors = False
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this is a NAME field
        if line.startswith("NAME:"):
            current_name = line.split(":", 1)[1].strip()
            was_in_target = in_target_changespec
            in_target_changespec = current_name == changespec_name

            # If we were in target and didn't find MENTORS, insert before NAME
            if was_in_target and not found_mentors and mentors:
                updated_lines.extend(_format_mentors_field(mentors))
                found_mentors = True

            updated_lines.append(line)
            i += 1
            continue

        # If we're in the target ChangeSpec
        if in_target_changespec:
            # Check for MENTORS field
            if line.startswith("MENTORS:"):
                found_mentors = True
                # Skip old MENTORS content and write new content
                updated_lines.extend(_format_mentors_field(mentors))
                i += 1
                # Skip old mentors content
                while i < len(lines):
                    next_line = lines[i]
                    stripped = next_line.strip()
                    # Check if still in mentors field:
                    # - 2-space indented entry lines (start with "(" after stripping)
                    # - 6-space "| " prefixed status lines
                    if next_line.startswith("      | "):
                        # Status line
                        i += 1
                    elif (
                        next_line.startswith("  ")
                        and not next_line.startswith("      ")
                        and stripped.startswith("(")
                    ):
                        # Entry line
                        i += 1
                    else:
                        # End of MENTORS field
                        break
                continue

        updated_lines.append(line)
        i += 1

    # If we were in target at end and didn't find MENTORS, append it
    if in_target_changespec and not found_mentors and mentors:
        updated_lines.extend(_format_mentors_field(mentors))

    return updated_lines


def add_mentor_entry(
    project_file: str,
    changespec_name: str,
    entry_id: str,
    profile_names: list[str],
) -> bool:
    """Add a new MENTORS entry for a ChangeSpec.

    If an entry for the given entry_id already exists, the profile_names
    will be merged with the existing entry's profiles.

    Args:
        project_file: Path to the project file.
        changespec_name: Name of the ChangeSpec.
        entry_id: The commit entry ID (e.g., "1", "2").
        profile_names: List of profile names that were triggered.

    Returns:
        True if successful, False otherwise.
    """
    try:
        with changespec_lock(project_file):
            changespecs = parse_project_file(project_file)
            current_mentors: list[MentorEntry] = []
            for cs in changespecs:
                if cs.name == changespec_name:
                    current_mentors = list(cs.mentors) if cs.mentors else []
                    break

            # Check if entry already exists
            existing_entry: MentorEntry | None = None
            for entry in current_mentors:
                if entry.entry_id == entry_id:
                    existing_entry = entry
                    break

            if existing_entry:
                # Merge profiles
                for pname in profile_names:
                    if pname not in existing_entry.profiles:
                        existing_entry.profiles.append(pname)
            else:
                # Create new entry
                new_entry = MentorEntry(
                    entry_id=entry_id,
                    profiles=profile_names,
                    status_lines=[],
                )
                current_mentors.append(new_entry)

            # Write updated mentors
            with open(project_file, encoding="utf-8") as f:
                lines = f.readlines()

            updated_lines = _apply_mentors_update(
                lines, changespec_name, current_mentors
            )
            content = "".join(updated_lines)

            write_changespec_atomic(
                project_file,
                content,
                f"Add MENTORS entry ({entry_id}) for {changespec_name}",
            )
            return True
    except Exception:
        return False


def set_mentor_status(
    project_file: str,
    changespec_name: str,
    entry_id: str,
    profile_name: str,
    mentor_name: str,
    status: str,
    suffix: str | None = None,
    suffix_type: str | None = None,
    duration: str | None = None,
) -> bool:
    """Set or update the status for a specific mentor in a profile.

    Args:
        project_file: Path to the project file.
        changespec_name: Name of the ChangeSpec.
        entry_id: The commit entry ID (e.g., "1", "2").
        profile_name: The profile name.
        mentor_name: The mentor name.
        status: The status (RUNNING, PASSED, FAILED).
        suffix: Optional suffix (e.g., "mentor_complete-12345-251230_1530").
        suffix_type: Optional suffix type ("running_agent", "error", "plain").
        duration: Optional duration string (e.g., "0h2m15s").

    Returns:
        True if successful, False otherwise.
    """
    try:
        with changespec_lock(project_file):
            changespecs = parse_project_file(project_file)
            current_mentors: list[MentorEntry] = []
            for cs in changespecs:
                if cs.name == changespec_name:
                    current_mentors = list(cs.mentors) if cs.mentors else []
                    break

            # Find the entry
            target_entry: MentorEntry | None = None
            for entry in current_mentors:
                if entry.entry_id == entry_id:
                    target_entry = entry
                    break

            if target_entry is None:
                # Entry doesn't exist - create it
                target_entry = MentorEntry(
                    entry_id=entry_id,
                    profiles=[profile_name],
                    status_lines=[],
                )
                current_mentors.append(target_entry)

            # Find or create the status line
            if target_entry.status_lines is None:
                target_entry.status_lines = []

            existing_status_line: MentorStatusLine | None = None
            for sl in target_entry.status_lines:
                if sl.profile_name == profile_name and sl.mentor_name == mentor_name:
                    existing_status_line = sl
                    break

            if existing_status_line:
                # Update existing status line
                existing_status_line.status = status
                existing_status_line.suffix = suffix
                existing_status_line.suffix_type = suffix_type
                existing_status_line.duration = duration
            else:
                # Create new status line
                new_status_line = MentorStatusLine(
                    profile_name=profile_name,
                    mentor_name=mentor_name,
                    status=status,
                    duration=duration,
                    suffix=suffix,
                    suffix_type=suffix_type,
                )
                target_entry.status_lines.append(new_status_line)

            # Write updated mentors
            with open(project_file, encoding="utf-8") as f:
                lines = f.readlines()

            updated_lines = _apply_mentors_update(
                lines, changespec_name, current_mentors
            )
            content = "".join(updated_lines)

            write_changespec_atomic(
                project_file,
                content,
                f"Set mentor status {profile_name}:{mentor_name} -> {status}",
            )
            return True
    except Exception:
        return False
