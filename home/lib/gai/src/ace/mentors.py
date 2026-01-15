"""Mentor field operations - writing and updating MENTORS entries."""

from status_state_machine import remove_workspace_suffix

from .changespec import (
    MentorEntry,
    MentorStatusLine,
    changespec_lock,
    is_error_suffix,
    is_running_agent_suffix,
    parse_commit_entry_id,
    parse_project_file,
    write_changespec_atomic,
)


def get_latest_proposal_for_entry(
    project_file: str,
    cl_name: str,
    base_entry_id: int,
    mentor_name: str | None = None,
) -> str | None:
    """Find the latest (highest letter) proposal for a base entry ID.

    This is used to associate a FAILED mentor with the proposal it created.
    For example, if entry_id is 2 and proposals "2a" and "2b" exist,
    returns "2b" (the latest).

    Args:
        project_file: Path to the project file.
        cl_name: Name of the ChangeSpec.
        base_entry_id: The base entry number (e.g., 2 for proposals "2a", "2b").
        mentor_name: If provided, only match proposals created by this mentor
            (proposals with notes starting with "[mentor:<name>]").

    Returns:
        Proposal ID like "2a" or None if no proposals exist for this entry.
    """
    try:
        changespecs = parse_project_file(project_file)
        for cs in changespecs:
            if cs.name == cl_name and cs.commits:
                # Find all proposals with this base number
                proposals = [
                    c
                    for c in cs.commits
                    if c.number == base_entry_id
                    and c.proposal_letter is not None
                    and (
                        mentor_name is None
                        or c.note.startswith(f"[mentor:{mentor_name}]")
                    )
                ]
                if not proposals:
                    return None
                # Return the one with the highest letter
                proposals.sort(key=lambda p: p.proposal_letter or "")
                latest = proposals[-1]
                return f"{latest.number}{latest.proposal_letter}"
        return None
    except Exception:
        return None


def _format_profile_with_count(
    profile_name: str,
    status_lines: list[MentorStatusLine] | None,
    is_wip: bool = False,
) -> str:
    """Format profile name with [started/total] count.

    Args:
        profile_name: Name of the profile.
        status_lines: List of MentorStatusLine objects to count started mentors.
        is_wip: If True, only count mentors with run_on_wip=True.

    Returns:
        Formatted string like "profile[2/3]".
    """
    from mentor_config import get_mentor_profile_by_name

    profile_config = get_mentor_profile_by_name(profile_name)
    if profile_config is None:
        return profile_name  # Fallback if profile not found in config

    # Calculate total based on WIP status
    if is_wip:
        total = sum(1 for m in profile_config.mentors if m.run_on_wip)
        wip_mentor_names = {
            m.mentor_name for m in profile_config.mentors if m.run_on_wip
        }
    else:
        total = len(profile_config.mentors)
        wip_mentor_names = None

    started = 0
    if status_lines:
        for sl in status_lines:
            if sl.profile_name == profile_name:
                # For WIP, only count status lines for run_on_wip mentors
                if wip_mentor_names is None or sl.mentor_name in wip_mentor_names:
                    started += 1

    return f"{profile_name}[{started}/{total}]"


