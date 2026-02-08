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
from gemini_wrapper import invoke_agent  # noqa: E402
from main.query_handler import (  # noqa: E402
    execute_standalone_steps,
    expand_embedded_workflows_in_query,
)
from running_field import release_workspace  # noqa: E402
from shared_utils import (  # noqa: E402
    convert_timestamp_to_artifacts_format,
    create_artifacts_directory,
    ensure_str_content,
)
from xprompt import process_xprompt_references  # noqa: E402

install_sigterm_handler("agent")


def _extract_embedded_outputs(
    post_workflows: list[tuple[list[Any], dict[str, Any]]],
) -> tuple[str | None, dict[str, str]]:
    """Extract diff_path and meta_* fields from embedded workflow contexts."""
    diff_path: str | None = None
    meta_fields: dict[str, str] = {}
    for _steps, ctx in post_workflows:
        for value in ctx.values():
            if not isinstance(value, dict):
                continue
            if "diff_path" in value and value["diff_path"]:
                diff_path = str(value["diff_path"])
            for k, v in value.items():
                if k.startswith("meta_") and v:
                    meta_fields[k] = str(v)
    return diff_path, meta_fields


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
    project_name_arg = sys.argv[10]
    cl_name_for_history = sys.argv[11]
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

    # Save prompt to history for future gai run sessions
    from prompt_history import add_or_update_prompt

    add_or_update_prompt(
        prompt,
        project_name=project_name_arg or None,
        branch_or_workspace=cl_name_for_history or None,
    )

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

            # Expand xprompts first (e.g., #p → #propose(note=''))
            prompt = process_xprompt_references(prompt)

            # Expand embedded workflows (e.g., #propose → prompt_part content)
            expanded_prompt, post_workflows = expand_embedded_workflows_in_query(
                prompt, artifacts_dir
            )

            # Run the agent
            ai_result = invoke_agent(
                expanded_prompt,
                agent_type="ace-run",
                model_size="big",
                artifacts_dir=artifacts_dir,
                timestamp=timestamp,
                is_home_mode=is_home_mode,
            )

            # Prepare and save chat history
            response_content = ensure_str_content(ai_result.content)
            saved_path = save_chat_history(
                prompt=expanded_prompt,
                response=response_content,
                workflow="ace-run",
                timestamp=timestamp,
            )
            print(f"\nChat history saved to: {saved_path}")

            # Execute post-steps from embedded workflows
            for post_steps, embedded_context in post_workflows:
                embedded_context["_prompt"] = expanded_prompt
                embedded_context["_response"] = response_content
                execute_standalone_steps(
                    post_steps,
                    embedded_context,
                    "ace-run-embedded",
                    artifacts_dir,
                )

            # Extract outputs from embedded workflows (e.g., #propose)
            embedded_diff_path, embedded_meta = _extract_embedded_outputs(
                post_workflows
            )

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
            if embedded_diff_path:
                done_marker["diff_path"] = embedded_diff_path
            if embedded_meta:
                done_marker["step_output"] = embedded_meta
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
