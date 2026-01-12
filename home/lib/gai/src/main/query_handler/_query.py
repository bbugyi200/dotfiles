"""Core query execution logic."""

import os

from change_actions import (
    execute_change_action,
    prompt_for_change_action,
)
from chat_history import save_chat_history
from rich.console import Console
from running_field import claim_workspace, release_workspace
from shared_utils import (
    create_artifacts_directory,
    generate_workflow_tag,
)

from ..utils import ensure_project_file_and_get_workspace_num


def _auto_create_wip_cl(
    chat_path: str,
    project: str,
    shared_timestamp: str,
    end_timestamp: str | None,
    custom_name: str | None = None,
    custom_message: str | None = None,
) -> tuple[bool, str | None]:
    """Auto-create a WIP CL after query completes.

    Args:
        chat_path: Path to the saved chat file.
        project: Project name.
        shared_timestamp: Timestamp for syncing files.
        end_timestamp: End timestamp for duration calculation.
        custom_name: Optional custom CL name (overrides auto-generated name).
        custom_message: Optional custom commit message (overrides summarize agent).

    Returns:
        Tuple of (success, cl_name).
    """
    from commit_workflow.workflow import CommitWorkflow
    from rich_utils import print_status
    from summarize_workflow import SummarizeWorkflow
    from workflow_utils import get_cl_name_from_branch, get_next_available_cl_name

    # Get CL name - priority order:
    # 1. custom_name (from -c flag) - always creates/updates specified ChangeSpec
    # 2. branch_name output (if on existing CL branch) - uses existing CL
    # 3. auto-generate new WIP name - only when not on any CL branch
    if custom_name:
        cl_name = custom_name
    else:
        branch_cl_name = get_cl_name_from_branch()
        if branch_cl_name:
            cl_name = branch_cl_name
        else:
            cl_name = get_next_available_cl_name(project)

    # Get commit message - use custom message if provided, otherwise summarize
    if custom_message:
        commit_message = custom_message
    else:
        # Run summarize agent on chat file
        summarize = SummarizeWorkflow(
            target_file=chat_path,
            usage="a git commit message describing the AI-assisted code changes",
            suppress_output=True,
        )
        if summarize.run() and summarize.summary:
            commit_message = summarize.summary
        else:
            commit_message = "AI-assisted code changes"
            print_status(
                "Failed to generate summary, using default message.", "warning"
            )

    # Run commit workflow
    workflow = CommitWorkflow(
        cl_name=cl_name,
        message=commit_message,
        project=project,
        chat_path=chat_path,
        timestamp=shared_timestamp,
        end_timestamp=end_timestamp,
        note="[run] Auto-created WIP CL",
    )

    success = workflow.run()
    if success:
        # Return the full CL name (with project prefix)
        full_name = (
            cl_name if cl_name.startswith(f"{project}_") else f"{project}_{cl_name}"
        )
        return True, full_name
    return False, None


def run_query(
    query: str,
    previous_history: str | None = None,
    accept_message: str | None = None,
    commit_name: str | None = None,
    commit_message: str | None = None,
) -> None:
    """Execute a query through Gemini, optionally continuing a previous conversation.

    Args:
        query: The query to send to the agent.
        previous_history: Optional previous conversation history to continue from.
        accept_message: If provided, auto-select 'a' (accept) with this message.
        commit_name: If provided along with commit_message, auto-select 'c' (commit).
        commit_message: The commit message to use with commit_name.
    """
    from gai_utils import generate_timestamp
    from gemini_wrapper.wrapper import invoke_agent
    from shared_utils import ensure_str_content

    # Get project info for workspace claiming (creates project file if needed)
    project_file, workspace_num, _ = ensure_project_file_and_get_workspace_num()

    # Save prompt to history immediately (only for new queries, not resume)
    # This ensures the prompt is visible in `gai run .` from other terminals
    if previous_history is None:
        from prompt_history import add_or_update_prompt

        add_or_update_prompt(query)

    try:
        # Build the full prompt
        if previous_history:
            full_prompt = f"""# Previous Conversation

{previous_history}

---

# New Query

{query}"""
        else:
            full_prompt = query

        # Convert escaped newlines to actual newlines
        full_prompt = full_prompt.replace("\\n", "\n")

        agent_type = "run" if previous_history is None else "run-continue"

        # Capture start timestamp for accurate duration calculation
        shared_timestamp = generate_timestamp()

        # Create artifacts directory for prompt persistence
        artifacts_timestamp: str | None = None
        try:
            artifacts_dir: str | None = create_artifacts_directory("run")
            # Extract timestamp from the directory path (last component)
            if artifacts_dir:
                artifacts_timestamp = os.path.basename(artifacts_dir)
        except RuntimeError:
            # Not in a recognized project - skip artifacts
            artifacts_dir = None

        # Claim workspace with artifacts timestamp for prompt lookup
        if project_file and workspace_num:
            claim_workspace(
                project_file,
                workspace_num,
                "run",
                None,
                pid=os.getpid(),
                artifacts_timestamp=artifacts_timestamp,
            )

        ai_result = invoke_agent(
            full_prompt,
            agent_type=agent_type,
            model_size="big",
            artifacts_dir=artifacts_dir,
            timestamp=shared_timestamp,
        )

        # Capture end timestamp for accurate duration calculation
        end_timestamp = generate_timestamp()

        # Check for file modifications and prompt for action
        console = Console()
        target_dir = os.getcwd()

        # Prepare and save chat history BEFORE prompting so we have chat_path
        response_content = ensure_str_content(ai_result.content)
        saved_path = save_chat_history(
            prompt=query,
            response=response_content,
            workflow="run",
            previous_history=previous_history,
            timestamp=shared_timestamp,
        )

        # Auto-create WIP CL after query completes
        from workflow_utils import get_project_from_workspace

        project_name = get_project_from_workspace()
        if project_name:
            success, auto_cl_name = _auto_create_wip_cl(
                chat_path=saved_path,
                project=project_name,
                shared_timestamp=shared_timestamp,
                end_timestamp=end_timestamp,
                custom_name=commit_name,
                custom_message=commit_message,
            )
            if success:
                console.print(f"[cyan]Created WIP CL: {auto_cl_name}[/cyan]")
            else:
                console.print("[yellow]Warning: Failed to auto-create WIP CL[/yellow]")

        prompt_result = prompt_for_change_action(
            console,
            target_dir,
            workflow_name="run",
            chat_path=saved_path,
            shared_timestamp=shared_timestamp,
            end_timestamp=end_timestamp,
            accept_message=accept_message,
        )

        if prompt_result is not None:
            action, action_args = prompt_result
            if action != "reject":
                workflow_tag = generate_workflow_tag()
                execute_change_action(
                    action=action,
                    action_args=action_args,
                    console=console,
                    target_dir=target_dir,
                    workflow_tag=workflow_tag,
                    workflow_name="run",
                    chat_path=saved_path,
                    shared_timestamp=shared_timestamp,
                    end_timestamp=end_timestamp,
                )

        print(f"\nChat history saved to: {saved_path}")
    finally:
        # Release workspace when done
        if project_file and workspace_num:
            release_workspace(project_file, workspace_num, "run", None)
