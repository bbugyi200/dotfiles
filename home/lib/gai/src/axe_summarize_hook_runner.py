#!/usr/bin/env python3
"""Standalone summarize-hook workflow runner for gai axe background execution.

This script runs the summarize workflow in the background and writes the summary
suffix back to the hook status line. Unlike fix-hook, this workflow does NOT
require a workspace since it only reads the hook output file and calls the
summarize agent.

Usage:
    python3 axe_summarize_hook_runner.py <changespec_name> <project_file> \
        <hook_command> <hook_output_path> <output_file> <entry_id> <timestamp>

Output file will contain:
    - Workflow output/logs
    - Completion marker: ===WORKFLOW_COMPLETE=== PROPOSAL_ID: None EXIT_CODE: <code>
"""

import os
import subprocess
import sys
from pathlib import Path

# Add the parent directory to the path for imports (use abspath to handle relative __file__)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ace.hooks import set_hook_suffix
from metahook_config import MetahookConfig, find_matching_metahook
from summarize_utils import get_file_summary

# Workflow completion marker (same pattern as other axe runners)
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

        # Check for matching metahook
        hook_output_content = Path(hook_output_path).read_text(encoding="utf-8")
        matching_metahook: MetahookConfig | None = find_matching_metahook(
            hook_command, hook_output_content
        )

        if matching_metahook:
            print(f"Found matching metahook: {matching_metahook.name}")
            metahook_script = f"gai_metahook_{matching_metahook.name}"

            try:
                result = subprocess.run(
                    [metahook_script, hook_output_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode != 0:
                    # Metahook returned non-zero - use its output as summary
                    summary = result.stdout.strip() or "Metahook failed"
                    print(f"Metahook completed with summary: {summary}")

                    success = set_hook_suffix(
                        project_file,
                        changespec_name,
                        hook_command,
                        summary,
                        hooks=None,
                        entry_id=entry_id,
                        suffix_type="metahook_complete",
                    )
                    if success:
                        print(
                            f"Updated hook suffix for entry ({entry_id}) to: {summary}"
                        )
                        exit_code = 0
                    else:
                        print(
                            f"Warning: Could not update hook suffix for {changespec_name}"
                        )
                        exit_code = 1

                    # Write completion marker and return early
                    print()
                    print(f"{WORKFLOW_COMPLETE_MARKER}None EXIT_CODE: {exit_code}")
                    return exit_code
                else:
                    print("Metahook returned 0, continuing with normal summarize flow")

            except FileNotFoundError:
                print(
                    f"Metahook script not found: {metahook_script}, continuing with normal flow"
                )
            except subprocess.TimeoutExpired:
                print(
                    f"Metahook script timed out: {metahook_script}, continuing with normal flow"
                )
            except Exception as e:
                print(f"Error running metahook: {e}, continuing with normal flow")

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
