"""Handler for the reword tool action."""

import os
import re
import subprocess
import sys
import tempfile
from typing import TYPE_CHECKING

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from commit_utils import run_bb_hg_clean
from commit_workflow.editor_utils import get_editor
from vcs_provider import get_vcs_provider

from ..changespec import ChangeSpec

if TYPE_CHECKING:
    from rich.console import Console

    from ..tui._workflow_context import WorkflowContext


def _sync_description_after_reword(
    workspace_dir: str, changespec: ChangeSpec, console: "Console"
) -> None:
    """Sync the ChangeSpec DESCRIPTION field after a successful reword.

    Runs ``cl_desc -s`` to get the clean description from the commit message
    and writes it back to the ``.gp`` file.  Errors are non-fatal (warnings
    only) since the reword itself already succeeded.

    Args:
        workspace_dir: Path to the workspace directory.
        changespec: The ChangeSpec whose description should be updated.
        console: Rich console for output.
    """
    from status_state_machine import update_changespec_description_atomic

    provider = get_vcs_provider(workspace_dir)
    success, desc_output = provider.get_description("", workspace_dir, short=True)
    if not success:
        console.print(
            f"[yellow]Warning: could not read updated description: {desc_output}[/yellow]"
        )
        return

    new_description = desc_output.strip() if desc_output else ""
    if not new_description:
        console.print(
            "[yellow]Warning: cl_desc -s returned empty output, "
            "skipping DESCRIPTION sync[/yellow]"
        )
        return

    success = update_changespec_description_atomic(
        changespec.file_path, changespec.name, new_description
    )
    if success:
        console.print("[green]Synced DESCRIPTION to project file[/green]")
    else:
        console.print(
            "[yellow]Warning: failed to sync DESCRIPTION to project file[/yellow]"
        )


def _fetch_cl_description(
    project_basename: str, changespec_name: str, console: "Console"
) -> str | None:
    """Fetch the CL description from the primary workspace without claiming it.

    Gets the primary workspace (#1) and runs ``cl_desc -r <name>`` to retrieve
    the current commit description.

    Args:
        project_basename: The project basename for workspace lookup.
        changespec_name: The changespec name (revision) to fetch.
        console: Rich console for output.

    Returns:
        The description string, or None on failure.
    """
    from running_field import get_workspace_directory as get_primary_workspace

    try:
        target_dir = get_primary_workspace(project_basename, 1)
    except RuntimeError as e:
        console.print(f"[red]Error getting workspace: {e}[/red]")
        return None

    provider = get_vcs_provider(target_dir)
    success, description = provider.get_description(changespec_name, target_dir)
    if not success:
        console.print(f"[red]{description}[/red]")
        return None
    return description


def _add_prettier_ignore_before_tags(description: str) -> str:
    """Insert ``<!-- prettier-ignore -->`` before the contiguous CL tag block.

    The tag block is the contiguous run of ``KEY=value`` / ``Key: value``
    lines at the very end of *description* (blank trailing lines are
    skipped first).  If no tag block is found the description is returned
    unchanged.
    """
    lines = description.split("\n")
    tag_pattern = re.compile(r"^[A-Z][A-Za-z_\s-]*[=:]")

    # Skip trailing blank lines
    last_non_blank = len(lines) - 1
    while last_non_blank >= 0 and lines[last_non_blank].strip() == "":
        last_non_blank -= 1

    # Scan upward to find contiguous tag block
    tags_start_idx = len(lines)
    for idx in range(last_non_blank, -1, -1):
        if tag_pattern.match(lines[idx].strip()):
            tags_start_idx = idx
        else:
            break

    if tags_start_idx >= len(lines):
        return description

    # Insert prettier-ignore comment before the tag block
    before = lines[:tags_start_idx]
    after = lines[tags_start_idx:]
    return "\n".join(before + ["<!-- prettier-ignore -->"] + after)


