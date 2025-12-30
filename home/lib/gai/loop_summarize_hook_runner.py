#!/usr/bin/env python3
"""Standalone summarize-hook workflow runner for gai loop background execution.

This script runs the summarize workflow in the background and writes the summary
suffix back to the hook status line. Unlike fix-hook, this workflow does NOT
require a workspace since it only reads the hook output file and calls the
summarize agent.

Usage:
    python3 loop_summarize_hook_runner.py <changespec_name> <project_file> \
        <hook_command> <hook_output_path> <output_file> <entry_id>

Output file will contain:
    - Workflow output/logs
    - Completion marker: ===WORKFLOW_COMPLETE=== PROPOSAL_ID: None EXIT_CODE: <code>
"""

import os
import sys

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.dirname(__file__))

from ace.changespec import parse_project_file
from ace.hooks import set_hook_suffix
from summarize_utils import get_file_summary

# Workflow completion marker (same pattern as other loop runners)
WORKFLOW_COMPLETE_MARKER = "===WORKFLOW_COMPLETE=== PROPOSAL_ID: "


def main() -> int:
    """Run the summarize-hook workflow and write completion marker."""
    if len(sys.argv) != 7:
        print(
            f"Usage: {sys.argv[0]} <changespec_name> <project_file> <hook_command> "
            "<hook_output_path> <output_file> <entry_id>"
        )
        return 1

    changespec_name = sys.argv[1]
    project_file = sys.argv[2]
    hook_command = sys.argv[3]
    hook_output_path = sys.argv[4]
    # output_file = sys.argv[5]  # Not used directly - stdout goes there
    entry_id = sys.argv[6]

    exit_code = 1

    try:
        print(f"Running summarize-hook workflow for {changespec_name}")
        print(f"Hook command: {hook_command}")
        print(f"Hook output: {hook_output_path}")
        print(f"Entry ID: {entry_id}")
        print()

        # Get summary of the hook failure
        summary = get_file_summary(
            target_file=hook_output_path,
            usage="a hook failure suffix on a status line",
            fallback="Hook Command Failed",
        )

        print(f"Generated summary: {summary}")

        # Re-read the project file to get current state
        changespecs = parse_project_file(project_file)
        current_cs = None
        for cs in changespecs:
            if cs.name == changespec_name:
                current_cs = cs
                break

        if current_cs and current_cs.hooks:
            # Update the hook suffix with the summary
            set_hook_suffix(
                project_file,
                changespec_name,
                hook_command,
                summary,
                current_cs.hooks,
                entry_id=entry_id,
            )
            print(f"Updated hook suffix for entry ({entry_id}) to: {summary}")
            exit_code = 0
        else:
            print(f"Warning: Could not find ChangeSpec {changespec_name}")
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
