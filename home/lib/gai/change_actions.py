"""Change action handling for workflow changes (prompt, accept, commit, purge)."""

import os
import subprocess
import tempfile
from typing import Literal

from ace.comments.operations import (
    mark_comment_agents_as_killed,
    update_changespec_comments_field,
)
from ace.hooks.core import (
    kill_running_agent_processes,
    kill_running_hook_processes,
    mark_hook_agents_as_killed,
    mark_hooks_as_killed,
)
from ace.hooks.execution import update_changespec_hooks_field
from rich.console import Console
from running_field import get_claimed_workspaces, release_workspace

# Type for change action prompt results
ChangeAction = Literal["accept", "commit", "reject", "purge"]


def _run_shell_command(
    cmd: str, capture_output: bool = True
) -> subprocess.CompletedProcess:
    """Run a shell command and return the result.

    Note: This is a local copy to avoid circular imports with shared_utils.
    """
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
    workflow_name: str | None = None,
    chat_path: str | None = None,
    shared_timestamp: str | None = None,
    project_file: str | None = None,
    accept_message: str | None = None,
    commit_name: str | None = None,
    commit_message: str | None = None,
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
        workflow_name: Name of the workflow for the proposal note
        chat_path: Optional path to chat file for COMMITS entry
        shared_timestamp: Optional shared timestamp for synced chat/diff files
        project_file: Optional path to project file. If not provided,
            will try to infer from workspace_name command.
        accept_message: If provided, auto-select 'a' (accept) with this message.
            Skips the interactive prompt.
        commit_name: If provided along with commit_message, auto-select 'c' (commit).
            Skips the interactive prompt.
        commit_message: The commit message to use with commit_name.

    Returns:
        ("accept", "<proposal_id>") - User chose 'a' to accept proposal
        ("commit", "<args>") - User chose 'c <args>' (tab-delimited name and message)
        ("reject", "<proposal_id>") - User chose 'n' (proposal stays)
        ("purge", "<proposal_id>") - User chose 'x' (delete proposal)
        None - No changes detected
    """
    # Import here to avoid circular imports
    from commit_utils import (
        add_proposed_commit_entry,
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
    saved_diff_path: str | None = None  # Track the saved diff path for 'd' option

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
                saved_diff_path = diff_path  # Store for 'd' option
                # Create proposed COMMITS entry
                success, entry_id = add_proposed_commit_entry(
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

    # Handle auto-selection if accept_message or commit_message was provided
    if accept_message is not None:
        if proposal_id:
            console.print(
                f"[cyan]Auto-selecting 'a' (accept) with message: {accept_message}[/cyan]"
            )
            return ("accept", f"{proposal_id}:{accept_message}")
        else:
            console.print(
                "[red]Error: Cannot auto-accept - no proposal was created[/red]"
            )
            return None

    if commit_name is not None and commit_message is not None:
        console.print(
            f"[cyan]Auto-selecting 'c' (commit) with name: {commit_name}[/cyan]"
        )
        # Encode both name and message with tab delimiter
        return ("commit", f"{commit_name}\t{commit_message}")

    # Build prompt based on whether we created a proposal
    if proposal_id:
        prompt_text = (
            f"\n[cyan]a (accept {proposal_id}) | "
            "c <name> (commit) | d (diff) | n (skip) | x (purge):[/cyan] "
        )
    elif branch_name:
        # Fallback if proposal creation failed
        prompt_text = (
            f"\n[cyan]a <msg> (propose to {branch_name}) | "
            "c <name> (commit) | d (diff) | n (skip) | x (purge):[/cyan] "
        )
    else:
        prompt_text = (
            "\n[cyan]c <name> (commit) | d (diff) | n (skip) | x (purge):[/cyan] "
        )

    # Prompt loop
    while True:
        console.print(prompt_text, end="")
        user_input = input().strip()

        if user_input == "d":
            # Show the saved diff file
            console.print()
            # Expand ~ to home directory for file operations
            expanded_diff_path = (
                os.path.expanduser(saved_diff_path) if saved_diff_path else None
            )
            if expanded_diff_path and os.path.isfile(expanded_diff_path):
                # Try bat first for syntax highlighting, fall back to cat | less
                try:
                    subprocess.run(
                        [
                            "bat",
                            "--color=always",
                            "--paging=always",
                            expanded_diff_path,
                        ],
                        check=True,
                    )
                except FileNotFoundError:
                    # bat not available, use cat piped to less
                    try:
                        cat_proc = subprocess.Popen(
                            ["cat", expanded_diff_path],
                            stdout=subprocess.PIPE,
                        )
                        subprocess.run(["less", "-R"], stdin=cat_proc.stdout)
                        cat_proc.wait()
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        # Last resort: just print the file
                        with open(expanded_diff_path, encoding="utf-8") as f:
                            print(f.read())
                except subprocess.CalledProcessError:
                    pass
            else:
                console.print("[dim]No diff file available.[/dim]")
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
            # Extract args after "c ": first word is CL name, rest is optional message
            commit_args = user_input[2:].strip()
            if commit_args:
                parts = commit_args.split(None, 1)  # Split on first whitespace
                cl_name = parts[0]
                if len(parts) > 1:
                    # Has message: encode with tab delimiter
                    return ("commit", f"{cl_name}\t{parts[1]}")
                else:
                    return ("commit", cl_name)
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
        chat_path: Optional path to chat file for COMMITS entry
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
            find_proposal_entry,
            parse_proposal_id,
            renumber_commit_entries,
        )
        from commit_utils import apply_diff_to_workspace
        from workflow_utils import get_changespec_from_file

        # Parse proposal ID
        parsed = parse_proposal_id(proposal_id)
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

        # Kill any running hook processes before accepting
        killed_processes = kill_running_hook_processes(changespec)
        if killed_processes:
            console.print(
                f"[cyan]Killed {len(killed_processes)} running hook process(es)[/cyan]"
            )
            if changespec.hooks:
                updated_hooks = mark_hooks_as_killed(
                    changespec.hooks,
                    killed_processes,
                    "Killed stale hook after accepting proposal.",
                )
                update_changespec_hooks_field(
                    resolved_project_file, cl_name, updated_hooks
                )

        # Kill any running agent processes before accepting
        killed_hook_agents, killed_comment_agents = kill_running_agent_processes(
            changespec
        )
        total_killed_agents = len(killed_hook_agents) + len(killed_comment_agents)
        if total_killed_agents:
            console.print(
                f"[cyan]Killed {total_killed_agents} running agent process(es)[/cyan]"
            )
            if killed_hook_agents and changespec.hooks:
                updated_hooks = mark_hook_agents_as_killed(
                    changespec.hooks, killed_hook_agents
                )
                update_changespec_hooks_field(
                    resolved_project_file, cl_name, updated_hooks
                )
            if killed_comment_agents and changespec.comments:
                updated_comments = mark_comment_agents_as_killed(
                    changespec.comments, killed_comment_agents
                )
                update_changespec_comments_field(
                    resolved_project_file, cl_name, updated_comments
                )

        entry = find_proposal_entry(changespec.commits, base_num, letter)
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
        console.print("[cyan]Updating COMMITS...[/cyan]")
        if renumber_commit_entries(
            resolved_project_file,
            cl_name,
            [(base_num, letter)],
            [extra_msg] if extra_msg else None,
        ):
            console.print("[green]HISTORY updated successfully.[/green]")
        else:
            console.print("[yellow]Warning: Failed to update COMMITS.[/yellow]")

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

        # Parse action_args: either "cl_name" or "cl_name\tcommit_message"
        if "\t" in action_args:
            cl_name_arg, commit_msg = action_args.split("\t", 1)
        else:
            cl_name_arg = action_args
            commit_msg = None

        # Run gai commit with the provided args
        console.print(f"[cyan]Running gai commit {cl_name_arg}...[/cyan]")
        try:
            cmd = ["gai", "commit", cl_name_arg]
            if commit_msg:
                cmd.extend(["-m", commit_msg])
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
            find_proposal_entry,
            parse_proposal_id,
        )
        from workflow_utils import get_changespec_from_file

        # Parse proposal ID
        parsed = parse_proposal_id(proposal_id)
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
            entry = find_proposal_entry(changespec.commits, base_num, letter)
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
