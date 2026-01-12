#!/usr/bin/env python3
"""Standalone summarize-hook workflow runner for gai loop background execution.

This script runs the summarize workflow in the background and writes the summary
suffix back to the hook status line. Unlike fix-hook, this workflow does NOT
require a workspace since it only reads the hook output file and calls the
summarize agent.

Usage:
    python3 loop_summarize_hook_runner.py <changespec_name> <project_file> \
        <hook_command> <hook_output_path> <output_file> <entry_id> <timestamp>

Output file will contain:
    - Workflow output/logs
    - Completion marker: ===WORKFLOW_COMPLETE=== PROPOSAL_ID: None EXIT_CODE: <code>
"""

import os
import sys
from pathlib import Path

# Add the parent directory to the path for imports (use abspath to handle relative __file__)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ace.hooks import set_hook_suffix
from summarize_utils import get_file_summary

# Workflow completion marker (same pattern as other loop runners)
WORKFLOW_COMPLETE_MARKER = "===WORKFLOW_COMPLETE=== PROPOSAL_ID: "


def main() -> int:
    """Run the summarize-hook workflow and write completion marker."""
    if len(sys.argv) != 8:
        print(
            f"Usage: {sys.argv[0]} <changespec_name> <project_file> <hook_command> "
            "<hook_output_path> <output_file> <entry_id> <timestamp>"
        )
        return 1

    changespec_name = sys.argv[1]
    project_file = sys.argv[2]
    hook_command = sys.argv[3]
    hook_output_path = sys.argv[4]
    # output_file = sys.argv[5]  # Not used directly - stdout goes there
    entry_id = sys.argv[6]
    timestamp = sys.argv[7]  # Same timestamp used in agent suffix

    exit_code = 1

    try:
        print(f"Running summarize-hook workflow for {changespec_name}")
        print(f"Hook command: {hook_command}")
        print(f"Hook output: {hook_output_path}")
        print(f"Entry ID: {entry_id}")
        print()

        # Create artifacts directory using same timestamp as agent suffix
        # This ensures the Agents tab can find the prompt file
        # Convert timestamp: YYmmdd_HHMMSS -> YYYYmmddHHMMSS
        artifacts_timestamp = f"20{timestamp[:6]}{timestamp[7:]}"
        project_name = Path(project_file).parent.name
        artifacts_dir = os.path.expanduser(
            f"~/.gai/projects/{project_name}/artifacts/"
            f"summarize-hook/{artifacts_timestamp}"
        )
        Path(artifacts_dir).mkdir(parents=True, exist_ok=True)

        # Get summary of the hook failure
        summary = get_file_summary(
            target_file=hook_output_path,
            usage="a hook failure suffix on a status line",
            fallback="Hook Command Failed",
            artifacts_dir=artifacts_dir,
        )

        print(f"Generated summary: {summary}")

        # Update the hook suffix with the summary
        # Use suffix_type="summarize_complete" to indicate ready for fix-hook
        # Pass hooks=None to let set_hook_suffix do a safe read inside the lock
        # (avoids race condition when multiple summarize agents run in parallel)
        success = set_hook_suffix(
            project_file,
            changespec_name,
            hook_command,
            summary,
            hooks=None,
            entry_id=entry_id,
            suffix_type="summarize_complete",
        )
        if success:
            print(f"Updated hook suffix for entry ({entry_id}) to: {summary}")
            exit_code = 0
        else:
            print(f"Warning: Could not update hook suffix for {changespec_name}")
            exit_code = 1

    except Exception as e:
        print(f"Error running summarize-hook workflow: {e}")
        import traceback

        traceback.print_exc()
        exit_code = 1

    # Write completion marker (no proposal ID for summarize workflows)
    print()
    print(f"{WORKFLOW_COMPLETE_MARKER}None EXIT_CODE: {exit_code}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
