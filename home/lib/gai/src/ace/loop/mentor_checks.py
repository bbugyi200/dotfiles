"""Mentor workflow checking logic for the loop command."""

import fnmatch
import os
import re
from collections.abc import Callable

from mentor_config import MentorProfileConfig, get_all_mentor_profiles

from ..changespec import ChangeSpec
from ..display_helpers import is_entry_ref_suffix

# Type alias for logging callback
LogCallback = Callable[[str, str | None], None]


def _get_started_mentors_for_entry(
    changespec: ChangeSpec, entry_id: str
) -> set[tuple[str, str]]:
    """Get set of (profile_name, mentor_name) tuples that have been started.

    Args:
        changespec: The ChangeSpec to check.
        entry_id: The commit entry ID.

    Returns:
        Set of (profile_name, mentor_name) tuples that have status lines.
    """
    started: set[tuple[str, str]] = set()
    if not changespec.mentors:
        return started

    for me in changespec.mentors:
        if me.entry_id == entry_id and me.status_lines:
            for sl in me.status_lines:
                started.add((sl.profile_name, sl.mentor_name))

    return started


def _all_non_skip_hooks_ready(changespec: ChangeSpec, entry_id: str) -> bool:
    """Check if all non-skip hooks are ready for mentors to run.

    Only checks hook status for the given entry_id (the latest commit).
    Status from older commits is irrelevant.

    A hook is "ready" for the given entry if it has either:
    - PASSED status for this entry, or
    - FAILED status for this entry with an entry_ref suffix (proposal attached)

    Hooks with skip_fix_hook (! prefix) are completely ignored.

    Args:
        changespec: The ChangeSpec to check.
        entry_id: The LATEST commit entry ID to check hooks for.

    Returns:
        True if all non-skip hooks are ready for this entry, False otherwise.
    """
    if not changespec.hooks:
        return True  # No hooks = ready

    for hook in changespec.hooks:
        # Skip hooks with ! prefix - they don't affect mentor eligibility
        if hook.skip_fix_hook:
            continue

        # Get status line for this entry
        status_line = hook.get_status_line_for_commit_entry(entry_id)

        if status_line is None:
            # Hook hasn't run for this entry yet
            return False

        if status_line.status == "RUNNING":
            # Hook still running
            return False

        if status_line.status == "FAILED":
            # Failed hooks must have a proposal attached (entry_ref suffix)
            if not is_entry_ref_suffix(status_line.suffix):
                return False
            # Has entry_ref suffix - ready

        # PASSED, KILLED, DEAD, or FAILED with entry_ref - considered ready

    return True


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

    Only checks the LATEST non-proposal commit entry.
    Returns profiles that have unstarted mentors for that entry.

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        List of (entry_id, profile) tuples to run.
    """
    result: list[tuple[str, MentorProfileConfig]] = []

    if not changespec.commits:
        return result

    # Get the latest non-proposal commit entry
    latest_entry_id = None
    for entry in reversed(changespec.commits):
        if entry.display_number.isdigit():
            latest_entry_id = entry.display_number
            break

    if latest_entry_id is None:
        return result

    # Check if all non-skip hooks are ready before running mentors
    if not _all_non_skip_hooks_ready(changespec, latest_entry_id):
        return result

    diff_path = _get_commit_entry_diff_path(changespec, latest_entry_id)
    amend_note = _get_commit_entry_note(changespec, latest_entry_id)

    # Get mentors already started for this entry
    started_mentors = _get_started_mentors_for_entry(changespec, latest_entry_id)

    for profile in get_all_mentor_profiles():
        if _profile_matches_commit(profile, diff_path, amend_note):
            # Check if any mentors in this profile are unstarted
            has_unstarted = False
            for mentor_name in profile.mentors:
                if (profile.name, mentor_name) not in started_mentors:
                    has_unstarted = True
                    break

            if has_unstarted:
                result.append((latest_entry_id, profile))

    return result


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
    max_runners: int,
    runners_started_this_cycle: int = 0,
) -> tuple[list[str], int]:
    """Check and run mentors for a ChangeSpec.

    Phase 1: Check completion status of RUNNING mentors
    Phase 2: Start mentors for matching profiles

    Args:
        changespec: The ChangeSpec to check.
        log: Logging callback.
        zombie_timeout_seconds: Zombie detection timeout in seconds.
        max_runners: Maximum concurrent runners (hooks, agents, mentors) globally.
        runners_started_this_cycle: Number of runners already started this cycle (across
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
    # Include runners started this cycle (across all ChangeSpecs) that aren't
    # yet written to disk
    from ..changespec import count_all_runners_global

    current_running = count_all_runners_global() + runners_started_this_cycle

    if current_running >= max_runners:
        log(
            f"Skipping mentor start: {current_running} runners running "
            f"(limit: {max_runners})",
            "dim",
        )
        return updates, mentors_started

    available_slots = max_runners - current_running

    # Import start_mentor here to avoid circular imports
    from .mentor_runner import start_mentors_for_profile

    for entry_id, profile in profiles_to_run:
        if mentors_started >= available_slots:
            log(
                f"Reached runner limit ({max_runners}), deferring remaining mentors",
                "dim",
            )
            break

        # Get mentors already started for this entry
        started_mentors = _get_started_mentors_for_entry(changespec, entry_id)

        # Start unstarted mentors for this profile
        started_count, start_updates = start_mentors_for_profile(
            changespec,
            entry_id,
            profile,
            log,
            available_slots - mentors_started,
            started_mentors,
        )
        updates.extend(start_updates)
        mentors_started += started_count

    return updates, mentors_started