def _strip_prettier_ignore(content: str) -> str:
    """Remove any ``<!-- prettier-ignore -->`` lines from *content*."""
    lines = content.split("\n")
    filtered = [line for line in lines if line.strip() != "<!-- prettier-ignore -->"]
    return "\n".join(filtered)


def _open_editor_with_content(content: str, console: "Console") -> str | None:
    """Open the user's editor with initial content and return the edited result.

    Creates a temporary file, writes *content* to it, opens the editor, reads
    back the (possibly modified) content, and cleans up the temp file.

    Args:
        content: Initial text to populate the editor with.
        console: Rich console for output.

    Returns:
        The edited content string, or None if the editor failed.
    """
    fd, temp_path = tempfile.mkstemp(suffix=".md", prefix="gai_reword_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        console.print(f"[red]Failed to write temp file: {e}[/red]")
        os.close(fd)
        return None

    editor = get_editor()

    try:
        result = subprocess.run([editor, temp_path], check=False)
        if result.returncode != 0:
            console.print("[red]Editor exited with non-zero status.[/red]")
            return None

        with open(temp_path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        console.print(f"[red]Failed to open editor: {e}[/red]")
        return None
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def handle_add_tag(
    self: "WorkflowContext", changespec: ChangeSpec, tag_name: str, tag_value: str
) -> None:
    """Handle 'W' (add tag) action to append a tag to the CL description.

    Claims a workspace, checks out the CL, runs bb_hg_reword --add-tag,
    and syncs the description back to the project file.

    Args:
        self: The WorkflowContext instance
        changespec: Current ChangeSpec
        tag_name: The tag name (e.g. "BUG")
        tag_value: The tag value (e.g. "12345")
    """
    from running_field import (
        claim_workspace,
        get_first_available_axe_workspace,
        get_workspace_directory_for_num,
        release_workspace,
    )

    workspace_num = get_first_available_axe_workspace(changespec.file_path)

    if not claim_workspace(
        changespec.file_path, workspace_num, "add_tag", os.getpid(), changespec.name
    ):
        self.console.print("[red]Failed to claim workspace[/red]")
        return

    try:
        workspace_dir, workspace_suffix = get_workspace_directory_for_num(
            workspace_num, changespec.project_basename
        )

        if workspace_suffix:
            self.console.print(f"[cyan]Using workspace: {workspace_suffix}[/cyan]")

        # Clean workspace before switching branches
        clean_success, clean_error = run_bb_hg_clean(
            workspace_dir, f"{changespec.name}-add_tag"
        )
        if not clean_success:
            self.console.print(
                f"[yellow]Warning: bb_hg_clean failed: {clean_error}[/yellow]"
            )

        # Update to the changespec (checkout the CL)
        provider = get_vcs_provider(workspace_dir)
        self.console.print(f"[cyan]Checking out {changespec.name}...[/cyan]")
        checkout_ok, checkout_err = provider.checkout(changespec.name, workspace_dir)
        if not checkout_ok:
            self.console.print(f"[red]Error checking out CL: {checkout_err}[/red]")
            return

        # Run bb_hg_reword --add-tag
        self.console.print(f"[cyan]Adding tag {tag_name}={tag_value}...[/cyan]")
        tag_ok, tag_err = provider.reword_add_tag(tag_name, tag_value, workspace_dir)
        if tag_ok:
            self.console.print(
                f"[green]Tag {tag_name}={tag_value} added successfully[/green]"
            )
            _sync_description_after_reword(workspace_dir, changespec, self.console)
            from ..hooks import reset_dollar_hooks

            reset_dollar_hooks(
                changespec.file_path,
                changespec.name,
                log_fn=lambda msg: self.console.print(f"[cyan]{msg}[/cyan]"),
            )
        else:
            self.console.print(
                f"[yellow]bb_hg_reword --add-tag failed: {tag_err}[/yellow]"
            )

    finally:
        release_workspace(
            changespec.file_path, workspace_num, "add_tag", changespec.name
        )


def handle_reword(self: "WorkflowContext", changespec: ChangeSpec) -> None:
    """Handle 'w' (reword) action to change CL description.

    Fetches the current description and opens an editor immediately (fast),
    then only claims a workspace and runs bb_hg_reword if the description
    was actually changed.

    Args:
        self: The WorkflowContext instance
        changespec: Current ChangeSpec
    """
    from running_field import (
        claim_workspace,
        get_first_available_axe_workspace,
        get_workspace_directory_for_num,
        release_workspace,
    )

    from ..changespec import get_base_status

    # Validate status (strip any suffix like "READY TO MAIL")
    base_status = get_base_status(changespec.status)
    if base_status not in ("WIP", "Drafted", "Mailed"):
        self.console.print(
            "[yellow]reword option only available for WIP, Drafted, or Mailed ChangeSpecs[/yellow]"
        )
        return

    # Validate CL is set
    if changespec.cl is None:
        self.console.print("[yellow]reword option requires a CL to be set[/yellow]")
        return

    # --- Fast path: fetch description and open editor immediately ---
    original = _fetch_cl_description(
        changespec.project_basename, changespec.name, self.console
    )
    if original is None:
        return

    content_for_editor = _add_prettier_ignore_before_tags(original)
    edited = _open_editor_with_content(content_for_editor, self.console)
    if edited is None:
        self.console.print("[yellow]Reword cancelled.[/yellow]")
        return

    # Strip prettier-ignore immediately after editor returns
    edited = _strip_prettier_ignore(edited)

    # Compare (ignore trailing newline differences)
    if original.rstrip("\n") == edited.rstrip("\n"):
        self.console.print("[yellow]Description unchanged, nothing to do.[/yellow]")
        return

    # --- Slow path: description changed, claim workspace and apply ---
    workspace_num = get_first_available_axe_workspace(changespec.file_path)

    if not claim_workspace(
        changespec.file_path, workspace_num, "reword", os.getpid(), changespec.name
    ):
        self.console.print("[red]Failed to claim workspace[/red]")
        return

    try:
        workspace_dir, workspace_suffix = get_workspace_directory_for_num(
            workspace_num, changespec.project_basename
        )

        if workspace_suffix:
            self.console.print(f"[cyan]Using workspace: {workspace_suffix}[/cyan]")

        # Clean workspace before switching branches
        clean_success, clean_error = run_bb_hg_clean(
            workspace_dir, f"{changespec.name}-reword"
        )
        if not clean_success:
            self.console.print(
                f"[yellow]Warning: bb_hg_clean failed: {clean_error}[/yellow]"
            )

        # Update to the changespec (checkout the CL)
        provider = get_vcs_provider(workspace_dir)
        self.console.print(f"[cyan]Checking out {changespec.name}...[/cyan]")
        checkout_ok, checkout_err = provider.checkout(changespec.name, workspace_dir)
        if not checkout_ok:
            self.console.print(f"[red]Error checking out CL: {checkout_err}[/red]")
            return

        # Run reword with the edited description (non-interactive)
        self.console.print("[cyan]Rewording CL description...[/cyan]")
        escaped_desc = provider.prepare_description_for_reword(edited)
        reword_ok, reword_err = provider.reword(escaped_desc, workspace_dir)
        if reword_ok:
            self.console.print("[green]CL description updated successfully[/green]")
            _sync_description_after_reword(workspace_dir, changespec, self.console)
            from ..hooks import reset_dollar_hooks

            reset_dollar_hooks(
                changespec.file_path,
                changespec.name,
                log_fn=lambda msg: self.console.print(f"[cyan]{msg}[/cyan]"),
            )
        else:
            self.console.print(f"[yellow]bb_hg_reword failed: {reword_err}[/yellow]")

    finally:
        # Always release the workspace
        release_workspace(
            changespec.file_path, workspace_num, "reword", changespec.name
        )
