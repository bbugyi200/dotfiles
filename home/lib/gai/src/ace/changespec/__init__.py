"""ChangeSpec parsing utilities."""

from pathlib import Path
from typing import Any

from .locking import (
    LockTimeoutError,
    changespec_lock,
    write_changespec_atomic,
)
from .models import (
    ERROR_SUFFIX_MESSAGES,
    READY_TO_MAIL_SUFFIX,
    ChangeSpec,
    CommentEntry,
    CommitEntry,
    HookEntry,
    HookStatusLine,
    MentorEntry,
    MentorStatusLine,
    extract_pid_from_agent_suffix,
    get_base_status,
    has_ready_to_mail_suffix,
    is_error_suffix,
    is_plain_suffix,
    is_running_agent_suffix,
    is_running_process_suffix,
    parse_commit_entry_id,
)
from .parser import parse_project_file
from .project_spec import (
    ProjectSpec,
    WorkspaceClaim,
    parse_project_spec,
    read_and_update_project_spec,
    serialize_project_spec,
    write_project_spec_atomic,
)
from .raw_text import get_raw_changespec_text
from .structured_updates import (
    add_changespec_commit_entry,
    add_running_claim,
    remove_running_claim,
    update_changespec_cl,
    update_changespec_comments,
    update_changespec_description,
    update_changespec_hooks,
    update_changespec_mentors,
    update_changespec_parent,
    update_changespec_status,
    update_commit_entry_suffix,
    update_parent_references,
)
from .validation import (
    all_hooks_passed_for_entries,
    count_all_runners_global,
    count_running_agents_global,
    count_running_hooks_global,
    get_current_and_proposal_entry_ids,
    has_any_error_suffix,
    has_any_running_agent,
    has_any_running_process,
    has_any_status_suffix,
    is_parent_ready_for_mail,
)

__all__ = [
    # Dataclasses
    "ChangeSpec",
    "CommitEntry",
    "HookEntry",
    "HookStatusLine",
    "CommentEntry",
    "MentorEntry",
    "MentorStatusLine",
    "ProjectSpec",
    "WorkspaceClaim",
    "parse_project_spec",
    "read_and_update_project_spec",
    "serialize_project_spec",
    "write_project_spec_atomic",
    # Constants
    "ERROR_SUFFIX_MESSAGES",
    "READY_TO_MAIL_SUFFIX",
    # Locking
    "LockTimeoutError",
    "changespec_lock",
    "write_changespec_atomic",
    # Functions
    "extract_pid_from_agent_suffix",
    "is_error_suffix",
    "is_plain_suffix",
    "is_running_agent_suffix",
    "is_running_process_suffix",
    "has_ready_to_mail_suffix",
    "get_base_status",
    "parse_commit_entry_id",
    "count_all_runners_global",
    "count_running_agents_global",
    "count_running_hooks_global",
    "has_any_error_suffix",
    "has_any_running_agent",
    "has_any_running_process",
    "has_any_status_suffix",
    "is_parent_ready_for_mail",
    "get_current_and_proposal_entry_ids",
    "all_hooks_passed_for_entries",
    "parse_project_file",
    "get_raw_changespec_text",
    "find_all_changespecs",
    "get_eligible_parents_in_project",
    "get_entry_id",
    # Structured update functions
    "add_changespec_commit_entry",
    "add_running_claim",
    "remove_running_claim",
    "update_changespec_cl",
    "update_changespec_comments",
    "update_changespec_description",
    "update_changespec_hooks",
    "update_changespec_mentors",
    "update_changespec_parent",
    "update_changespec_status",
    "update_commit_entry_suffix",
    "update_parent_references",
]


def find_all_changespecs() -> list[ChangeSpec]:
    """Find all ChangeSpecs in all project files.

    Returns:
        List of all ChangeSpec objects from ~/.gai/projects/<project>/<project>.gp files
    """
    projects_dir = Path.home() / ".gai" / "projects"

    if not projects_dir.exists():
        return []

    all_changespecs: list[ChangeSpec] = []

    # Iterate through project directories
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue

        # Look for <project>.gp file inside the project directory
        project_name = project_dir.name
        gp_file = project_dir / f"{project_name}.gp"

        if gp_file.exists():
            changespecs = parse_project_file(str(gp_file))
            all_changespecs.extend(changespecs)

    return all_changespecs


# Eligible statuses for rebase parent selection
_ELIGIBLE_REBASE_STATUSES = ("WIP", "Drafted", "Mailed")


def get_eligible_parents_in_project(
    project_file: str, exclude_name: str
) -> list[tuple[str, str]]:
    """Get all ChangeSpecs in the same project file eligible to be parents for rebase.

    Args:
        project_file: Path to the project file
        exclude_name: Name to exclude (the CL being rebased)

    Returns:
        List of (name, status) tuples for ChangeSpecs with status WIP/Drafted/Mailed
    """
    changespecs = parse_project_file(project_file)
    eligible: list[tuple[str, str]] = []

    for cs in changespecs:
        # Skip the CL being rebased
        if cs.name == exclude_name:
            continue

        # Check if status is eligible (use base status to handle suffixes)
        base_status = get_base_status(cs.status)
        if base_status in _ELIGIBLE_REBASE_STATUSES:
            eligible.append((cs.name, base_status))

    return eligible


def get_entry_id(entry: dict[str, Any]) -> str:
    """Get the entry ID string (e.g., '1', '2a') from an entry dict.

    Args:
        entry: Dict with 'number' and optional 'letter' keys.

    Returns:
        Entry ID string like '1' or '2a'.
    """
    num = entry["number"]
    letter = entry.get("letter") or ""
    return f"{num}{letter}"
