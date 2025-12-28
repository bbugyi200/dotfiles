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

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import HumanMessage
from loop_runner_utils import (
    create_proposal_from_changes,
    finalize_loop_runner,
)
from search.changespec import ChangeSpec
from search.hooks import set_hook_suffix


def _strip_hook_prefix(hook_command: str) -> str:
    """Strip the '!' and '$' prefixes from a hook command if present."""
    return hook_command.lstrip("!$")


def _update_hook_suffix(
    cs: ChangeSpec,
    project_file: str,
    proposal_id: str | None,
    exit_code: int,
    hook_command: str,
) -> None:
    """Update the hook suffix based on workflow result."""
    if not cs.hooks:
        return
    suffix = proposal_id if exit_code == 0 and proposal_id else "!"
    set_hook_suffix(project_file, cs.name, hook_command, suffix, cs.hooks)


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
        response_content = str(response.content)
        print(f"\nAgent Response:\n{response_content}\n")

        # Build workflow note with summary
        history_ref = f"({last_history_id})" if last_history_id else ""

        # Get summary of the fix-hook response for the HISTORY entry header
        summary = ""
        if response_content:
            import tempfile

            # Save response to temp file for summarization
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False
            ) as f:
                f.write(response_content)
                temp_path = f.name

            try:
                from summarize_utils import get_file_summary

                summary = get_file_summary(
                    target_file=temp_path,
                    usage="a HISTORY entry header describing what changes were made to fix the hook",
                    fallback="",
                )
            finally:
                os.unlink(temp_path)

        if summary:
            workflow_note = f"[fix-hook {history_ref} {run_hook_command}] {summary}"
        else:
            workflow_note = f"[fix-hook {history_ref} {run_hook_command}]"

        # Create proposal from changes
        proposal_id, exit_code = create_proposal_from_changes(
            project_file=project_file,
            cl_name=changespec_name,
            workspace_dir=workspace_dir,
            workflow_note=workflow_note,
            prompt=prompt,
            response=response_content,
            workflow="fix-hook",
        )

    except Exception as e:
        print(f"Error running fix-hook workflow: {e}")
        import traceback

        traceback.print_exc()
        exit_code = 1

    finally:
        # Finalize: update suffix, release workspace, write completion marker
        finalize_loop_runner(
            project_file=project_file,
            changespec_name=changespec_name,
            workspace_num=workspace_num,
            workflow_name=workflow_name,
            proposal_id=proposal_id,
            exit_code=exit_code,
            update_suffix_fn=lambda cs, pf, pid, ec: _update_hook_suffix(
                cs, pf, pid, ec, hook_command
            ),
        )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
