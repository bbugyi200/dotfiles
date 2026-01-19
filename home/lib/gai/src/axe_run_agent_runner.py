#!/usr/bin/env python3
"""Background run agent runner for gai ace TUI.

This script is launched by the ace TUI to run custom agents in the background.
It handles workspace cleanup and releases the workspace upon completion.
"""

import json
import os
import signal
import sys
import time

# Add parent directory to path for imports (use abspath to handle relative __file__)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ace.hooks import format_duration  # noqa: E402
from change_actions import execute_change_action, prompt_for_change_action  # noqa: E402
from chat_history import save_chat_history  # noqa: E402
from gemini_wrapper import invoke_agent  # noqa: E402
from rich.console import Console  # noqa: E402
from running_field import release_workspace  # noqa: E402
from shared_utils import ensure_str_content  # noqa: E402

# Global flag to track if we received SIGTERM
_killed = False


def _sigterm_handler(_signum: int, _frame: object) -> None:
    """Handle SIGTERM by setting killed flag and exiting gracefully.

    Using sys.exit() instead of re-raising SIGTERM allows finally blocks
    to run, ensuring workspace cleanup happens before the process exits.
    """
    global _killed
    _killed = True
    print("\nReceived SIGTERM - agent was killed", file=sys.stderr)
    # Exit with conventional signal exit code (128 + signal number)
    # This allows cleanup code in finally blocks to run
    sys.exit(128 + signal.SIGTERM)


# Register SIGTERM handler
signal.signal(signal.SIGTERM, _sigterm_handler)


