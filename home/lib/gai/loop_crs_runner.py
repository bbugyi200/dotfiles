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

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.dirname(__file__))

from ace.changespec import ChangeSpec
from ace.comments import set_comment_suffix
from crs_workflow import CrsWorkflow
from gai_utils import shorten_path
from loop_runner_utils import (
    create_proposal_from_changes,
    finalize_loop_runner,
)


def _update_comment_suffix(
    cs: ChangeSpec,
    project_file: str,
    proposal_id: str | None,
    exit_code: int,
    reviewer_type: str,
) -> None:
    """Update the comment suffix based on workflow result."""
    if not cs.comments:
        return
    suffix = proposal_id if exit_code == 0 and proposal_id else "!"
    set_comment_suffix(project_file, cs.name, reviewer_type, suffix, cs.comments)


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
            # Read CRS response for chat history
            crs_response = ""
            if workflow.response_path and os.path.exists(workflow.response_path):
                with open(workflow.response_path, encoding="utf-8") as f:
                    crs_response = f.read()

            # Build references for note and prompt
            comments_ref = shorten_path(comments_file) if comments_file else "comments"
            prompt_desc = f"CRS workflow processing: {comments_ref}"

            # Get summary of the CRS response for the HISTORY entry header
            summary = ""
            if workflow.response_path and os.path.exists(workflow.response_path):
                from summarize_utils import get_file_summary

                summary = get_file_summary(
                    target_file=workflow.response_path,
                    usage="a HISTORY entry header describing what the CRS workflow accomplished",
                    fallback="",
                )

            if summary:
                workflow_note = f"[crs ({comments_ref})] {summary}"
            else:
                workflow_note = f"[crs ({comments_ref})]" if comments_file else "[crs]"

            # Create proposal from changes
            proposal_id, exit_code = create_proposal_from_changes(
                project_file=project_file,
                cl_name=changespec_name,
                workspace_dir=workspace_dir,
                workflow_note=workflow_note,
                prompt=prompt_desc,
                response=crs_response,
                workflow="crs",
            )

    except Exception as e:
        print(f"Error running CRS workflow: {e}")
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
            update_suffix_fn=lambda cs, pf, pid, ec: _update_comment_suffix(
                cs, pf, pid, ec, reviewer_type
            ),
        )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
