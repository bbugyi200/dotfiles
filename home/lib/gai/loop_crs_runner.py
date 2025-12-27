#!/usr/bin/env python3
"""Standalone CRS workflow runner for gai loop background execution.

This script runs the CRS workflow in the background and writes completion
markers to the output file for the loop to detect when finished.

Usage:
    python3 loop_crs_runner.py <changespec_name> <project_file> <comments_file> \
        <reviewer_type> <workspace_dir> <output_file> <workspace_num> <workflow_name>

Output file will contain:
    - Workflow output/logs
    - Completion marker: ===WORKFLOW_COMPLETE=== PROPOSAL_ID: <id> EXIT_CODE: <code>
"""

import os
import sys
from pathlib import Path

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.dirname(__file__))

from chat_history import save_chat_history
from crs_workflow import CrsWorkflow
from history_utils import save_diff
from running_field import release_workspace
from work.changespec import parse_project_file
from work.comments import set_comment_suffix


def _shorten_path(path: str) -> str:
    """Shorten a file path by replacing home directory with ~."""
    return path.replace(str(Path.home()), "~")


def _add_proposed_history_entry(
    project_file: str,
    cl_name: str,
    note: str,
    diff_path: str | None = None,
    chat_path: str | None = None,
) -> tuple[bool, str | None]:
    """Add a proposed HISTORY entry to a ChangeSpec."""
    from history_utils import add_proposed_history_entry

    return add_proposed_history_entry(project_file, cl_name, note, diff_path, chat_path)


def main() -> int:
    """Run the CRS workflow and write completion marker."""
    if len(sys.argv) != 9:
        print(
            f"Usage: {sys.argv[0]} <changespec_name> <project_file> <comments_file> "
            "<reviewer_type> <workspace_dir> <output_file> <workspace_num> <workflow_name>"
        )
        return 1

    changespec_name = sys.argv[1]
    project_file = sys.argv[2]
    comments_file = sys.argv[3] if sys.argv[3] else None
    reviewer_type = sys.argv[4]
    workspace_dir = sys.argv[5]
    # output_file = sys.argv[6]  # Not used - output goes to stdout
    workspace_num = int(sys.argv[7])
    workflow_name = sys.argv[8]

    proposal_id: str | None = None
    exit_code = 1

    try:
        # Change to workspace directory
        os.chdir(workspace_dir)
        print(f"Running CRS workflow for {changespec_name}")
        print(f"Workspace: {workspace_dir}")
        print(f"Comments file: {comments_file}")
        print(f"Reviewer type: {reviewer_type}")
        print()

        # Get project basename for context files
        project_basename = os.path.splitext(os.path.basename(project_file))[0]

        # Set context file directory
        context_file_directory = os.path.expanduser(
            f"~/.gai/projects/{project_basename}/context/"
        )

        # Run the CRS workflow
        workflow = CrsWorkflow(
            context_file_directory=context_file_directory,
            comments_file=comments_file,
        )
        workflow_succeeded = workflow.run()

        if not workflow_succeeded:
            print("CRS workflow failed")
            exit_code = 1
        else:
            # Check for changes
            import subprocess

            result = subprocess.run(
                ["branch_local_changes"],
                capture_output=True,
                text=True,
            )

            if not result.stdout.strip():
                print("No changes detected from CRS workflow")
                exit_code = 1
            else:
                print("Changes detected, creating proposal...")

                # Read CRS response and save as chat file
                crs_response = ""
                if workflow.response_path and os.path.exists(workflow.response_path):
                    with open(workflow.response_path, encoding="utf-8") as f:
                        crs_response = f.read()

                # Build prompt description for chat history
                comments_ref = (
                    _shorten_path(comments_file) if comments_file else "comments"
                )
                prompt_desc = f"CRS workflow processing: {comments_ref}"

                # Save chat history
                chat_path = save_chat_history(
                    prompt=prompt_desc,
                    response=crs_response,
                    workflow="crs",
                )

                # Save the diff
                diff_path = save_diff(changespec_name, target_dir=workspace_dir)

                if diff_path:
                    # Build workflow name for the note
                    workflow_note = (
                        f"[crs ({comments_ref})]" if comments_file else "[crs]"
                    )

                    # Create proposed HISTORY entry
                    success, entry_id = _add_proposed_history_entry(
                        project_file=project_file,
                        cl_name=changespec_name,
                        note=workflow_note,
                        diff_path=diff_path,
                        chat_path=chat_path,
                    )

                    if success and entry_id:
                        proposal_id = entry_id
                        print(f"Created proposal ({proposal_id}): {workflow_note}")
                        exit_code = 0

                        # Clean workspace after creating proposal
                        from history_utils import clean_workspace

                        clean_workspace(workspace_dir)
                    else:
                        print("Failed to create proposal entry")
                        exit_code = 1
                else:
                    print("Failed to save diff")
                    exit_code = 1

    except Exception as e:
        print(f"Error running CRS workflow: {e}")
        import traceback

        traceback.print_exc()
        exit_code = 1

    finally:
        # Update comment suffix based on result
        try:
            changespecs = parse_project_file(project_file)
            for cs in changespecs:
                if cs.name == changespec_name and cs.comments:
                    if exit_code == 0 and proposal_id:
                        # Success - set suffix to proposal ID
                        set_comment_suffix(
                            project_file,
                            changespec_name,
                            reviewer_type,
                            proposal_id,
                            cs.comments,
                        )
                    else:
                        # Failure - set suffix to "!"
                        set_comment_suffix(
                            project_file,
                            changespec_name,
                            reviewer_type,
                            "!",
                            cs.comments,
                        )
                    break
        except Exception as e:
            print(f"Warning: Failed to update comment suffix: {e}")

        # Always release the workspace
        try:
            release_workspace(
                project_file,
                workspace_num,
                workflow_name,
                changespec_name,
            )
            print(f"Released workspace #{workspace_num}")
        except Exception as e:
            print(f"Warning: Failed to release workspace: {e}")

        # Write completion marker
        print()
        print(
            f"===WORKFLOW_COMPLETE=== PROPOSAL_ID: {proposal_id} EXIT_CODE: {exit_code}"
        )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