def _prepare_workspace(workspace_dir: str, cl_name: str, update_target: str) -> bool:
    """Clean and update workspace before running agent.

    Args:
        workspace_dir: The workspace directory.
        cl_name: Display name for the CL/project (used for backup diff name).
        update_target: What to checkout (CL name or "p4head").

    Returns:
        True if successful, False otherwise.
    """
    import subprocess

    from commit_utils import run_bb_hg_clean

    # Clean workspace (saves any existing changes to a diff file)
    print("Cleaning workspace...")
    success, error = run_bb_hg_clean(workspace_dir, f"{cl_name}-ace")
    if not success:
        print(f"bb_hg_clean failed: {error}", file=sys.stderr)
        return False

    # Update workspace to target
    print(f"Updating workspace to {update_target}...")
    try:
        result = subprocess.run(
            ["bb_hg_update", update_target],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip()
            print(f"bb_hg_update failed: {error_msg}", file=sys.stderr)
            return False
    except subprocess.TimeoutExpired:
        print("bb_hg_update timed out", file=sys.stderr)
        return False
    except Exception as e:
        print(f"bb_hg_update error: {e}", file=sys.stderr)
        return False

    print("Workspace ready")
    return True


def _create_new_changespec(
    console: Console,
    project_file: str,
    new_cl_name: str,
    parent_cl_name: str | None,
    saved_path: str,
    diff_path: str,
    bug: str | None = None,
    fixed_bug: str | None = None,
) -> str | None:
    """Create a new WIP ChangeSpec for the agent's changes.

    Follows the same workflow as gai commit:
    1. Generate description from chat history
    2. Create Mercurial commit
    3. Upload and get CL number
    4. Create ChangeSpec with CL URL and hooks

    Note: Assumes current directory is the workspace directory.

    Args:
        console: Rich Console for output.
        project_file: Path to the project file.
        new_cl_name: Name for the new ChangeSpec.
        parent_cl_name: Parent CL name (if any).
        saved_path: Path to the saved chat history file.
        diff_path: Path to the saved diff file.
        bug: Bug number for BUG: field (e.g., "12345").
        fixed_bug: Bug number for FIXED: field (mutually exclusive with bug).

    Returns:
        The suffixed CL name on success (e.g., "project_foo_bar__1"),
        None on failure.
    """
    import tempfile

    from commit_workflow.branch_info import get_cl_number, get_parent_branch_name
    from commit_workflow.changespec_operations import add_changespec_to_project_file
    from commit_workflow.cl_formatting import format_cl_description
    from shared_utils import run_shell_command
    from summarize_utils import get_file_summary
    from workflow_utils import get_initial_hooks_for_changespec

    # Extract project name from project_file path
    # Path format: ~/.gai/projects/<project>/<project>.gp
    project_name = os.path.basename(os.path.dirname(project_file))

    # Add project prefix if not already present
    full_cl_name = new_cl_name
    if not new_cl_name.startswith(f"{project_name}_"):
        full_cl_name = f"{project_name}_{new_cl_name}"

    # Validate CL name doesn't conflict with non-WIP/non-Reverted ChangeSpecs
    from commit_workflow.changespec_queries import get_conflicting_changespec

    conflict = get_conflicting_changespec(project_name, full_cl_name)
    if conflict:
        conflict_name, conflict_status = conflict
        console.print(
            f"[red]Cannot create CL '{new_cl_name}': conflicts with "
            f"'{conflict_name}' (status: {conflict_status})[/red]"
        )
        return None

    # Generate description using summarize agent
    print("Generating description from chat history...")
    description = get_file_summary(
        saved_path,
        usage="a concise description of what changes were made to the codebase",
        fallback="Changes made by agent",
    )
    print(f"Description: {description}")

    # Write description to temp file for hg commit
    fd, desc_file = tempfile.mkstemp(suffix=".txt", prefix="gai_ace_desc_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(description)

        # Format with [project] prefix for Mercurial commit message
        format_cl_description(desc_file, project_name, bug=bug, fixed_bug=fixed_bug)

        # Get parent branch name
        parent_branch = get_parent_branch_name()

        # Run hg addremove to stage new/deleted files
        print("Running hg addremove...")
        run_shell_command("hg addremove", capture_output=True)

        # Create the Mercurial commit
        print(f"Creating Mercurial commit with name: {full_cl_name}")
        commit_cmd = f'hg commit --name "{full_cl_name}" --logfile "{desc_file}"'
        commit_result = run_shell_command(commit_cmd, capture_output=True)
        if commit_result.returncode != 0:
            console.print(f"[red]Failed to create commit: {commit_result.stderr}[/red]")
            return None

        # Run hg fix
        print("Running hg fix...")
        fix_result = run_shell_command("hg fix", capture_output=True)
        if fix_result.returncode != 0:
            print(f"hg fix warning: {fix_result.stderr}")
            # Continue anyway

        # Run hg upload tree
        print("Running hg upload tree...")
        upload_result = run_shell_command("hg upload tree", capture_output=True)
        if upload_result.returncode != 0:
            print(f"hg upload tree warning: {upload_result.stderr}")
            # Continue anyway

        # Get CL number
        print("Retrieving CL number...")
        cl_number = get_cl_number()
        if not cl_number:
            console.print("[red]Failed to get CL number[/red]")
            return None
        cl_url = f"http://cl/{cl_number}"
        print(f"CL URL: {cl_url}")

        # Get initial hooks
        print("Gathering hooks for new ChangeSpec...")
        initial_hooks = get_initial_hooks_for_changespec(verbose=False)

        # Create the ChangeSpec with all required fields
        # Format bug as URL for ChangeSpec (use bug or fixed_bug, whichever is set)
        bug_url = f"http://b/{bug}" if bug else None
        fixed_bug_url = f"http://b/{fixed_bug}" if fixed_bug else None
        suffixed_name = add_changespec_to_project_file(
            project=project_name,
            cl_name=full_cl_name,
            description=description,  # Original, unformatted description
            parent=parent_branch or parent_cl_name,
            cl_url=cl_url,
            initial_hooks=initial_hooks,
            initial_commits=[(1, "[run] Initial Commit", saved_path, diff_path)],
            bug=bug_url or fixed_bug_url,
        )

        if suffixed_name:
            # Rename the CL to match the suffixed ChangeSpec name
            if suffixed_name != full_cl_name:
                rename_result = run_shell_command(
                    f'bb_hg_rename "{suffixed_name}"', capture_output=True
                )
                if rename_result.returncode != 0:
                    print(f"Warning: Failed to rename CL: {rename_result.stderr}")

            console.print(f"[green]Created new ChangeSpec: {suffixed_name}[/green]")
            return suffixed_name
        else:
            console.print(f"[red]Failed to create ChangeSpec: {full_cl_name}[/red]")
            return None

    finally:
        # Clean up temp file
        try:
            os.unlink(desc_file)
        except OSError:
            pass


def main() -> None:
    """Run agent workflow and release workspace on completion."""
    # Accept 16 args: cl_name, project_file, workspace_dir, output_path,
    # workspace_num, workflow_name, prompt_file, timestamp, new_cl_name,
    # parent_cl_name, update_target, project_name, cl_name_for_history, bug,
    # fixed_bug
    if len(sys.argv) != 16:
        print(
            f"Usage: {sys.argv[0]} <cl_name> <project_file> <workspace_dir> "
            "<output_path> <workspace_num> <workflow_name> <prompt_file> <timestamp> "
            "<new_cl_name> <parent_cl_name> <update_target> <project_name> "
            "<cl_name_for_history> <bug> <fixed_bug>",
            file=sys.stderr,
        )
        sys.exit(1)

    cl_name = sys.argv[1]
    project_file = sys.argv[2]
    workspace_dir = sys.argv[3]
    output_path = sys.argv[4]
    workspace_num = int(sys.argv[5])
    workflow_name = sys.argv[6]
    prompt_file = sys.argv[7]
    timestamp = sys.argv[8]

    # Optional parameters (empty string = not provided)
    new_cl_name_arg = sys.argv[9]
    parent_cl_name_arg = sys.argv[10]
    update_target = sys.argv[11]
    project_name_arg = sys.argv[12]
    cl_name_for_history = sys.argv[13]
    bug_arg = sys.argv[14]
    fixed_bug_arg = sys.argv[15]
    # Convert empty strings to None
    new_cl_name: str | None = new_cl_name_arg if new_cl_name_arg else None
    parent_cl_name: str | None = parent_cl_name_arg if parent_cl_name_arg else None
    bug: str | None = bug_arg if bug_arg else None
    fixed_bug: str | None = fixed_bug_arg if fixed_bug_arg else None

    # Read prompt from temp file
    try:
        with open(prompt_file, encoding="utf-8") as f:
            prompt = f.read()
    except Exception as e:
        print(f"Error reading prompt file: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Clean up temp prompt file
        try:
            os.unlink(prompt_file)
        except OSError:
            pass

    # Save prompt to history for future gai run sessions
    from prompt_history import add_or_update_prompt

    add_or_update_prompt(
        prompt,
        project_name=project_name_arg or None,
        branch_or_workspace=cl_name_for_history or None,
    )

    start_time = time.time()
    success = False
    duration = "0s"

    print("Starting agent run")
    print(f"CL: {cl_name}")
    print(f"Workspace: {workspace_dir}")
    print(f"Workflow: {workflow_name}")
    print()
    print("=== Prompt ===")
    print(prompt)
    print("==============")
    print()

    console = Console()

    # Prepare workspace before running agent
    if update_target:
        print("=== Preparing Workspace ===")
        if not _prepare_workspace(workspace_dir, cl_name, update_target):
            print("Failed to prepare workspace", file=sys.stderr)
            sys.exit(1)
        print("===========================")
        print()

    try:
        try:
            # Change to workspace directory
            os.chdir(workspace_dir)

            # Get project name from project_file path
            # Path format: ~/.gai/projects/<project>/<project>.gp
            project_name = os.path.basename(os.path.dirname(project_file))

            # Create artifacts directory using shared timestamp
            # Convert timestamp from YYmmdd_HHMMSS to YYYYmmddHHMMSS format
            artifacts_timestamp = f"20{timestamp[:6]}{timestamp[7:]}"
            artifacts_dir = os.path.expanduser(
                f"~/.gai/projects/{project_name}/artifacts/ace-run/{artifacts_timestamp}"
            )
            os.makedirs(artifacts_dir, exist_ok=True)

            # Run the agent
            ai_result = invoke_agent(
                prompt,
                agent_type="ace-run",
                model_size="big",
                artifacts_dir=artifacts_dir,
                timestamp=timestamp,
            )

            # Prepare and save chat history
            response_content = ensure_str_content(ai_result.content)
            saved_path = save_chat_history(
                prompt=prompt,
                response=response_content,
                workflow="ace-run",
                timestamp=timestamp,
            )
            print(f"\nChat history saved to: {saved_path}")

            # Check for local changes
            from gai_utils import run_shell_command

            changes_result = run_shell_command(
                "branch_local_changes", capture_output=True
            )
            has_changes = bool(changes_result.stdout.strip())

            if has_changes and new_cl_name:
                # Save diff BEFORE creating the new ChangeSpec (before hg commit)
                from commit_utils import save_diff

                diff_path = save_diff(
                    cl_name, target_dir=workspace_dir, timestamp=timestamp
                )

                if diff_path is None:
                    console.print("[red]Failed to save diff for new ChangeSpec[/red]")
                    raise RuntimeError(
                        "save_diff returned None despite has_changes=True"
                    )

                # Create a new ChangeSpec for the changes
                print(f"\nCreating new ChangeSpec: {new_cl_name}")
                full_new_cl_name = _create_new_changespec(
                    console=console,
                    project_file=project_file,
                    new_cl_name=new_cl_name,
                    parent_cl_name=parent_cl_name,
                    saved_path=saved_path,
                    diff_path=diff_path,
                    bug=bug,
                    fixed_bug=fixed_bug,
                )

                # If ChangeSpec creation failed, use unsuffixed name for done marker
                if not full_new_cl_name:
                    from pathlib import Path

                    project_name = Path(project_file).parent.name
                    full_new_cl_name = f"{project_name}_{new_cl_name}"

                # Write done marker for NEW CL outcome
                new_cl_done_marker = {
                    "cl_name": cl_name,
                    "project_file": project_file,
                    "timestamp": timestamp,
                    "artifacts_timestamp": artifacts_timestamp,
                    "response_path": saved_path,
                    "outcome": "new_cl",
                    "diff_path": diff_path,
                    "new_cl_name": full_new_cl_name,
                    "workspace_num": workspace_num,
                }
                done_path = os.path.join(artifacts_dir, "done.json")
                with open(done_path, "w", encoding="utf-8") as f:
                    json.dump(new_cl_done_marker, f, indent=2)
                print(f"Done marker written to: {done_path}")
            elif has_changes:
                # No new_cl_name provided - create a proposal for existing CL
                # Generate summary from chat history for better proposal note
                from summarize_utils import get_file_summary

                workflow_summary = get_file_summary(
                    target_file=saved_path,
                    usage="a COMMITS entry header describing what changes were made",
                    fallback="",
                )

                prompt_result = prompt_for_change_action(
                    console,
                    workspace_dir,
                    workflow_name="ace-run",
                    workflow_summary=workflow_summary,
                    chat_path=saved_path,
                    shared_timestamp=timestamp,
                    project_file=project_file,
                    auto_reject=True,  # Non-interactive - auto-reject changes
                    cl_name=cl_name,  # Pass known CL name for proposal creation
                )

                proposal_id: str | None = None
                if prompt_result is not None:
                    action, action_args = prompt_result
                    if action == "reject":
                        proposal_id = action_args
                        print(f"\nChanges auto-rejected (proposal: {proposal_id})")
                    else:
                        # Execute non-reject actions (shouldn't happen with auto_reject)
                        from shared_utils import generate_workflow_tag

                        workflow_tag = generate_workflow_tag()
                        execute_change_action(
                            action=action,
                            action_args=action_args,
                            console=console,
                            target_dir=workspace_dir,
                            workflow_tag=workflow_tag,
                            workflow_name="ace-run",
                            chat_path=saved_path,
                            shared_timestamp=timestamp,
                        )

                # Build diff path (same format as save_diff uses)
                from gai_utils import make_safe_filename

                safe_name = make_safe_filename(cl_name)
                diff_path = f"~/.gai/diffs/{safe_name}-{timestamp}.diff"

                # Write done marker for NEW PROPOSAL outcome
                proposal_done_marker: dict[str, str | int | None] = {
                    "cl_name": cl_name,
                    "project_file": project_file,
                    "timestamp": timestamp,
                    "artifacts_timestamp": artifacts_timestamp,
                    "response_path": saved_path,
                    "outcome": "new_proposal",
                    "diff_path": diff_path,
                    "proposal_id": proposal_id,
                    "workspace_num": workspace_num,
                }
                done_path = os.path.join(artifacts_dir, "done.json")
                with open(done_path, "w", encoding="utf-8") as f:
                    json.dump(proposal_done_marker, f, indent=2)
                print(f"Done marker written to: {done_path}")
            else:
                print("\nNo changes detected")
                # Write done marker for NO CHANGES outcome
                no_changes_done_marker = {
                    "cl_name": cl_name,
                    "project_file": project_file,
                    "timestamp": timestamp,
                    "artifacts_timestamp": artifacts_timestamp,
                    "response_path": saved_path,
                    "outcome": "no_changes",
                    "workspace_num": workspace_num,
                }
                done_path = os.path.join(artifacts_dir, "done.json")
                with open(done_path, "w", encoding="utf-8") as f:
                    json.dump(no_changes_done_marker, f, indent=2)
                print(f"Done marker written to: {done_path}")

            success = True

        except Exception as e:
            print(f"Error running agent: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()
            success = False

        end_time = time.time()
        elapsed_seconds = int(end_time - start_time)
        duration = format_duration(elapsed_seconds)

        print()
        print(f"Agent completed with status: {'SUCCESS' if success else 'FAILED'}")
        print(f"Duration: {duration}")

    finally:
        # Always release workspace, even if killed via SIGTERM
        # This prevents zombie workspace claims in the RUNNING field
        try:
            release_workspace(project_file, workspace_num, workflow_name, cl_name)
            print("Workspace released")
        except Exception as e:
            print(f"Error releasing workspace: {e}", file=sys.stderr)

        # Write completion marker
        try:
            with open(output_path, "a") as f:
                f.write("\n=== AGENT_RUN_COMPLETE ===\n")
                f.write(f"Status: {'SUCCESS' if success else 'FAILED'}\n")
                f.write(f"Duration: {duration}\n")
        except Exception as e:
            print(f"Error writing completion marker: {e}", file=sys.stderr)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
