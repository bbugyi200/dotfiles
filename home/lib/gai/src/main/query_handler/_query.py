"""Core query execution logic."""

import os
import re
import tempfile
from typing import Any

from change_actions import (
    execute_change_action,
    prompt_for_change_action,
)
from chat_history import save_chat_history
from gai_utils import run_shell_command
from rich.console import Console
from running_field import claim_workspace, release_workspace
from shared_utils import (
    create_artifacts_directory,
    generate_workflow_tag,
)
from xprompt.workflow_models import WorkflowStep

from ..utils import ensure_project_file_and_get_workspace_num

# Pattern to match workflow references in prompts
_WORKFLOW_REF_PATTERN = (
    r"(?:^|(?<=\s)|(?<=[(\[{\"']))"
    r"#([a-zA-Z_][a-zA-Z0-9_]*(?:/[a-zA-Z_][a-zA-Z0-9_]*)*)"
    r"(?:(\()|:(`[^`]*`|[a-zA-Z0-9_.-]+)|(\+))?"  # Supports backtick-delimited colon args
)


def expand_embedded_workflows_in_query(
    query: str,
    artifacts_dir: str | None = None,
) -> tuple[str, list[tuple[list[WorkflowStep], dict[str, Any]]]]:
    """Detect and expand embedded workflows in a query.

    For simple `gai run` queries, this handles workflows with `prompt_part`:
    - Executes pre-steps from embedded workflows
    - Replaces workflow references with prompt_part content
    - Returns post-steps to be executed after the main prompt

    Args:
        query: The query text that may contain workflow references.
        artifacts_dir: Optional directory for workflow artifacts.

    Returns:
        Tuple of (expanded_query, list of (post_steps, context) tuples).
    """
    from xprompt._parsing import find_matching_paren_for_args, parse_args
    from xprompt.loader import get_all_workflows
    from xprompt.workflow_executor_utils import render_template

    workflows = get_all_workflows()
    post_workflows: list[tuple[list[WorkflowStep], dict[str, Any]]] = []

    # Find all potential workflow references
    matches = list(re.finditer(_WORKFLOW_REF_PATTERN, query, re.MULTILINE))

    # Process from last to first to preserve positions
    for match in reversed(matches):
        name = match.group(1)

        # Skip if not a workflow
        if name not in workflows:
            continue

        workflow = workflows[name]

        # Skip workflows without prompt_part (execute as full workflow)
        if not workflow.has_prompt_part():
            continue

        # Extract arguments
        has_open_paren = match.group(2) is not None
        colon_arg = match.group(3)
        plus_suffix = match.group(4)
        match_end = match.end()

        positional_args: list[str] = []
        named_args: dict[str, str] = {}

        if has_open_paren:
            paren_start = match.end() - 1
            paren_end = find_matching_paren_for_args(query, paren_start)
            if paren_end is not None:
                paren_content = query[paren_start + 1 : paren_end]
                positional_args, named_args = parse_args(paren_content)
                match_end = paren_end + 1
        elif colon_arg is not None:
            # Strip backticks if present (backtick-delimited syntax)
            if colon_arg.startswith("`") and colon_arg.endswith("`"):
                colon_arg = colon_arg[1:-1]
            positional_args = [colon_arg]
        elif plus_suffix is not None:
            positional_args = ["true"]

        # Build args dict
        args: dict[str, Any] = dict(named_args)
        for i, value in enumerate(positional_args):
            if i < len(workflow.inputs):
                input_arg = workflow.inputs[i]
                if input_arg.name not in args:
                    args[input_arg.name] = value

        # Apply defaults
        for input_arg in workflow.inputs:
            if input_arg.name not in args and input_arg.default is not None:
                args[input_arg.name] = str(input_arg.default)

        # Get pre and post steps
        pre_steps = workflow.get_pre_prompt_steps()
        post_steps = workflow.get_post_prompt_steps()

        # Create isolated context for the embedded workflow
        embedded_context: dict[str, Any] = dict(args)

        # Execute pre-steps using a minimal workflow executor
        if pre_steps:
            embedded_context = execute_standalone_steps(
                pre_steps, embedded_context, workflow.name, artifacts_dir
            )

        # Render prompt_part with the embedded context (args + pre-step outputs)
        prompt_part_content = workflow.get_prompt_part_content()
        if prompt_part_content:
            prompt_part_content = render_template(prompt_part_content, embedded_context)

            # Handle section content (starting with ### or ---)
            # Prepend \n\n when the workflow ref is not at the start of a line
            if prompt_part_content.startswith("###") or prompt_part_content.startswith(
                "---"
            ):
                is_at_line_start = (
                    match.start() == 0 or query[match.start() - 1] == "\n"
                )
                if not is_at_line_start:
                    prompt_part_content = "\n\n" + prompt_part_content

        # Replace the workflow reference with the prompt_part content
        query = query[: match.start()] + prompt_part_content + query[match_end:]

        # Store post-steps for execution after the main prompt
        if post_steps:
            post_workflows.append((post_steps, embedded_context))

    return query, post_workflows


