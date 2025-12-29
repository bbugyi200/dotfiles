"""ChangeSpec parsing utilities."""

from pathlib import Path

from .models import (
    ACKNOWLEDGED_SUFFIX_MESSAGES,
    ERROR_SUFFIX_MESSAGES,
    READY_TO_MAIL_SUFFIX,
    ChangeSpec,
    CommentEntry,
    HistoryEntry,
    HookEntry,
    HookStatusLine,
    get_base_status,
    has_ready_to_mail_suffix,
    is_acknowledged_suffix,
    is_error_suffix,
    parse_history_entry_id,
)
from .parser import parse_project_file
from .validation import (
    all_hooks_passed_for_entries,
    get_current_and_proposal_entry_ids,
    has_any_error_suffix,
    is_parent_ready_for_mail,
)

__all__ = [
    # Dataclasses
    "ChangeSpec",
    "HistoryEntry",
    "HookEntry",
    "HookStatusLine",
    "CommentEntry",
    # Constants
    "ERROR_SUFFIX_MESSAGES",
    "ACKNOWLEDGED_SUFFIX_MESSAGES",
    "READY_TO_MAIL_SUFFIX",
    # Functions
    "is_error_suffix",
    "is_acknowledged_suffix",
    "has_ready_to_mail_suffix",
    "get_base_status",
    "parse_history_entry_id",
    "has_any_error_suffix",
    "is_parent_ready_for_mail",
    "get_current_and_proposal_entry_ids",
    "all_hooks_passed_for_entries",
    "parse_project_file",
    "find_all_changespecs",
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
