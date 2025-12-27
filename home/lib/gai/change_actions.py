"""Change action handling for workflow changes (prompt, accept, commit, purge)."""

import os
import subprocess
import tempfile
from typing import Literal

from rich.console import Console
from running_field import get_claimed_workspaces, release_workspace

# Type for change action prompt results
ChangeAction = Literal["accept", "commit", "reject", "purge"]


def _run_shell_command(
    cmd: str, capture_output: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run a shell command and return the result."""
    return subprocess.run(
        cmd,
        shell=True,
        capture_output=capture_output,
        text=True,
    )


def _delete_proposal_entry(
    project_file: str, cl_name: str, base_num: int, letter: str
) -> bool:
    """Delete a proposal entry from a ChangeSpec's HISTORY.

    Args:
        project_file: Path to the project file.
        cl_name: The CL name.
        base_num: The base number of the proposal (e.g., 2 for "2a").
        letter: The letter of the proposal (e.g., "a" for "2a").

    Returns:
        True if successful, False otherwise.
    """
    try:
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return False

    # Find the ChangeSpec and its history section
    in_target_changespec = False
    new_lines: list[str] = []
    skip_until_next_entry = False
    proposal_pattern = f"({base_num}{letter})"

    i = 0
    while i < len(lines):
        line = lines[i]

        if line.startswith("NAME: "):
            current_name = line[6:].strip()
            in_target_changespec = current_name == cl_name
            skip_until_next_entry = False
            new_lines.append(line)
            i += 1
            continue

        if in_target_changespec:
            stripped = line.strip()
            # Check if this is the proposal entry to delete
            if stripped.startswith(proposal_pattern):
                # Skip this entry and its metadata lines
                skip_until_next_entry = True
                i += 1
                continue
            # Check if we're still in metadata for skipped entry
            if skip_until_next_entry:
                if stripped.startswith("| "):
                    # Skip metadata line
                    i += 1
                    continue
                else:
                    # No longer in metadata
                    skip_until_next_entry = False

        new_lines.append(line)
        i += 1

    # Write back atomically
    project_dir = os.path.dirname(project_file)
    fd, temp_path = tempfile.mkstemp(dir=project_dir, prefix=".tmp_", suffix=".gp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        os.replace(temp_path, project_file)
        return True
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        return False


def prompt_for_change_action(
    console: Console,
    target_dir: str,
    propose_mode: bool = True,  # Kept for API compatibility
    workflow_name: str | None = None,
    chat_path: str | None = None,
    shared_timestamp: str | None = None,
    project_file: str | None = None,
) -> tuple[ChangeAction, str | None] | None:
    """
    Prompt user for action on uncommitted changes.

    This function:
    1. Checks for uncommitted changes using `branch_local_changes`
    2. If no changes, returns None
    3. Creates a proposal from the changes (if on a branch)
    4. Prompts user with options: a/c/n/x (Enter = view diff)
    5. Returns the selected action and proposal ID (for accept/purge)

    Args:
        console: Rich Console for output
        target_dir: Directory to check for changes
        propose_mode: Deprecated parameter (always uses propose mode)
        workflow_name: Name of the workflow for the proposal note
        chat_path: Optional path to chat file for HISTORY entry
        shared_timestamp: Optional shared timestamp for synced chat/diff files
        project_file: Optional path to project file. If not provided,
            will try to infer from workspace_name command.

    Returns:
        ("accept", "<proposal_id>") - User chose 'a' to accept proposal
        ("commit", "<args>") - User chose 'c <args>'
        ("reject", "<proposal_id>") - User chose 'n' (proposal stays)
        ("purge", "<proposal_id>") - User chose 'x' (delete proposal)
        None - No changes detected
    """
    # Import here to avoid circular imports
    from history_utils import (
        add_proposed_history_entry,
        clean_workspace,
        save_diff,
    )

    # Check for uncommitted changes using branch_local_changes
    result = _run_shell_command("branch_local_changes", capture_output=True)
    if not result.stdout.strip():
        return None  # No changes

    # Check if there's a branch to propose to
    branch_result = _run_shell_command("branch_name", capture_output=True)
    branch_name = branch_result.stdout.strip() if branch_result.returncode == 0 else ""

    proposal_id: str | None = None

    # If we have a branch, create a proposal first
    if branch_name:
        # Get project file - prefer explicit path over workspace inference
        resolved_project_file: str | None = None
        if project_file:
            resolved_project_file = os.path.expanduser(project_file)
        else:
            workspace_result = _run_shell_command("workspace_name", capture_output=True)
            project = (
                workspace_result.stdout.strip()
                if workspace_result.returncode == 0
                else None
            )
            if project:
                resolved_project_file = os.path.expanduser(
                    f"~/.gai/projects/{project}/{project}.gp"
                )

        if resolved_project_file and os.path.isfile(resolved_project_file):
            # Build proposal note
            if workflow_name:
                propose_note = f"[{workflow_name}]"
            else:
                propose_note = "[agent]"

            # Save the diff
            diff_path = save_diff(
                branch_name, target_dir=target_dir, timestamp=shared_timestamp
            )

            if diff_path:
                # Create proposed HISTORY entry
                success, entry_id = add_proposed_history_entry(
                    project_file=resolved_project_file,
                    cl_name=branch_name,
                    note=propose_note,
                    diff_path=diff_path,
                    chat_path=chat_path,
                )
                if success and entry_id:
                    proposal_id = entry_id
                    console.print(
                        f"[cyan]Created proposal ({proposal_id}): {propose_note}[/cyan]"
                    )
                    # Clean workspace after creating proposal
                    clean_workspace(target_dir)

    # Build prompt based on whether we created a proposal
    if proposal_id:
        prompt_text = (
            f"\n[cyan]a (accept {proposal_id}) | "
            "c <name> (commit) | n (skip) | x (purge):[/cyan] "
        )
    elif branch_name:
        # Fallback if proposal creation failed
        prompt_text = (
            f"\n[cyan]a <msg> (propose to {branch_name}) | "
            "c <name> (commit) | n (skip) | x (purge):[/cyan] "
        )
    else:
        prompt_text = "\n[cyan]c <name> (commit) | n (skip) | x (purge):[/cyan] "

    # Prompt loop
    while True:
        console.print(prompt_text, end="")
        user_input = input().strip()

        if user_input == "":
            # Show diff (either from workspace or from saved diff)
            console.print()
            if proposal_id:
                # Workspace was cleaned after creating proposal
                # Just inform user that proposal diff is saved
                try:
                    result = subprocess.run(
                        ["hg", "diff", "--color=always"],
                        cwd=target_dir,
                        capture_output=True,
                        text=True,
                    )
                    if result.stdout.strip():
                        print(result.stdout)
                    else:
                        console.print(
                            "[dim]Workspace is clean. Proposal diff saved.[/dim]"
                        )
                except (subprocess.CalledProcessError, FileNotFoundError):
                    pass
            else:
                try:
                    subprocess.run(
                        ["hg", "diff", "--color=always"],
                        cwd=target_dir,
                        check=True,
                    )
                except (subprocess.CalledProcessError, FileNotFoundError):
                    pass
            continue  # Prompt again

        if user_input == "a":
            if proposal_id:
                # Accept the proposal (no extra message)
                return ("accept", proposal_id)
            elif not branch_name:
                console.print(
                    "[red]Error: 'a' is not available - no branch found[/red]"
                )
                continue
            else:
                # Fallback to old behavior if proposal wasn't created
                console.print(
                    "[red]Error: 'a' requires a message (e.g., 'a fix typo')[/red]"
                )
                continue
        elif user_input.startswith("a "):
            if proposal_id:
                # Accept with optional message: "a <msg>" -> append msg to note
                extra_msg = user_input[2:].strip()
                return (
                    "accept",
                    f"{proposal_id}:{extra_msg}" if extra_msg else proposal_id,
                )
            elif not branch_name:
                console.print(
                    "[red]Error: 'a' is not available - no branch found[/red]"
                )
                continue
            else:
                # Proposal creation failed earlier, can't accept
                console.print(
                    "[red]Error: No proposal was created. Cannot accept.[/red]"
                )
                continue
        elif user_input.startswith("c "):
            # Extract args after "c "
            commit_args = user_input[2:].strip()
            if commit_args:
                return ("commit", commit_args)
            else:
                console.print(
                    "[red]Error: 'c' requires a CL name (e.g., 'c my_feature')[/red]"
                )
                continue
        elif user_input == "c":
            console.print(
                "[red]Error: 'c' requires a CL name (e.g., 'c my_feature')[/red]"
            )
            continue
        elif user_input == "n":
            return ("reject", proposal_id)
        elif user_input == "x":
            return ("purge", proposal_id)
        else:
            console.print(f"[red]Invalid option: {user_input}[/red]")


def execute_change_action(
    action: ChangeAction,
    action_args: str | None,
    console: Console,
    target_dir: str,
    workflow_tag: str | None = None,
    workflow_name: str | None = None,
    chat_path: str | None = None,
    shared_timestamp: str | None = None,
    project_file: str | None = None,
) -> bool:
    """
    Execute the action selected by prompt_for_change_action.

    Args:
        action: The action to execute ("accept", "amend", "commit", "reject",
            "purge", "propose")
        action_args: Arguments for the action (proposal_id for "accept"/"purge",
            message for "amend"/"propose", CL name for "commit")
        console: Rich Console for output
        target_dir: Directory where changes are located
        workflow_tag: Optional workflow tag for amend commit message
        workflow_name: Optional workflow name for amend commit message
        chat_path: Optional path to chat file for HISTORY entry
        shared_timestamp: Optional shared timestamp for synced chat/diff files
        project_file: Optional path to project file. If not provided,
            will try to infer from workspace_name command.

    Returns:
        True if action completed successfully, False otherwise
    """
    if action == "accept":
        # Accept a proposal: apply diff, amend, renumber
        if not action_args:
            console.print("[red]Error: accept requires a proposal ID[/red]")
            return False

        # Parse action_args: "proposal_id" or "proposal_id:extra_msg"
        if ":" in action_args:
            proposal_id, extra_msg = action_args.split(":", 1)
        else:
            proposal_id = action_args
            extra_msg = ""

        # Import accept workflow functions
        from accept_workflow import (
            _find_proposal_entry,
            _parse_proposal_id,
            _renumber_history_entries,
        )
        from history_utils import apply_diff_to_workspace
        from workflow_utils import get_changespec_from_file

        # Parse proposal ID
        parsed = _parse_proposal_id(proposal_id)
        if not parsed:
            console.print(f"[red]Invalid proposal ID: {proposal_id}[/red]")
            return False
        base_num, letter = parsed

        # Get project file - prefer explicit path over workspace inference
        if project_file:
            resolved_project_file = os.path.expanduser(project_file)
        else:
            workspace_result = _run_shell_command("workspace_name", capture_output=True)
            project = (
                workspace_result.stdout.strip()
                if workspace_result.returncode == 0
                else None
            )
            if not project:
                console.print("[red]Failed to get project name[/red]")
                return False
            resolved_project_file = os.path.expanduser(
                f"~/.gai/projects/{project}/{project}.gp"
            )

        branch_result = _run_shell_command("branch_name", capture_output=True)
        cl_name = branch_result.stdout.strip() if branch_result.returncode == 0 else ""
        if not cl_name:
            console.print("[red]Failed to get branch name[/red]")
            return False

        if not os.path.isfile(resolved_project_file):
            console.print(f"[red]Project file not found: {resolved_project_file}[/red]")
            return False

        # Get the proposal entry
        changespec = get_changespec_from_file(resolved_project_file, cl_name)
        if not changespec:
            console.print(f"[red]ChangeSpec not found: {cl_name}[/red]")
            return False

        entry = _find_proposal_entry(changespec.history, base_num, letter)
        if not entry:
            console.print(f"[red]Proposal ({proposal_id}) not found[/red]")
            return False
        if not entry.diff:
            console.print(f"[red]Proposal ({proposal_id}) has no diff[/red]")
            return False

        # Apply the diff
        console.print(f"[cyan]Applying proposal ({proposal_id})...[/cyan]")
        success, error_msg = apply_diff_to_workspace(target_dir, entry.diff)
        if not success:
            console.print(f"[red]Failed to apply diff: {error_msg}[/red]")
            return False

        # Build amend note (append extra_msg if provided)
        amend_note = f"{entry.note} - {extra_msg}" if extra_msg else entry.note

        # Run bb_hg_amend with the amend note
        console.print("[cyan]Amending commit...[/cyan]")
        try:
            result = subprocess.run(
                ["bb_hg_amend", amend_note],
                capture_output=True,
                text=True,
                cwd=target_dir,
            )
            if result.returncode != 0:
                console.print(f"[red]bb_hg_amend failed: {result.stderr}[/red]")
                return False
        except FileNotFoundError:
            console.print("[red]bb_hg_amend command not found[/red]")
            return False

        # Renumber history entries (pass extra_msg to append to HISTORY note)
        console.print("[cyan]Updating HISTORY...[/cyan]")
        if _renumber_history_entries(
            resolved_project_file, cl_name, [(base_num, letter)], extra_msg or None
        ):
            console.print("[green]HISTORY updated successfully.[/green]")
        else:
            console.print("[yellow]Warning: Failed to update HISTORY.[/yellow]")

        # Release any loop(hooks)-* workspaces for the old proposal ID
        # The proposal is now renumbered to a regular entry, so the old
        # loop(hooks)-<proposal_id> workspace claim is stale
        old_workflow = f"loop(hooks)-{proposal_id}"
        for claim in get_claimed_workspaces(resolved_project_file):
            if claim.cl_name == cl_name and claim.workflow == old_workflow:
                release_workspace(
                    resolved_project_file, claim.workspace_num, old_workflow, cl_name
                )
                console.print(f"[dim]Released workspace #{claim.workspace_num}[/dim]")

        console.print(f"[green]Proposal ({proposal_id}) accepted![/green]")
        return True

    elif action == "commit":
        if not action_args:
            console.print("[red]Error: commit requires a CL name[/red]")
            return False

        # Run gai commit with the provided args
        console.print(f"[cyan]Running gai commit {action_args}...[/cyan]")
        try:
            cmd = ["gai", "commit", action_args]
            if chat_path:
                cmd.extend(["--chat", chat_path])
            if shared_timestamp:
                cmd.extend(["--timestamp", shared_timestamp])
            subprocess.run(
                cmd,
                cwd=target_dir,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            console.print(f"[red]gai commit failed (exit code {e.returncode})[/red]")
            return False

        console.print("[green]Commit created successfully![/green]")
        return True

    elif action == "reject":
        console.print("[yellow]Changes rejected. Returning to view.[/yellow]")
        return False

    elif action == "purge":
        # Delete the proposal entry from HISTORY
        if not action_args:
            console.print("[yellow]No proposal to purge.[/yellow]")
            return False

        proposal_id = action_args

        # Import needed functions
        from accept_workflow import (
            _find_proposal_entry,
            _parse_proposal_id,
        )
        from workflow_utils import get_changespec_from_file

        # Parse proposal ID
        parsed = _parse_proposal_id(proposal_id)
        if not parsed:
            console.print(f"[red]Invalid proposal ID: {proposal_id}[/red]")
            return False
        base_num, letter = parsed

        # Get project file - prefer explicit path over workspace inference
        if project_file:
            resolved_project_file = os.path.expanduser(project_file)
        else:
            workspace_result = _run_shell_command("workspace_name", capture_output=True)
            project = (
                workspace_result.stdout.strip()
                if workspace_result.returncode == 0
                else None
            )
            if not project:
                console.print("[red]Failed to get project name[/red]")
                return False
            resolved_project_file = os.path.expanduser(
                f"~/.gai/projects/{project}/{project}.gp"
            )

        branch_result = _run_shell_command("branch_name", capture_output=True)
        cl_name = branch_result.stdout.strip() if branch_result.returncode == 0 else ""
        if not cl_name:
            console.print("[red]Failed to get branch name[/red]")
            return False

        if not os.path.isfile(resolved_project_file):
            console.print(f"[red]Project file not found: {resolved_project_file}[/red]")
            return False

        # Get the proposal entry to find the diff path
        changespec = get_changespec_from_file(resolved_project_file, cl_name)
        if changespec:
            entry = _find_proposal_entry(changespec.history, base_num, letter)
            if entry and entry.diff:
                # Delete the diff file
                try:
                    if os.path.isfile(entry.diff):
                        os.remove(entry.diff)
                        console.print(f"[dim]Deleted diff: {entry.diff}[/dim]")
                except OSError:
                    pass  # Ignore errors deleting diff

        # Delete the proposal entry from the project file
        console.print(f"[cyan]Deleting proposal ({proposal_id})...[/cyan]")
        success = _delete_proposal_entry(
            resolved_project_file, cl_name, base_num, letter
        )
        if success:
            console.print(f"[green]Proposal ({proposal_id}) deleted.[/green]")
        else:
            console.print("[yellow]Warning: Could not delete proposal entry.[/yellow]")

        return False  # Return False to indicate workflow didn't "succeed"

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        return False