def execute_standalone_steps(
    steps: list[WorkflowStep],
    context: dict[str, Any],
    workflow_name: str,
    artifacts_dir: str | None = None,
) -> dict[str, Any]:
    """Execute workflow steps in a standalone context.

    Used for running pre/post steps from embedded workflows outside of
    the normal workflow executor context.

    Args:
        steps: List of workflow steps to execute.
        context: Initial context (args).
        workflow_name: Name of the workflow (for artifacts).
        artifacts_dir: Optional directory for artifacts.

    Returns:
        Updated context with step outputs.

    Raises:
        WorkflowExecutionError: If any step fails.
    """
    import subprocess
    import sys

    from xprompt.workflow_executor_utils import parse_bash_output, render_template
    from xprompt.workflow_models import WorkflowExecutionError

    for step in steps:
        if step.is_bash_step() and step.bash:
            rendered_command = render_template(step.bash, context)
            try:
                result = subprocess.run(
                    rendered_command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=os.getcwd(),
                )
            except Exception as e:
                raise WorkflowExecutionError(
                    f"Failed to execute bash step '{step.name}': {e}"
                ) from e

            if result.returncode != 0:
                error_msg = (
                    result.stderr.strip()
                    if result.stderr
                    else f"Exit code {result.returncode}"
                )
                raise WorkflowExecutionError(
                    f"Bash step '{step.name}' failed: {error_msg}"
                )

            output = parse_bash_output(result.stdout)
            context[step.name] = output

        elif step.is_python_step() and step.python:
            rendered_code = render_template(step.python, context)
            try:
                result = subprocess.run(
                    [sys.executable, "-c", rendered_code],
                    capture_output=True,
                    text=True,
                    cwd=os.getcwd(),
                )
            except Exception as e:
                raise WorkflowExecutionError(
                    f"Failed to execute python step '{step.name}': {e}"
                ) from e

            if result.returncode != 0:
                error_msg = (
                    result.stderr.strip()
                    if result.stderr
                    else f"Exit code {result.returncode}"
                )
                raise WorkflowExecutionError(
                    f"Python step '{step.name}' failed: {error_msg}"
                )

            output = parse_bash_output(result.stdout)
            context[step.name] = output

        elif step.is_prompt_step() and step.prompt:
            from gemini_wrapper import invoke_agent
            from shared_utils import ensure_str_content
            from xprompt import process_xprompt_references

            rendered_prompt = render_template(step.prompt, context)
            expanded_prompt = process_xprompt_references(rendered_prompt)

            # Create temp artifacts dir if not provided
            step_artifacts_dir = artifacts_dir
            if step_artifacts_dir is None:
                step_artifacts_dir = tempfile.mkdtemp(
                    prefix=f"embedded-{workflow_name}-"
                )

            response = invoke_agent(
                expanded_prompt,
                agent_type=f"embedded-{workflow_name}-{step.name}",
                artifacts_dir=step_artifacts_dir,
            )
            response_text = ensure_str_content(response.content)

            # Store raw output for prompt steps
            context[step.name] = {"_raw": response_text}

    return context


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
                os.getpid(),
                None,
                artifacts_timestamp=artifacts_timestamp,
            )

        # Expand xprompts FIRST, so workflow references like #propose can be produced
        # from aliases like #p before workflow expansion looks for them
        from xprompt import process_xprompt_references

        full_prompt = process_xprompt_references(full_prompt)

        # Expand embedded workflows (workflows with prompt_part)
        # This executes pre-steps and replaces workflow refs with prompt_part content
        expanded_prompt, post_workflows = expand_embedded_workflows_in_query(
            full_prompt, artifacts_dir
        )

        ai_result = invoke_agent(
            expanded_prompt,
            agent_type=agent_type,
            model_size="big",
            artifacts_dir=artifacts_dir,
            timestamp=shared_timestamp,
        )

        # Get response content before executing post-steps
        response_content = ensure_str_content(ai_result.content)

        # Execute post-steps from embedded workflows
        for post_steps, embedded_context in post_workflows:
            # Make agent prompt and response available to post-steps
            embedded_context["_prompt"] = expanded_prompt
            embedded_context["_response"] = response_content
            execute_standalone_steps(
                post_steps, embedded_context, "run-embedded", artifacts_dir
            )

        # Capture end timestamp for accurate duration calculation
        end_timestamp = generate_timestamp()

        # Check for file modifications and prompt for action
        console = Console()
        target_dir = os.getcwd()

        # Prepare and save chat history BEFORE prompting so we have chat_path
        saved_path = save_chat_history(
            prompt=query,
            response=response_content,
            workflow="run",
            previous_history=previous_history,
            timestamp=shared_timestamp,
        )

        # Auto-create WIP CL only if there are file changes
        from workflow_utils import get_project_from_workspace

        project_name = get_project_from_workspace()
        if project_name:
            # Check for local changes first
            changes_result = run_shell_command(
                "branch_local_changes", capture_output=True
            )
            if changes_result.stdout.strip():
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
                    console.print(
                        "[yellow]Warning: Failed to auto-create WIP CL[/yellow]"
                    )
            # If no changes, silently skip CL creation

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
