#!/usr/bin/env python3
"""Background run agent runner for gai ace TUI.

This script is launched by the ace TUI to run custom agents in the background.
It handles workspace cleanup and releases the workspace upon completion.
"""

import json
import os
import sys
import time
from typing import Any

# Add parent directory to path for imports (use abspath to handle relative __file__)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ace.hooks import format_duration  # noqa: E402
from axe_runner_utils import install_sigterm_handler, prepare_workspace  # noqa: E402
from chat_history import save_chat_history  # noqa: E402
from running_field import release_workspace  # noqa: E402
from shared_utils import (  # noqa: E402
    convert_timestamp_to_artifacts_format,
    create_artifacts_directory,
)

install_sigterm_handler("agent")


def main() -> None:
    """Run agent workflow and release workspace on completion."""
    # Accept 13 args: cl_name, project_file, workspace_dir, output_path,
    # workspace_num, workflow_name, prompt_file, timestamp,
    # update_target, project_name, cl_name_for_history, is_home_mode
    if len(sys.argv) != 13:
        print(
            f"Usage: {sys.argv[0]} <cl_name> <project_file> <workspace_dir> "
            "<output_path> <workspace_num> <workflow_name> <prompt_file> <timestamp> "
            "<update_target> <project_name> "
            "<cl_name_for_history> <is_home_mode>",
            file=sys.stderr,
        )
        sys.exit(1)

    cl_name = sys.argv[1]
    project_file = sys.argv[2]
    workspace_dir = sys.argv[3]
    output_path = sys.argv[4]
    workspace_num = int(sys.argv[5])
    workflow_name = sys.argv[6]
    prompt_file = sys.argv[7]
    timestamp = sys.argv[8]

    # Optional parameters (empty string = not provided)
    update_target = sys.argv[9]
    # sys.argv[10] (project_name) and sys.argv[11] (cl_name_for_history)
    # are no longer used here; prompt history is saved by the TUI before launch.
    is_home_mode_arg = sys.argv[12]
    is_home_mode: bool = bool(is_home_mode_arg)

    # Read prompt from temp file
    try:
        with open(prompt_file, encoding="utf-8") as f:
            prompt = f.read()
    except Exception as e:
        print(f"Error reading prompt file: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Clean up temp prompt file
        try:
            os.unlink(prompt_file)
        except OSError:
            pass

    start_time = time.time()
    success = False
    duration = "0s"

    print("Starting agent run")
    print(f"CL: {cl_name}")
    print(f"Workspace: {workspace_dir}")
    print(f"Workflow: {workflow_name}")
    print()
    print("=== Prompt ===")
    print(prompt)
    print("==============")
    print()

    # Prepare workspace before running agent (skip for home mode)
    if update_target and not is_home_mode:
        print("=== Preparing Workspace ===")
        if not prepare_workspace(
            workspace_dir, cl_name, update_target, backup_suffix="ace"
        ):
            print("Failed to prepare workspace", file=sys.stderr)
            sys.exit(1)
        print("===========================")
        print()

    # Track running marker path for cleanup (home mode only)
    running_marker_path: str | None = None

    try:
        try:
            # Change to workspace directory
            os.chdir(workspace_dir)

            # Get project name from project_file path (or use "home" for home mode)
            # Path format: ~/.gai/projects/<project>/<project>.gp
            if is_home_mode:
                project_name = "home"
            else:
                project_name = os.path.basename(os.path.dirname(project_file))

            # Create artifacts directory using shared timestamp
            artifacts_timestamp = convert_timestamp_to_artifacts_format(timestamp)
            artifacts_dir = create_artifacts_directory(
                "ace-run",
                project_name=project_name,
                timestamp=timestamp,
            )

            # Write running marker for home mode (no workspace tracking available)
            if is_home_mode:
                running_marker_path = os.path.join(artifacts_dir, "running.json")
                running_marker = {
                    "cl_name": cl_name,
                    "pid": os.getpid(),
                    "timestamp": timestamp,
                    "prompt": prompt,
                }
                with open(running_marker_path, "w", encoding="utf-8") as f:
                    json.dump(running_marker, f, indent=2)

            # Create anonymous workflow and execute through WorkflowExecutor
            from xprompt.models import create_anonymous_workflow
            from xprompt.processor import execute_workflow

            anon_workflow = create_anonymous_workflow(prompt)
            result = execute_workflow(
                anon_workflow.name,
                [],
                {},
                artifacts_dir=artifacts_dir,
                silent=True,
                workflow_obj=anon_workflow,
            )

            # Extract response text for chat history
            response_content = result.response_text or ""

            # Prepare and save chat history
            saved_path = save_chat_history(
                prompt=prompt,
                response=response_content,
                workflow="ace-run",
                timestamp=timestamp,
            )
            print(f"\nChat history saved to: {saved_path}")

            # Write done marker
            done_marker: dict[str, Any] = {
                "cl_name": cl_name,
                "project_file": project_file,
                "timestamp": timestamp,
                "artifacts_timestamp": artifacts_timestamp,
                "response_path": saved_path,
                "outcome": "completed",
                "workspace_num": workspace_num,
            }
            done_path = os.path.join(artifacts_dir, "done.json")
            with open(done_path, "w", encoding="utf-8") as f:
                json.dump(done_marker, f, indent=2)
            print(f"Done marker written to: {done_path}")

            success = True

        except Exception as e:
            print(f"Error running agent: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()
            success = False
            # Write error done marker so TUI can display the error
            try:
                error_done: dict[str, Any] = {
                    "cl_name": cl_name,
                    "project_file": project_file,
                    "timestamp": timestamp,
                    "artifacts_timestamp": artifacts_timestamp,
                    "outcome": "failed",
                    "error": str(e),
                    "workspace_num": workspace_num,
                }
                done_path = os.path.join(artifacts_dir, "done.json")
                with open(done_path, "w", encoding="utf-8") as f:
                    json.dump(error_done, f, indent=2)
            except Exception:
                pass  # Best effort

        end_time = time.time()
        elapsed_seconds = int(end_time - start_time)
        duration = format_duration(elapsed_seconds)

        print()
        print(f"Agent completed with status: {'SUCCESS' if success else 'FAILED'}")
        print(f"Duration: {duration}")

    finally:
        # Clean up running marker for home mode (done.json replaces it)
        if running_marker_path and os.path.exists(running_marker_path):
            try:
                os.unlink(running_marker_path)
            except OSError:
                pass

        # Release workspace (skip for home mode - no workspace to release)
        if not is_home_mode:
            # Always release workspace, even if killed via SIGTERM
            # This prevents zombie workspace claims in the RUNNING field
            try:
                release_workspace(project_file, workspace_num, workflow_name, cl_name)
                print("Workspace released")
            except Exception as e:
                print(f"Error releasing workspace: {e}", file=sys.stderr)

        # Write completion marker
        try:
            with open(output_path, "a") as f:
                f.write("\n=== AGENT_RUN_COMPLETE ===\n")
                f.write(f"Status: {'SUCCESS' if success else 'FAILED'}\n")
                f.write(f"Duration: {duration}\n")
        except Exception as e:
            print(f"Error writing completion marker: {e}", file=sys.stderr)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
