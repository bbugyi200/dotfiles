#!/usr/bin/env python3
"""Standalone fix-hook workflow runner for gai loop background execution.

This script runs the fix-hook workflow in the background and writes completion
markers to the output file for the loop to detect when finished.

Usage:
    python3 loop_fix_hook_runner.py <changespec_name> <project_file> <hook_command> \
        <hook_output_path> <workspace_dir> <output_file> <workspace_num> \
        <workflow_name> <last_history_id>

Output file will contain:
    - Workflow output/logs
    - Completion marker: ===WORKFLOW_COMPLETE=== PROPOSAL_ID: <id> EXIT_CODE: <code>
"""

import os
import sys

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.dirname(__file__))

from chat_history import save_chat_history
from gemini_wrapper import GeminiCommandWrapper
from history_utils import save_diff
from langchain_core.messages import HumanMessage
from running_field import release_workspace
from work.changespec import parse_project_file
from work.hooks import set_hook_suffix


def _strip_hook_prefix(hook_command: str) -> str:
    """Strip the '!' prefix from a hook command if present."""
    if hook_command.startswith("!"):
        return hook_command[1:]
    return hook_command


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
    """Run the fix-hook workflow and write completion marker."""
    if len(sys.argv) != 10:
        print(
            f"Usage: {sys.argv[0]} <changespec_name> <project_file> <hook_command> "
            "<hook_output_path> <workspace_dir> <output_file> <workspace_num> "
            "<workflow_name> <last_history_id>"
        )
        return 1

    changespec_name = sys.argv[1]
    project_file = sys.argv[2]
    hook_command = sys.argv[3]
    hook_output_path = sys.argv[4]
    workspace_dir = sys.argv[5]
    # output_file = sys.argv[6]  # Not used - output goes to stdout
    workspace_num = int(sys.argv[7])
    workflow_name = sys.argv[8]
    last_history_id = sys.argv[9]

    proposal_id: str | None = None
    exit_code = 1

    # Get the command to run (strip "!" prefix)
    run_hook_command = _strip_hook_prefix(hook_command)

    try:
        # Change to workspace directory
        os.chdir(workspace_dir)
        print(f"Running fix-hook workflow for {changespec_name}")
        print(f"Workspace: {workspace_dir}")
        print(f"Hook command: {run_hook_command}")
        print(f"Hook output: {hook_output_path}")
        print()

        # Build the prompt for the agent
        prompt = (
            f'The command "{run_hook_command}" is failing. The output of the last run can '
            f"be found in the @{hook_output_path} file. Can you help me fix this command by "
            "making the appropriate file changes? Verify that your fix worked when you "
            "are done by re-running that command.\n\n"
            "IMPORTANT: Do NOT commit or amend any changes. Only make file edits and "
            "leave them uncommitted.\n\nx::this_cl"
        )

        # Run the agent
        print("Running fix-hook agent...")
        print(f"Command: {run_hook_command}")
        print()

        wrapper = GeminiCommandWrapper(model_size="big")
        wrapper.set_logging_context(
            agent_type="fix-hook", suppress_output=False, workflow="fix-hook"
        )

        response = wrapper.invoke([HumanMessage(content=prompt)])
        print(f"\nAgent Response:\n{response.content}\n")

        # Check for changes
        import subprocess

        result = subprocess.run(
            ["branch_local_changes"],
            capture_output=True,
            text=True,
        )

        if not result.stdout.strip():
            print("No changes detected from fix-hook workflow")
            exit_code = 1
        else:
            print("Changes detected, creating proposal...")

            # Save chat history
            chat_path = save_chat_history(
                prompt=prompt,
                response=str(response.content),
                workflow="fix-hook",
            )

            # Save the diff
            diff_path = save_diff(changespec_name, target_dir=workspace_dir)

            if diff_path:
                # Build workflow name for the note
                history_ref = f"({last_history_id})" if last_history_id else ""
                workflow_note = f"[fix-hook {history_ref} {run_hook_command}]"

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
        print(f"Error running fix-hook workflow: {e}")
        import traceback

        traceback.print_exc()
        exit_code = 1

    finally:
        # Update hook suffix based on result
        try:
            changespecs = parse_project_file(project_file)
            for cs in changespecs:
                if cs.name == changespec_name and cs.hooks:
                    if exit_code == 0 and proposal_id:
                        # Success - set suffix to proposal ID
                        set_hook_suffix(
                            project_file,
                            changespec_name,
                            hook_command,
                            proposal_id,
                            cs.hooks,
                        )
                    else:
                        # Failure - set suffix to "!"
                        set_hook_suffix(
                            project_file,
                            changespec_name,
                            hook_command,
                            "!",
                            cs.hooks,
                        )
                    break
        except Exception as e:
            print(f"Warning: Failed to update hook suffix: {e}")

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
