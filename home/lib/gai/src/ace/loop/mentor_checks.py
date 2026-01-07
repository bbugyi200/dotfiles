"""Mentor workflow checking logic for the loop command."""

import fnmatch
import os
import re
from collections.abc import Callable

from mentor_config import MentorProfileConfig, get_all_mentor_profiles

from ..changespec import ChangeSpec, CommitEntry
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
        return False  # Hooks not yet added, wait for them

    checked_any = False
    for hook in changespec.hooks:
        # Skip hooks with ! prefix - they don't affect mentor eligibility
        if hook.skip_fix_hook:
            continue

        checked_any = True

        # Get status line for this entry
        status_line = hook.get_status_line_for_commit_entry(entry_id)

        if status_line is None:
            # Hook hasn't run for this entry yet
            return False

        if status_line.status == "RUNNING":
            # Hook still running
            return False

        if status_line.status == "FAILED":
            # Failed hooks are ready if fix-hook is running OR has created a proposal
            if status_line.suffix_type == "running_agent":
                continue  # fix-hook is running, ready
            if not is_entry_ref_suffix(status_line.suffix):
                return False  # fix-hook hasn't started yet
            # Has entry_ref suffix - ready

        # PASSED, KILLED, DEAD, or FAILED with entry_ref - considered ready

    if not checked_any:
        return False  # All hooks were !-prefixed, wait for non-! hooks

    return True


def _get_commits_since_last_mentors(
    changespec: ChangeSpec,
) -> list[CommitEntry]:
    """Get all regular commits since the last MENTORS entry.

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        List of CommitEntry objects for commits after the last MENTORS entry.
    """
    # Find the highest numeric entry_id in mentors
    last_mentor_id: int | None = None
    if changespec.mentors:
        for me in changespec.mentors:
            if me.entry_id.isdigit():
                entry_num = int(me.entry_id)
                if last_mentor_id is None or entry_num > last_mentor_id:
                    last_mentor_id = entry_num

    # Get all regular commits after that ID
    result: list[CommitEntry] = []
    if changespec.commits:
        for entry in changespec.commits:
            # Skip proposals (entries with letters like "5a")
            if not entry.display_number.isdigit():
                continue
            entry_num = int(entry.display_number)
            # Include if no mentors yet, or at/after last mentor entry
            if last_mentor_id is None or entry_num >= last_mentor_id:
                result.append(entry)
    return result


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


def _profile_matches_any_commit(
    profile: MentorProfileConfig,
    commits: list[CommitEntry],
) -> bool:
    """Check if a profile matches ANY of the given commits.

    Args:
        profile: The mentor profile config.
        commits: List of commit entries to check.

    Returns:
        True if the profile matches any commit's diff/note.
    """
    for commit in commits:
        diff_path = commit.diff
        amend_note = commit.note
        if _profile_matches_commit(profile, diff_path, amend_note):
            return True
    return False


def _get_mentor_profiles_to_run(
    changespec: ChangeSpec,
) -> list[tuple[str, MentorProfileConfig]]:
    """Get list of (entry_id, profile) tuples that should run mentors.

    Checks ALL commits since the last MENTORS entry.
    Returns profiles that have unstarted mentors for the latest entry.

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

    # Get all commits since the last MENTORS entry
    commits_to_check = _get_commits_since_last_mentors(changespec)

    # Get mentors already started for this entry
    started_mentors = _get_started_mentors_for_entry(changespec, latest_entry_id)

    for profile in get_all_mentor_profiles():
        if _profile_matches_any_commit(profile, commits_to_check):
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
