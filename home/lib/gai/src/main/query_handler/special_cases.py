"""Special case handling for gai run command."""

import sys

from chat_history import list_chat_histories
from shared_utils import create_artifacts_directory

from ._editor import open_editor_for_prompt, show_prompt_history_picker
from ._query import run_query
from ._resume import handle_run_with_resume


def handle_run_special_cases(args_after_run: list[str]) -> bool:
    """Handle special cases for 'gai run' before argparse processes it.

    This handles queries that contain spaces and special flags like -l, -r.

    Args:
        args_after_run: Arguments after 'run' command.

    Returns:
        True if a special case was handled (and sys.exit was called), False otherwise.
    """
    # Handle -l/--list flag
    if args_after_run and args_after_run[0] in ("-l", "--list"):
        histories = list_chat_histories()
        if not histories:
            print("No chat histories found.")
        else:
            print("Available chat histories:")
            for history in histories:
                print(f"  {history}")
        sys.exit(0)

    # Handle '.' - show prompt history picker
    if args_after_run == ["."]:
        prompt = show_prompt_history_picker()
        if prompt is None:
            print("No prompt selected. Aborting.")
            sys.exit(1)
        run_query(prompt)
        sys.exit(0)

    # Handle no arguments - open editor for prompt
    if not args_after_run:
        prompt = open_editor_for_prompt()
        if prompt is None:
            print("No prompt provided. Aborting.")
            sys.exit(1)
        run_query(prompt)
        sys.exit(0)

    # Handle -r/--resume flag
    if args_after_run and args_after_run[0] in ("-r", "--resume"):
        handle_run_with_resume(args_after_run)
        # handle_run_with_resume calls sys.exit, but just in case:
        sys.exit(0)

    # Handle #workflow_name syntax (e.g., gai run "#split" or gai run "#explain")
    # All xprompts and workflows are treated uniformly through execute_workflow
    if args_after_run:
        potential_query = args_after_run[0]
        if potential_query.startswith("#"):
            workflow_ref = potential_query[1:]  # Strip the #

            from xprompt import (
                execute_workflow,
                get_all_prompts,
                parse_workflow_reference,
                strip_hitl_suffix,
            )

            workflow_ref, hitl_override = strip_hitl_suffix(workflow_ref)
            workflow_name, positional_args, named_args = parse_workflow_reference(
                workflow_ref
            )

            # Extract project from workflow_name if it contains a slash
            project = None
            if "/" in workflow_name:
                project = workflow_name.split("/")[0]

            # get_all_prompts() returns both workflows and converted xprompts
            prompts = get_all_prompts(project=project)
            if workflow_name in prompts:
                # Create artifacts directory in ~/.gai/projects/ so TUI can find it
                # Extract base workflow name (without project prefix) to avoid slashes in path
                base_workflow = (
                    workflow_name.split("/")[-1]
                    if "/" in workflow_name
                    else workflow_name
                )
                artifacts_dir = create_artifacts_directory(f"workflow-{base_workflow}")
                try:
                    execute_workflow(
                        workflow_name,
                        positional_args,
                        named_args,
                        artifacts_dir=artifacts_dir,
                        project=project,
                        hitl_override=hitl_override,
                    )
                    sys.exit(0)
                except Exception as e:
                    print(f"Workflow error: {e}")
                    sys.exit(1)

    # Handle direct query (not a known prompt, contains spaces)
    if args_after_run:
        potential_query = args_after_run[0]
        # Get known prompts dynamically (includes both xprompts and workflows)
        from xprompt import get_all_prompts

        known_prompts = set(get_all_prompts().keys())
        if potential_query not in known_prompts and " " in potential_query:
            run_query(potential_query)
            sys.exit(0)

    # No special case handled
    return False
