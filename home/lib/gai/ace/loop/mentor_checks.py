"""Mentor workflow checking logic for the loop command."""

import fnmatch
import os
import re
from collections.abc import Callable

from mentor_config import MentorProfileConfig, get_all_mentor_profiles

from ..changespec import ChangeSpec

# Type alias for logging callback
LogCallback = Callable[[str, str | None], None]


def _get_max_mentored_entry_id(changespec: ChangeSpec) -> int:
    """Get the highest entry_id that has MENTORS entries.

    All entries <= this ID are considered "already mentored".

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        The highest mentored entry ID, or -1 if no MENTORS entries exist.
    """
    if not changespec.mentors:
        return -1

    max_id = -1
    for me in changespec.mentors:
        if me.entry_id.isdigit():
            max_id = max(max_id, int(me.entry_id))
    return max_id


def _get_unmentored_commit_ids(changespec: ChangeSpec) -> list[str]:
    """Get non-proposal commit IDs that need mentor checking.

    Returns all commit IDs > max_mentored_entry_id. If MENTORS has
    an entry for (N), all entries <= N are considered "already mentored".

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        List of commit entry IDs that need mentor profile matching.
    """
    if not changespec.commits:
        return []

    max_mentored = _get_max_mentored_entry_id(changespec)

    return [
        entry.display_number
        for entry in changespec.commits
        if entry.display_number.isdigit() and int(entry.display_number) > max_mentored
    ]


def _get_commit_entry_diff_path(changespec: ChangeSpec, entry_id: str) -> str | None:
    """Get the diff file path for a commit entry.

    Args:
        changespec: The ChangeSpec to check.
        entry_id: The commit entry ID.

    Returns:
        The diff file path, or None if not found.
    """
    if not changespec.commits:
        return None

    for entry in changespec.commits:
        if entry.display_number == entry_id:
            return entry.diff

    return None


def _get_commit_entry_note(changespec: ChangeSpec, entry_id: str) -> str | None:
    """Get the note (amend note) for a commit entry.

    Args:
        changespec: The ChangeSpec to check.
        entry_id: The commit entry ID.

    Returns:
        The note text, or None if not found.
    """
    if not changespec.commits:
        return None

    for entry in changespec.commits:
        if entry.display_number == entry_id:
            return entry.note

    return None


def _extract_changed_files_from_diff(diff_content: str) -> list[str]:
    """Extract file paths from diff content (hg/git unified diff format).

    Args:
        diff_content: The diff content as a string.

    Returns:
        List of file paths that were changed.
    """
    files = []
    for line in diff_content.split("\n"):
        # Match "diff --git a/path/to/file b/path/to/file"
        git_match = re.match(r"^diff --git a/(\S+) b/(\S+)", line)
        if git_match:
            files.append(git_match.group(2))
            continue

        # Match "diff -r ... path/to/file" (hg format)
        hg_match = re.match(r"^diff -r [a-f0-9]+ (\S+)", line)
        if hg_match:
            files.append(hg_match.group(1))
            continue

    return files


def _profile_matches_commit(
    profile: MentorProfileConfig,
    diff_path: str | None,
    amend_note: str | None,
) -> bool:
    """Check if a profile's criteria match the commit.

    Args:
        profile: The mentor profile configuration.
        diff_path: Path to the diff file, or None.
        amend_note: The commit's note text, or None.

    Returns:
        True if any of the profile's criteria match.
    """
    # Check file_globs
    if profile.file_globs and diff_path:
        full_path = os.path.expanduser(diff_path)
        if os.path.exists(full_path):
            with open(full_path, encoding="utf-8", errors="ignore") as f:
                diff_content = f.read()
            changed_files = _extract_changed_files_from_diff(diff_content)
            for pattern in profile.file_globs:
                for filepath in changed_files:
                    if fnmatch.fnmatch(filepath, pattern):
                        return True

    # Check diff_regexes
    if profile.diff_regexes and diff_path:
        full_path = os.path.expanduser(diff_path)
        if os.path.exists(full_path):
            with open(full_path, encoding="utf-8", errors="ignore") as f:
                diff_content = f.read()
            for regex in profile.diff_regexes:
                if re.search(regex, diff_content):
                    return True

    # Check amend_note_regexes
    if profile.amend_note_regexes and amend_note:
        for regex in profile.amend_note_regexes:
            if re.search(regex, amend_note):
                return True

    return False


