#!/usr/bin/env python3
"""Background workflow runner for gai ace TUI.

This script is launched by the ace TUI to run workflows in the background
with proper workspace management. It handles workspace cleanup and releases
the workspace upon completion.
"""

import json
import os
import sys

# Add parent directory to path for imports (use abspath to handle relative __file__)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from axe_runner_utils import install_sigterm_handler, prepare_workspace  # noqa: E402
from running_field import release_workspace  # noqa: E402

install_sigterm_handler("workflow")


def main() -> None:
    """Run workflow and release workspace on completion."""
    # Accept 9 args: workflow_name, positional_args_json, named_args_json,
    # project_file, workspace_dir, workspace_num, artifacts_dir,
    # update_target, is_home_mode
    if len(sys.argv) != 10:
        print(
            f"Usage: {sys.argv[0]} <workflow_name> <positional_args_json> "
            "<named_args_json> <project_file> <workspace_dir> <workspace_num> "
            "<artifacts_dir> <update_target> <is_home_mode>",
            file=sys.stderr,
        )
        sys.exit(1)

    workflow_name = sys.argv[1]
    positional_args_json = sys.argv[2]
    named_args_json = sys.argv[3]
    project_file = sys.argv[4]
    workspace_dir = sys.argv[5]
    workspace_num = int(sys.argv[6])
    artifacts_dir = sys.argv[7]
    update_target = sys.argv[8]
    is_home_mode_arg = sys.argv[9]

    # Parse JSON args
    positional_args: list[str] = json.loads(positional_args_json)
    named_args: dict[str, str] = json.loads(named_args_json)
    is_home_mode: bool = bool(is_home_mode_arg)

    # Get CL name from update_target for logging/backup purposes
    cl_name = update_target or "workflow"

    print(f"Starting workflow: {workflow_name}")
    print(f"Workspace: {workspace_dir}")
    print(f"Arguments: {positional_args}, {named_args}")
    print()

    # Prepare workspace before running workflow (skip for home mode)
    if update_target and not is_home_mode:
        print("=== Preparing Workspace ===")
        if not prepare_workspace(
            workspace_dir, cl_name, update_target, backup_suffix="workflow"
        ):
            print("Failed to prepare workspace", file=sys.stderr)
            sys.exit(1)
        print("===========================")
        print()

    success = False
    try:
        # Change to workspace directory
        os.chdir(workspace_dir)

        # Ensure artifacts directory exists
        os.makedirs(artifacts_dir, exist_ok=True)

        # Execute the workflow
        from xprompt import execute_workflow

        # Inject cl_name into named_args so it's available in workflow context
        workflow_named_args = dict(named_args)
        workflow_named_args["cl_name"] = cl_name

        execute_workflow(
            workflow_name,
            positional_args,
            workflow_named_args,
            artifacts_dir=artifacts_dir,
            silent=True,
        )
        success = True
        print(f"\nWorkflow '{workflow_name}' completed successfully")

    except Exception as e:
        print(f"Error running workflow: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        success = False

    finally:
        # Release workspace (skip for home mode - no workspace to release)
        if not is_home_mode:
            # Always release workspace, even if killed via SIGTERM
            # This prevents zombie workspace claims in the RUNNING field
            try:
                # Build workflow field name to match what was used for claiming
                workflow_field_name = f"workflow({workflow_name})"
                release_workspace(
                    project_file, workspace_num, workflow_field_name, cl_name
                )
                print("Workspace released")
            except Exception as e:
                print(f"Error releasing workspace: {e}", file=sys.stderr)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
