#!/usr/bin/env python3
"""Background mentor runner for gai loop.

This script is launched by the loop workflow to run mentors in the background.
It handles workspace cleanup and status updates upon completion.
"""

import os
import sys
import time

# Add parent directory to path for imports (use abspath to handle relative __file__)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ace.hooks import format_duration
from ace.mentors import get_latest_proposal_for_entry, set_mentor_status
from mentor_workflow import MentorWorkflow
from running_field import release_workspace


def main() -> None:
    """Run mentor workflow and update status on completion."""
    if len(sys.argv) != 11:
        print(
            f"Usage: {sys.argv[0]} <cl_name> <project_file> <mentor_name> "
            "<workspace_dir> <output_path> <workspace_num> <workflow_name> "
            "<entry_id> <profile_name> <timestamp>",
            file=sys.stderr,
        )
        sys.exit(1)

    cl_name = sys.argv[1]
    project_file = sys.argv[2]
    mentor_name = sys.argv[3]
    workspace_dir = sys.argv[4]
    output_path = sys.argv[5]
    workspace_num = int(sys.argv[6])
    workflow_name = sys.argv[7]
    entry_id = sys.argv[8]
    profile_name = sys.argv[9]
    timestamp = sys.argv[10]

    start_time = time.time()

    print(f"Starting mentor workflow: {mentor_name}")
    print(f"CL: {cl_name}")
    print(f"Profile: {profile_name}")
    print(f"Entry ID: {entry_id}")
    print(f"Workspace: {workspace_dir}")
    print()

    success = False
    try:
        # Run the mentor workflow with pre-claimed workspace info
        workflow = MentorWorkflow(
            mentor_name=mentor_name,
            cl_name=cl_name,
            workspace_num=workspace_num,
            workflow_name=workflow_name,
            workspace_dir=workspace_dir,
            timestamp=timestamp,
        )
        success = workflow.run()
    except Exception as e:
        print(f"Error running mentor workflow: {e}", file=sys.stderr)
        success = False

    end_time = time.time()
    elapsed_seconds = int(end_time - start_time)
    duration = format_duration(elapsed_seconds)

    # Determine final status
    # PASSED = mentor ran successfully and made no changes
    # FAILED = mentor ran and made changes (created a proposal)
    # Note: Currently, we mark as PASSED if the workflow succeeded
    # The mentor workflow itself handles creating proposals for changes
    final_status = "PASSED" if success else "FAILED"

    print()
    print(f"Mentor workflow completed with status: {final_status}")
    print(f"Duration: {duration}")

    # Look up if mentor created a proposal for this entry
    # Filter by mentor_name to only find proposals created by this specific mentor
    proposal_id: str | None = None
    try:
        proposal_id = get_latest_proposal_for_entry(
            project_file, cl_name, int(entry_id), mentor_name=mentor_name
        )
        if proposal_id:
            print(f"Associated proposal: {proposal_id}")
    except Exception as e:
        print(f"Error looking up proposal: {e}", file=sys.stderr)

    # Determine final status:
    # - FAILED if a proposal was created (regardless of workflow success)
    # - PASSED if workflow succeeded with no proposal
    # - FAILED if workflow errored (no proposal, already set above)
    if proposal_id:
        final_status = "FAILED"

    # Update MENTORS field with result
    # When FAILED without a proposal, include the output file path for debugging
    if final_status == "FAILED" and not proposal_id:
        # Shorten home directory to ~ for readability
        display_path = output_path.replace(os.path.expanduser("~"), "~")
        suffix = display_path
        suffix_type = "error"
    elif proposal_id:
        suffix = proposal_id
        suffix_type = "entry_ref"
    else:
        suffix = None
        suffix_type = None

    try:
        set_mentor_status(
            project_file,
            cl_name,
            entry_id,
            profile_name,
            mentor_name,
            status=final_status,
            timestamp=timestamp,
            duration=duration if final_status == "PASSED" else None,
            suffix=suffix,
            suffix_type=suffix_type,
        )
    except Exception as e:
        print(f"Error updating mentor status: {e}", file=sys.stderr)

    # Release workspace
    try:
        release_workspace(project_file, workspace_num, workflow_name, cl_name)
    except Exception as e:
        print(f"Error releasing workspace: {e}", file=sys.stderr)

    # Write completion marker
    try:
        with open(output_path, "a") as f:
            f.write("\n=== MENTOR_WORKFLOW_COMPLETE ===\n")
            f.write(f"Status: {final_status}\n")
            f.write(f"Duration: {duration}\n")
    except Exception as e:
        print(f"Error writing completion marker: {e}", file=sys.stderr)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
