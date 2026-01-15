"""Orphaned workspace claim cleanup utilities for the axe scheduler."""

from collections.abc import Callable

from running_field import (
    get_claimed_workspaces,
    release_workspace,
)

from ..changespec import ChangeSpec
from ..hooks.processes import is_process_running


def cleanup_orphaned_workspace_claims(
    all_changespecs: list[ChangeSpec],
    log_fn: Callable[[str, str | None], None] | None = None,
) -> int:
    """Release workspace claims for reverted CLs with dead PIDs.

    This catches orphaned workspace claims that weren't cleaned up during revert,
    such as when a mentor claims a workspace but hasn't registered in MENTORS yet.

    Args:
        all_changespecs: All ChangeSpecs in the project
        log_fn: Optional logging function (message, style)

    Returns:
        Number of orphaned workspace claims released
    """
    # Build lookup of reverted CL names
    reverted_cls = {cs.name for cs in all_changespecs if cs.status == "Reverted"}
    if not reverted_cls:
        return 0

    # Get project file from first changespec
    if not all_changespecs:
        return 0
    project_file = all_changespecs[0].file_path

    claims = get_claimed_workspaces(project_file)
    released_count = 0

    for claim in claims:
        # Skip claims without cl_name or not for reverted CLs
        if not claim.cl_name or claim.cl_name not in reverted_cls:
            continue

        # Skip if process is still running (or if pid is not set)
        if claim.pid is not None and is_process_running(claim.pid):
            continue

        # Release the orphaned workspace claim
        release_workspace(
            project_file,
            claim.workspace_num,
            claim.workflow,
            claim.cl_name,
        )
        released_count += 1

        if log_fn:
            log_fn(
                f"Released orphaned workspace #{claim.workspace_num} "
                f"({claim.workflow}) for reverted CL {claim.cl_name}",
                "cyan",
            )

    return released_count
