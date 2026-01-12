#!/usr/bin/env python3
"""Background run agent runner for gai ace TUI.

This script is launched by the ace TUI to run custom agents in the background.
It handles workspace cleanup and releases the workspace upon completion.
"""

import os
import signal
import sys
import time

# Add parent directory to path for imports (use abspath to handle relative __file__)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ace.hooks import format_duration  # noqa: E402
from change_actions import execute_change_action, prompt_for_change_action  # noqa: E402
from chat_history import save_chat_history  # noqa: E402
from gemini_wrapper import invoke_agent  # noqa: E402
from rich.console import Console  # noqa: E402
from running_field import release_workspace  # noqa: E402
from shared_utils import create_artifacts_directory, ensure_str_content  # noqa: E402

# Global flag to track if we received SIGTERM
_killed = False


def _sigterm_handler(_signum: int, _frame: object) -> None:
    """Handle SIGTERM by setting killed flag and re-raising."""
    global _killed
    _killed = True
    print("\nReceived SIGTERM - agent was killed", file=sys.stderr)
    # Re-raise to allow default termination behavior
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    os.kill(os.getpid(), signal.SIGTERM)


# Register SIGTERM handler
signal.signal(signal.SIGTERM, _sigterm_handler)


def _create_new_changespec(
    console: Console,
    project_file: str,
    new_cl_name: str,
    parent_cl_name: str | None,
    saved_path: str,
    workspace_dir: str,
) -> bool:
    """Create a new WIP ChangeSpec for the agent's changes.

    Uses the summarize agent to generate a description from the chat history.

    Args:
        console: Rich Console for output.
        project_file: Path to the project file.
        new_cl_name: Name for the new ChangeSpec.
        parent_cl_name: Parent CL name (if any).
        saved_path: Path to the saved chat history file.
        workspace_dir: Path to the workspace directory.

    Returns:
        True if successful, False otherwise.
    """
    from commit_workflow.changespec_operations import add_changespec_to_project_file
    from summarize_utils import get_file_summary

    # Extract project name from project_file path
    # Path format: ~/.gai/projects/<project>/<project>.gp
    project_name = os.path.basename(os.path.dirname(project_file))

    # Generate description using summarize agent
    print("Generating description from chat history...")
    description = get_file_summary(
        saved_path,
        usage="a concise description of what changes were made to the codebase",
        fallback="Changes made by agent",
    )
    print(f"Description: {description}")

    # Create the new ChangeSpec
    # Note: CL URL will be empty initially (set when drafted)
    success = add_changespec_to_project_file(
        project=project_name,
        cl_name=new_cl_name,
        description=description,
        parent=parent_cl_name,
        cl_url="",  # Will be set when the CL is drafted
    )

    if success:
        console.print(f"[green]Created new ChangeSpec: {new_cl_name}[/green]")

        # Now commit the changes to this new CL
        # First, clean the workspace and commit
        from commit_utils import clean_workspace

        clean_workspace(workspace_dir)
        print(f"Workspace cleaned for new ChangeSpec: {new_cl_name}")
    else:
        console.print(
            f"[red]Failed to create ChangeSpec: {new_cl_name}[/red]", style="red"
        )

    return success


def main() -> None:
    """Run agent workflow and release workspace on completion."""
    # Accept 9 args (original) or 11 args (with new_cl_name and parent_cl_name)
    if len(sys.argv) not in (9, 11):
        print(
            f"Usage: {sys.argv[0]} <cl_name> <project_file> <workspace_dir> "
            "<output_path> <workspace_num> <workflow_name> <prompt_file> <timestamp> "
            "[<new_cl_name> <parent_cl_name>]",
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

    # Optional new CL parameters (empty string = not provided)
    new_cl_name_arg = sys.argv[9] if len(sys.argv) > 9 else ""
    parent_cl_name_arg = sys.argv[10] if len(sys.argv) > 10 else ""
    # Convert empty strings to None
    new_cl_name: str | None = new_cl_name_arg if new_cl_name_arg else None
    parent_cl_name: str | None = parent_cl_name_arg if parent_cl_name_arg else None

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

    print("Starting agent run")
    print(f"CL: {cl_name}")
    print(f"Workspace: {workspace_dir}")
    print(f"Workflow: {workflow_name}")
    print()
    print("=== Prompt ===")
    print(prompt)
    print("==============")
    print()

    console = Console()
    success = False

    try:
        # Change to workspace directory
        os.chdir(workspace_dir)

        # Get project name from project_file path
        # Path format: ~/.gai/projects/<project>/<project>.gp
        project_name = os.path.basename(os.path.dirname(project_file))

        # Create artifacts directory for prompt persistence
        try:
            artifacts_dir: str | None = create_artifacts_directory(
                "ace-run", project_name=project_name
            )
        except RuntimeError:
            artifacts_dir = None

        # Run the agent
        ai_result = invoke_agent(
            prompt,
            agent_type="ace-run",
            model_size="big",
            artifacts_dir=artifacts_dir,
            timestamp=timestamp,
        )

        # Prepare and save chat history
        response_content = ensure_str_content(ai_result.content)
        saved_path = save_chat_history(
            prompt=prompt,
            response=response_content,
            workflow="ace-run",
            timestamp=timestamp,
        )
        print(f"\nChat history saved to: {saved_path}")

        # Check for local changes
        from gai_utils import run_shell_command

        changes_result = run_shell_command("branch_local_changes", capture_output=True)
        has_changes = bool(changes_result.stdout.strip())

        if has_changes and new_cl_name:
            # Create a new ChangeSpec for the changes
            print(f"\nCreating new ChangeSpec: {new_cl_name}")
            _create_new_changespec(
                console=console,
                project_file=project_file,
                new_cl_name=new_cl_name,
                parent_cl_name=parent_cl_name,
                saved_path=saved_path,
                workspace_dir=workspace_dir,
            )
        elif has_changes:
            # No new_cl_name provided - create a proposal for existing CL
            prompt_result = prompt_for_change_action(
                console,
                workspace_dir,
                workflow_name="ace-run",
                chat_path=saved_path,
                shared_timestamp=timestamp,
                project_file=project_file,
                auto_reject=True,  # Non-interactive - auto-reject changes
            )

            if prompt_result is not None:
                action, action_args = prompt_result
                if action == "reject":
                    print(f"\nChanges auto-rejected (proposal: {action_args})")
                else:
                    # Execute non-reject actions (shouldn't happen with auto_reject)
                    from shared_utils import generate_workflow_tag

                    workflow_tag = generate_workflow_tag()
                    execute_change_action(
                        action=action,
                        action_args=action_args,
                        console=console,
                        target_dir=workspace_dir,
                        workflow_tag=workflow_tag,
                        workflow_name="ace-run",
                        chat_path=saved_path,
                        shared_timestamp=timestamp,
                    )
        else:
            print("\nNo changes detected")

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

    # Release workspace (unless we were killed)
    if not _killed:
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