def _get_mentor_profiles_to_run(
    changespec: ChangeSpec,
) -> list[tuple[str, MentorProfileConfig]]:
    """Get list of (entry_id, profile) tuples that should run mentors.

    Returns profiles that match commit criteria for entries that haven't
    been mentored yet. If MENTORS has an entry for (N), all entries <= N
    are considered "already mentored" and won't be checked.

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        List of (entry_id, profile) tuples to run.
    """
    result: list[tuple[str, MentorProfileConfig]] = []

    # Get commit IDs that need mentor checking (> any existing MENTORS entry)
    entry_ids_to_check = _get_unmentored_commit_ids(changespec)

    for entry_id in entry_ids_to_check:
        diff_path = _get_commit_entry_diff_path(changespec, entry_id)
        amend_note = _get_commit_entry_note(changespec, entry_id)

        for profile in get_all_mentor_profiles():
            if _profile_matches_commit(profile, diff_path, amend_note):
                result.append((entry_id, profile))

    return result


def _count_running_mentors(changespec: ChangeSpec) -> int:
    """Count the number of currently running mentors in a ChangeSpec.

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        Number of mentors with RUNNING status.
    """
    count = 0
    if changespec.mentors:
        for entry in changespec.mentors:
            if entry.status_lines:
                for sl in entry.status_lines:
                    if sl.status == "RUNNING":
                        count += 1
    return count


def _count_running_mentors_global() -> int:
    """Count all running mentors across all ChangeSpecs globally.

    Returns:
        Total number of mentors with RUNNING status.
    """
    from ..changespec import find_all_changespecs

    total = 0
    for changespec in find_all_changespecs():
        total += _count_running_mentors(changespec)
    return total


def _check_mentor_completion(
    changespec: ChangeSpec,
    log: LogCallback,
    zombie_timeout_seconds: int,
) -> list[str]:
    """Check completion status of running mentors.

    Phase 1 of mentor checking: check if any RUNNING mentors have completed.

    Args:
        changespec: The ChangeSpec to check.
        log: Logging callback.
        zombie_timeout_seconds: Timeout for detecting zombie processes.

    Returns:
        List of update messages.
    """
    updates: list[str] = []

    if not changespec.mentors:
        return updates

    # For now, mentor completion is handled by the background runner
    # which updates the status directly when it finishes.
    # This function could be extended to detect zombie mentors.

    return updates


def check_mentors(
    changespec: ChangeSpec,
    log: LogCallback,
    zombie_timeout_seconds: int,
    max_concurrent_mentors: int,
    agents_started_this_cycle: int = 0,
) -> tuple[list[str], int]:
    """Check and run mentors for a ChangeSpec.

    Phase 1: Check completion status of RUNNING mentors
    Phase 2: Start mentors for matching profiles

    Args:
        changespec: The ChangeSpec to check.
        log: Logging callback.
        zombie_timeout_seconds: Zombie detection timeout in seconds.
        max_concurrent_mentors: Maximum concurrent mentors globally.
        agents_started_this_cycle: Number of agents already started this cycle (across
            all ChangeSpecs). Added to the global count to avoid exceeding the limit.

    Returns:
        Tuple of (update messages, number of mentors started by this call).
    """
    updates: list[str] = []
    mentors_started = 0

    # Don't check mentors for terminal statuses
    if changespec.status in ("Reverted", "Submitted"):
        return updates, mentors_started

    # Phase 1: Check completion of running mentors
    completion_updates = _check_mentor_completion(
        changespec, log, zombie_timeout_seconds
    )
    updates.extend(completion_updates)

    # Phase 2: Start mentors for matching profiles
    profiles_to_run = _get_mentor_profiles_to_run(changespec)

    if not profiles_to_run:
        return updates, mentors_started

    # Check global concurrency limit
    # Include agents started this cycle (across all ChangeSpecs) that aren't
    # yet written to disk
    from ..changespec import count_running_agents_global

    current_running_agents = count_running_agents_global()
    current_running_mentors = _count_running_mentors_global()
    total_running = (
        current_running_agents + current_running_mentors + agents_started_this_cycle
    )

    if total_running >= max_concurrent_mentors:
        log(
            f"Skipping mentor start: {total_running} agents+mentors running "
            f"(limit: {max_concurrent_mentors})",
            "dim",
        )
        return updates, mentors_started

    available_slots = max_concurrent_mentors - total_running

    # Import start_mentor here to avoid circular imports
    from .mentor_runner import start_mentors_for_profile

    for entry_id, profile in profiles_to_run:
        if mentors_started >= available_slots:
            log(
                f"Reached agent limit ({max_concurrent_mentors}), "
                f"deferring remaining mentors",
                "dim",
            )
            break

        # Start all mentors for this profile
        started_count, start_updates = start_mentors_for_profile(
            changespec,
            entry_id,
            profile,
            log,
            available_slots - mentors_started,
        )
        updates.extend(start_updates)
        mentors_started += started_count

    return updates, mentors_started
