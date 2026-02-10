#!/usr/bin/env python3
"""Standalone CRS workflow runner for gai axe background execution.

This script runs the CRS workflow in the background and writes completion
markers to the output file for the axe scheduler to detect when finished.

Usage:
    python3 axe_crs_runner.py <changespec_name> <project_file> <comments_file> \
        <reviewer_type> <workspace_dir> <output_file> <workspace_num> <workflow_name> \
        <timestamp>

Output file will contain:
    - Workflow output/logs
    - Completion marker: ===WORKFLOW_COMPLETE=== PROPOSAL_ID: <id> EXIT_CODE: <code>
"""

import os
import sys

# Add the parent directory to the path for imports (use abspath to handle relative __file__)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ace.changespec import ChangeSpec
from ace.comments import set_comment_suffix
from axe_runner_utils import finalize_axe_runner
from crs_workflow import CrsWorkflow
from gai_utils import shorten_path


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
    if exit_code == 0 and proposal_id:
        set_comment_suffix(
            project_file, cs.name, reviewer_type, proposal_id, cs.comments
        )
    else:
        set_comment_suffix(
            project_file,
            cs.name,
            reviewer_type,
            "Unresolved Critique Comments",
            cs.comments,
            suffix_type="error",
        )


def main() -> int:
    """Run the CRS workflow and write completion marker."""
    if len(sys.argv) != 10:
        print(
            f"Usage: {sys.argv[0]} <changespec_name> <project_file> <comments_file> "
            "<reviewer_type> <workspace_dir> <output_file> <workspace_num> "
            "<workflow_name> <timestamp>"
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
    timestamp = sys.argv[9]  # Same timestamp used in agent suffix

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

        # Get project basename
        project_basename = os.path.splitext(os.path.basename(project_file))[0]

        # Build who identifier for proposal
        comments_ref = shorten_path(comments_file) if comments_file else "comments"
        who = f"crs ({comments_ref})"

        # Run the CRS workflow with timestamp for consistent artifacts directory
        workflow = CrsWorkflow(
            comments_file=comments_file,
            timestamp=timestamp,
            who=who,
            project_name=project_basename,
        )
        workflow_succeeded = workflow.run()

        if not workflow_succeeded:
            print("CRS workflow failed")
            exit_code = 1
        else:
            # Get proposal_id from workflow
            proposal_id = workflow.proposal_id
            exit_code = 0 if proposal_id else 1

    except Exception as e:
        print(f"Error running CRS workflow: {e}")
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
            update_suffix_fn=lambda cs, pf, pid, ec: _update_comment_suffix(
                cs, pf, pid, ec, reviewer_type
            ),
        )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
