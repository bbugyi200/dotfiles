"""Special case handling for gai run command."""

import sys

from chat_history import list_chat_histories
from shared_utils import run_shell_command

from ._editor import open_editor_for_prompt, show_prompt_history_picker
from ._query import run_query
from ._resume import handle_run_with_resume


def handle_run_special_cases(args_after_run: list[str]) -> bool:
    """Handle special cases for 'gai run' before argparse processes it.

    This handles queries that contain spaces and special flags like -l, -r, -a, -c.

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

    # Handle -a/--accept and -c/--commit flags
    accept_message: str | None = None
    commit_name: str | None = None
    commit_message: str | None = None
    query_start_idx = 0

    if args_after_run and args_after_run[0] in ("-a", "--accept"):
        if len(args_after_run) < 3:
            print("Error: -a/--accept requires MSG and query arguments")
            sys.exit(1)
        # Verify there's a branch to accept to
        branch_result = run_shell_command("branch_name", capture_output=True)
        if branch_result.returncode != 0 or not branch_result.stdout.strip():
            print("Error: -a/--accept requires an existing branch to accept")
            sys.exit(1)
        accept_message = args_after_run[1]
        query_start_idx = 2
    elif args_after_run and args_after_run[0] in (
        "-c",
        "--commit",
    ):
        if len(args_after_run) < 4:
            print("Error: -c/--commit requires NAME, MSG, and query arguments")
            sys.exit(1)
        commit_name = args_after_run[1]
        commit_message = args_after_run[2]
        query_start_idx = 3

    if accept_message is not None or commit_name is not None:
        # We have auto-action flags, get the query
        remaining_args = args_after_run[query_start_idx:]
        if not remaining_args:
            print("Error: query is required")
            sys.exit(1)
        query = remaining_args[0]
        run_query(
            query,
            accept_message=accept_message,
            commit_name=commit_name,
            commit_message=commit_message,
        )
        sys.exit(0)

    # Handle direct query (not a known workflow, contains spaces)
    if args_after_run:
        potential_query = args_after_run[0]
        known_workflows = {
            "crs",
            "fix-hook",
            "mentor",
            "split",
            "summarize",
        }
        if potential_query not in known_workflows and (
            " " in potential_query or potential_query.startswith("#")
        ):
            run_query(potential_query)
            sys.exit(0)

    # No special case handled
    return False
