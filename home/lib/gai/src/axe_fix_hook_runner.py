#!/usr/bin/env python3
"""Standalone fix-hook workflow runner for gai axe background execution.

This script runs the fix-hook workflow in the background and writes completion
markers to the output file for the axe scheduler to detect when finished.

Usage:
    python3 axe_fix_hook_runner.py <changespec_name> <project_file> <hook_command> \
        <hook_output_path> <workspace_dir> <output_file> <workspace_num> \
        <workflow_name> <last_history_id> <timestamp>

Output file will contain:
    - Workflow output/logs
    - Completion marker: ===WORKFLOW_COMPLETE=== PROPOSAL_ID: <id> EXIT_CODE: <code>
"""

import os
import sys
from pathlib import Path

# Add the parent directory to the path for imports (use abspath to handle relative __file__)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ace.changespec import ChangeSpec, parse_project_file
from ace.hooks import contract_test_target_command, set_hook_suffix
from axe_runner_utils import finalize_axe_runner
from gai_utils import shorten_path, strip_hook_prefix
from gemini_wrapper import invoke_agent
from main.query_handler import (
    execute_standalone_steps,
    expand_embedded_workflows_in_query,
)
from shared_utils import create_artifacts_directory, ensure_str_content
from xprompt import escape_for_xprompt, process_xprompt_references


def _update_hook_suffix(
    cs: ChangeSpec,
    project_file: str,
    proposal_id: str | None,
    exit_code: int,
    hook_command: str,
    entry_id: str,
    output_file: str,
) -> None:
    """Update the hook suffix based on workflow result."""
    # Find the current summary from the status line (to preserve it)
    # Note: cs.hooks may be slightly stale but summary is unlikely to change
    current_summary: str | None = None
    if cs.hooks:
        for hook in cs.hooks:
            if hook.command == hook_command:
                sl = hook.get_status_line_for_commit_entry(entry_id)
                if sl:
                    current_summary = sl.summary
                break

    if exit_code == 0 and proposal_id:
        # Success - proposal ID suffix (not an error), preserve summary
        # Pass hooks=None to let set_hook_suffix do a safe read inside the lock
        # (avoids race condition when multiple fix-hook agents run in parallel)
        set_hook_suffix(
            project_file,
            cs.name,
            hook_command,
            proposal_id,
            hooks=None,
            entry_id=entry_id,
            suffix_type="plain",
            summary=current_summary,
        )
    else:
        # Failure - "!" suffix (is an error), preserve summary
        # Prepend output file path to summary for easy access to fix-hook logs
        shortened_output = shorten_path(output_file)
        if current_summary:
            current_summary = f"{shortened_output} | {current_summary}"
        else:
            current_summary = shortened_output
        set_hook_suffix(
            project_file,
            cs.name,
            hook_command,
            "fix-hook Failed",
            hooks=None,
            entry_id=entry_id,
            suffix_type="error",
            summary=current_summary,
        )