def _format_mentors_field(mentors: list[MentorEntry]) -> list[str]:
    """Format mentors as lines for the MENTORS field.

    Args:
        mentors: List of MentorEntry objects.

    Returns:
        List of formatted lines including "MENTORS:\n" header.
    """
    from mentor_config import profile_has_wip_mentors

    if not mentors:
        return []

    lines = ["MENTORS:\n"]
    for entry in mentors:
        # Filter profiles for WIP entries - only show profiles with run_on_wip mentors
        if entry.is_wip:
            visible_profiles = [p for p in entry.profiles if profile_has_wip_mentors(p)]
        else:
            visible_profiles = entry.profiles

        # Skip entry entirely if no visible profiles
        if not visible_profiles:
            continue

        # Format entry header: (<id>) <profile1>[x/y] [<profile2>[x/y] ...]
        profiles_with_counts = [
            _format_profile_with_count(p, entry.status_lines, is_wip=entry.is_wip)
            for p in visible_profiles
        ]
        profiles_str = " ".join(profiles_with_counts)
        wip_suffix = " #WIP" if entry.is_wip else ""
        lines.append(f"  ({entry.entry_id}) {profiles_str}{wip_suffix}\n")

        # Format status lines
        if entry.status_lines:
            for sl in entry.status_lines:
                # Build the line parts with optional timestamp prefix
                # Only show timestamp for completed mentors (not RUNNING)
                if sl.timestamp and sl.status != "RUNNING":
                    line_parts = [
                        f"      | [{sl.timestamp}] "
                        f"{sl.profile_name}:{sl.mentor_name} - {sl.status}"
                    ]
                else:
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
                        elif sl.suffix_type == "entry_ref":
                            # Entry reference (e.g., "2a") - no prefix needed
                            suffix_content = sl.suffix
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
                # Remove trailing blank lines before inserting MENTORS
                # (parser treats 2+ blank lines as end of changespec)
                while updated_lines and updated_lines[-1].strip() == "":
                    updated_lines.pop()
                updated_lines.extend(_format_mentors_field(mentors))
                # Add one blank line before next changespec
                updated_lines.append("\n")
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
    is_wip: bool = False,
) -> bool:
    """Add a new MENTORS entry for a ChangeSpec.

    If an entry for the given entry_id already exists, the profile_names
    will be merged with the existing entry's profiles.

    Args:
        project_file: Path to the project file.
        changespec_name: Name of the ChangeSpec.
        entry_id: The commit entry ID (e.g., "1", "2").
        profile_names: List of profile names that were triggered.
        is_wip: True if entry is being created during WIP status.

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
                    is_wip=is_wip,
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
    timestamp: str | None = None,
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
        timestamp: Optional timestamp in YYmmdd_HHMMSS format for chat file link.
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
            changespec_status: str | None = None
            for cs in changespecs:
                if cs.name == changespec_name:
                    current_mentors = list(cs.mentors) if cs.mentors else []
                    changespec_status = cs.status
                    break

            # Determine if changespec is in WIP status
            is_wip_status = (
                changespec_status is not None
                and remove_workspace_suffix(changespec_status) == "WIP"
            )

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
                    is_wip=is_wip_status,
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
                # Don't overwrite killed_agent status - this prevents a killed mentor
                # from overwriting its status if it survives the SIGTERM
                if existing_status_line.suffix_type == "killed_agent":
                    return True

                # Update existing status line
                existing_status_line.status = status
                # Only update timestamp if provided (preserve existing if not)
                if timestamp is not None:
                    existing_status_line.timestamp = timestamp
                existing_status_line.suffix = suffix
                existing_status_line.suffix_type = suffix_type
                existing_status_line.duration = duration
            else:
                # Create new status line
                new_status_line = MentorStatusLine(
                    profile_name=profile_name,
                    mentor_name=mentor_name,
                    status=status,
                    timestamp=timestamp,
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


def update_changespec_mentors_field(
    project_file: str,
    changespec_name: str,
    mentors: list[MentorEntry],
) -> bool:
    """Update the MENTORS field for a ChangeSpec.

    Replaces the entire MENTORS field with the provided mentor entries.
    This is useful for bulk updates like marking killed agents.

    Args:
        project_file: Path to the project file.
        changespec_name: NAME of the ChangeSpec to update.
        mentors: List of MentorEntry objects to write.

    Returns:
        True if successful, False otherwise.
    """
    try:
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()

        updated_lines = _apply_mentors_update(lines, changespec_name, mentors)
        content = "".join(updated_lines)

        write_changespec_atomic(
            project_file,
            content,
            f"Update MENTORS field for {changespec_name}",
        )
        return True
    except Exception:
        return False


def clear_mentor_wip_flags(project_file: str, changespec_name: str) -> bool:
    """Clear is_wip flag and add all matching profiles for the LAST MENTORS entry.

    This is called when transitioning from WIP to Drafted status. It:
    1. Finds the MENTORS entry with the highest entry_id that has is_wip=True
    2. Adds ALL matching profiles (not just WIP-enabled ones) to that entry
    3. Clears the is_wip flag

    Args:
        project_file: Path to the project file.
        changespec_name: NAME of the ChangeSpec to update.

    Returns:
        True if successful (or no WIP mentors to update), False on error.
    """
    from mentor_config import get_all_mentor_profiles

    from ace.scheduler.mentor_checks import profile_matches_any_commit

    try:
        changespecs = parse_project_file(project_file)
        for cs in changespecs:
            if cs.name == changespec_name:
                if not cs.mentors:
                    return True  # No mentors, nothing to do

                # Find WIP entries and sort by entry_id
                wip_entries = [e for e in cs.mentors if e.is_wip]
                if not wip_entries:
                    return True  # No WIP entries, nothing to do

                # Sort by entry_id and get the last one
                wip_entries.sort(key=lambda e: parse_commit_entry_id(e.entry_id))
                last_wip_entry = wip_entries[-1]

                # Collect profiles with running mentors (must be preserved)
                profiles_with_running_mentors: set[str] = set()
                if last_wip_entry.status_lines:
                    for sl in last_wip_entry.status_lines:
                        profiles_with_running_mentors.add(sl.profile_name)

                # Use ALL commits for matching (not just this entry_id)
                matching_commits = list(cs.commits) if cs.commits else []

                # Rebuild profiles list from scratch (unless no commits exist)
                if matching_commits:
                    new_profiles: list[str] = []
                    for profile in get_all_mentor_profiles():
                        profile_name = profile.profile_name
                        # Include if: matches any commit OR has running mentors
                        if profile_matches_any_commit(profile, matching_commits):
                            new_profiles.append(profile_name)
                        elif profile_name in profiles_with_running_mentors:
                            new_profiles.append(profile_name)

                    last_wip_entry.profiles = new_profiles
                # If no commits, keep existing profiles (edge case / backward compat)

                # Clear the WIP flag
                last_wip_entry.is_wip = False

                # Write back
                return update_changespec_mentors_field(
                    project_file, changespec_name, cs.mentors
                )
        return True  # ChangeSpec not found, nothing to do
    except Exception:
        return False
