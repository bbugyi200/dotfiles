"""Handler for the show-diff tool action."""

import subprocess
import tempfile
from typing import TYPE_CHECKING

from vcs_provider import get_vcs_provider

from ..changespec import ChangeSpec

if TYPE_CHECKING:
    from ..tui._workflow_context import WorkflowContext


def handle_show_diff(self: "WorkflowContext", changespec: ChangeSpec) -> None:
    """Handle 'd' (show diff) action.

    Gets the diff via the VCS provider, writes it to a temp file, then
    displays through bat (if available) for syntax highlighting, with
    fallback to less.

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
        provider = get_vcs_provider(target_dir)
        success, diff_text = provider.diff_revision(changespec.name, target_dir)
        if not success:
            self.console.print(f"[red]Error showing diff: {diff_text}[/red]")
            return

        if not diff_text:
            self.console.print("[yellow]No diff output.[/yellow]")
            return

        # Write diff to a temp file and display with bat/less
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".diff", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(diff_text)
            tmp_path = tmp.name

        try:
            if shutil.which("bat"):
                cmd = (
                    f"bat --color=always --style=numbers --language=diff"
                    f" {tmp_path} | less -R"
                )
            else:
                cmd = f"less -R {tmp_path}"

            subprocess.run(cmd, shell=True, check=False)
        finally:
            import os

            os.unlink(tmp_path)
    except Exception as e:
        self.console.print(f"[red]Error showing diff: {str(e)}[/red]")