def main() -> int:
    """Run the fix-hook workflow and write completion marker."""
    if len(sys.argv) != 11:
        print(
            f"Usage: {sys.argv[0]} <changespec_name> <project_file> <hook_command> "
            "<hook_output_path> <workspace_dir> <output_file> <workspace_num> "
            "<workflow_name> <last_history_id> <timestamp>"
        )
        return 1

    changespec_name = sys.argv[1]
    project_file = sys.argv[2]
    hook_command = sys.argv[3]
    hook_output_path = sys.argv[4]
    workspace_dir = sys.argv[5]
    output_file = sys.argv[6]
    workspace_num = int(sys.argv[7])
    workflow_name = sys.argv[8]
    last_history_id = sys.argv[9]
    timestamp = sys.argv[10]  # Same timestamp used in agent suffix

    proposal_id: str | None = None
    exit_code = 1

    # Get the command to run (strip "!" prefix)
    run_hook_command = strip_hook_prefix(hook_command)

    try:
        # Change to workspace directory
        os.chdir(workspace_dir)
        print(f"Running fix-hook workflow for {changespec_name}")
        print(f"Workspace: {workspace_dir}")
        print(f"Hook command: {run_hook_command}")
        print(f"Hook output: {hook_output_path}")
        print()

        # Build the prompt using xprompt reference
        escaped_cmd = escape_for_xprompt(run_hook_command)
        escaped_output = escape_for_xprompt(hook_output_path)
        prompt_ref = (
            f'#fix_hook(hook_command="{escaped_cmd}", output_file="{escaped_output}")'
        )
        prompt = process_xprompt_references(prompt_ref)

        # Expand embedded workflows (#propose from fix_hook.md)
        # Create artifacts directory using same timestamp as agent suffix
        # This ensures the Agents tab can find the prompt file
        artifacts_dir = create_artifacts_directory(
            "fix-hook",
            project_name=Path(project_file).parent.name,
            timestamp=timestamp,
        )

        expanded_prompt, post_workflows = expand_embedded_workflows_in_query(
            prompt, artifacts_dir
        )

        # Run the agent
        print("Running fix-hook agent...")
        print(f"Command: {run_hook_command}")
        print()

        response = invoke_agent(
            expanded_prompt,
            agent_type="fix-hook",
            model_size="big",
            workflow="fix-hook",
            artifacts_dir=artifacts_dir,
            timestamp=timestamp,
        )
        response_content = ensure_str_content(response.content)
        print(f"\nAgent Response:\n{response_content}\n")

        # Build who identifier for proposal
        history_ref = f"({last_history_id})" if last_history_id else ""
        display_command = contract_test_target_command(run_hook_command)
        who = f"fix-hook {history_ref} {display_command}"

        # Execute post-steps from embedded workflows (proposal creation via #propose)
        for ewf_result in post_workflows:
            ewf_result.context["_prompt"] = expanded_prompt
            ewf_result.context["_response"] = response_content
            ewf_result.context["who"] = who
            try:
                execute_standalone_steps(
                    ewf_result.post_steps,
                    ewf_result.context,
                    "fix-hook-embedded",
                    artifacts_dir,
                )
            except Exception as step_error:
                print(f"Warning: Some embedded workflow steps failed: {step_error}")
                import traceback

                traceback.print_exc()

            # Always check for proposal_id (even if later steps failed)
            create_result = ewf_result.context.get("create_proposal", {})
            if (
                isinstance(create_result, dict)
                and create_result.get("success") == "true"
            ):
                proposal_id = create_result.get("proposal_id")
                exit_code = 0

        # Fallback: if context extraction failed, check ChangeSpec directly
        # (the create_proposal step may have written the entry to disk even
        # though embedded_context didn't capture the result properly)
        if not proposal_id:
            try:
                base_num = int(last_history_id)
                for cs in parse_project_file(project_file):
                    if cs.name == changespec_name:
                        for commit in cs.commits or []:
                            if (
                                commit.number == base_num
                                and commit.is_proposed
                                and commit.note.startswith("[fix-hook")
                            ):
                                proposal_id = commit.display_number
                                exit_code = 0
                                print(
                                    f"Fallback: found proposal ({proposal_id}) "
                                    f"in ChangeSpec despite context extraction failure"
                                )
                                break
                        break
            except (ValueError, Exception) as e:
                print(f"Warning: fallback proposal check failed: {e}")

    except Exception as e:
        print(f"Error running fix-hook workflow: {e}")
        import traceback

        traceback.print_exc()
        exit_code = 1

    finally:
        # Finalize: update suffix, release workspace, write completion marker
        finalize_axe_runner(
            project_file=project_file,
            changespec_name=changespec_name,
            workspace_num=workspace_num,
            workflow_name=workflow_name,
            proposal_id=proposal_id,
            exit_code=exit_code,
            update_suffix_fn=lambda cs, pf, pid, ec: _update_hook_suffix(
                cs, pf, pid, ec, hook_command, last_history_id, output_file
            ),
        )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
