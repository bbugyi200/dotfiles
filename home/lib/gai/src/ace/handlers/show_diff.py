"""Handler for the show-diff tool action."""

import subprocess
from typing import TYPE_CHECKING

from ..changespec import ChangeSpec

if TYPE_CHECKING:
    from ..tui._workflow_context import WorkflowContext


def handle_show_diff(self: "WorkflowContext", changespec: ChangeSpec) -> None:
    """Handle 'd' (show diff) action.

    Runs 'hg diff <name>' in the primary workspace, piped through bat (if
    available) for syntax highlighting, with fallback to less.

    Args:
        self: The WorkflowContext instance
        changespec: Current ChangeSpec
    """
    import shutil

    from running_field import get_workspace_directory as get_primary_workspace

    # Get the primary workspace directory (workspace #1)
    try:
        target_dir = get_primary_workspace(changespec.project_basename, 1)
    except RuntimeError as e:
        self.console.print(f"[red]Error getting workspace: {e}[/red]")
        return

    try:
        # Build command: hg diff piped through bat (if available) or less
        if shutil.which("bat"):
            cmd = (
                f"hg diff -c {changespec.name} "
                "| bat --color=always --style=numbers --language=diff | less -R"
            )
        else:
            cmd = f"hg diff -c {changespec.name} | less -R"

        subprocess.run(cmd, shell=True, cwd=target_dir, check=False)
    except Exception as e:
        self.console.print(f"[red]Error showing diff: {str(e)}[/red]")
