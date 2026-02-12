"""Handler for the mail tool action."""

import os
import sys
from typing import TYPE_CHECKING

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from commit_utils import run_bb_hg_clean

from ..changespec import ChangeSpec
from ..mail_ops import handle_mail as mail_ops_handle_mail
from ..operations import update_to_changespec

if TYPE_CHECKING:
    from ..tui._workflow_context import WorkflowContext


def handle_mail(
    self: "WorkflowContext",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
) -> tuple[list[ChangeSpec], int]:
    """Handle 'M' (mail) action.

    Claims a workspace in the 100-199 range, checks out the CL,
    runs mail prep and execution, then releases the workspace.

    Args:
        self: The WorkflowContext instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    from running_field import (
        claim_workspace,
        get_first_available_axe_workspace,
        get_workspace_directory_for_num,
        release_workspace,
    )

    from ..changespec import get_base_status

    base_status = get_base_status(changespec.status)
    if base_status != "Drafted":
        self.console.print(
            "[yellow]mail option only available for Drafted ChangeSpecs[/yellow]"
        )
        return changespecs, current_idx

    # Claim a workspace in the 100-199 range
    workspace_num = get_first_available_axe_workspace(changespec.file_path)

    if not claim_workspace(
        changespec.file_path, workspace_num, "mail", os.getpid(), changespec.name
    ):
        self.console.print("[red]Failed to claim workspace[/red]")
        return changespecs, current_idx

    try:
        # Get workspace directory
        workspace_dir, workspace_suffix = get_workspace_directory_for_num(
            workspace_num, changespec.project_basename
        )

        if workspace_suffix:
            self.console.print(f"[cyan]Using workspace: {workspace_suffix}[/cyan]")

        # Clean workspace before switching branches
        clean_success, clean_error = run_bb_hg_clean(
            workspace_dir, f"{changespec.name}-mail"
        )
        if not clean_success:
            self.console.print(
                f"[yellow]Warning: bb_hg_clean failed: {clean_error}[/yellow]"
            )

        # Update to the changespec branch (NAME field) to ensure we're on the correct branch
        success, error_msg = update_to_changespec(
            changespec,
            self.console,
            revision=changespec.name,
            workspace_dir=workspace_dir,
        )
        if not success:
            self.console.print(f"[red]Error: {error_msg}[/red]")
            return changespecs, current_idx

        # Run the mail handler with the claimed workspace directory
        success = mail_ops_handle_mail(changespec, workspace_dir, self.console)

        if success:
            # Reload changespecs to reflect the status update
            changespecs, current_idx = self._reload_and_reposition(
                changespecs, changespec
            )

    finally:
        # Always release the workspace
        release_workspace(changespec.file_path, workspace_num, "mail", changespec.name)

    return changespecs, current_idx
