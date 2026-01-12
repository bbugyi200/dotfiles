"""Resume handling for continuing previous conversations."""

import sys

from chat_history import list_chat_histories, load_chat_history
from shared_utils import run_shell_command

from ._query import run_query


def _parse_auto_action_flags(
    args: list[str],
) -> tuple[list[str], str | None, str | None, str | None]:
    """Parse -a/--accept and -c/--commit flags from argument list.

    Args:
        args: List of arguments to parse.

    Returns:
        Tuple of (remaining_args, accept_message, commit_name, commit_message).
    """
    accept_message: str | None = None
    commit_name: str | None = None
    commit_message: str | None = None
    remaining: list[str] = []
    i = 0

    while i < len(args):
        if args[i] in ("-a", "--accept"):
            if i + 1 >= len(args):
                print("Error: -a/--accept requires MSG argument")
                sys.exit(1)
            # Verify there's a branch to accept to
            branch_result = run_shell_command("branch_name", capture_output=True)
            if branch_result.returncode != 0 or not branch_result.stdout.strip():
                print("Error: -a/--accept requires an existing branch to accept")
                sys.exit(1)
            accept_message = args[i + 1]
            i += 2
        elif args[i] in ("-c", "--commit"):
            if i + 2 >= len(args):
                print("Error: -c/--commit requires NAME and MSG arguments")
                sys.exit(1)
            commit_name = args[i + 1]
            commit_message = args[i + 2]
            i += 3
        else:
            remaining.append(args[i])
            i += 1

    return remaining, accept_message, commit_name, commit_message


def handle_run_with_resume(
    args_after_run: list[str],
) -> bool:
    """Handle 'gai run' with -r flag for resuming previous conversations.

    Args:
        args_after_run: Arguments after 'run' (e.g., ['-r', 'query'] or ['-r', 'history', 'query'])

    Returns:
        True if this was a resume request that was handled, False otherwise.
    """
    if not args_after_run:
        return False

    # Check for -r or --resume flag
    if args_after_run[0] not in ("-r", "--resume"):
        return False

    remaining = args_after_run[1:]

    # Determine history file and query
    history_file: str | None = None
    query: str | None = None
    accept_message: str | None = None
    commit_name: str | None = None
    commit_message: str | None = None

    if len(remaining) == 0:
        # Just -r with no arguments - error
        print("Error: query is required when using -r/--resume")
        sys.exit(1)
    elif len(remaining) == 1:
        # -r "query" - use most recent history
        query = remaining[0]
    else:
        # -r history_file "query" OR -r "query with" "more parts"
        # Check if first arg looks like a history file (no spaces, could be a basename)
        potential_history = remaining[0]
        # If it doesn't contain spaces and remaining[1] exists, treat as history file
        if " " not in potential_history:
            history_file = potential_history
            remaining = remaining[1:]
        # Parse -a/-c flags from remaining args
        remaining, accept_message, commit_name, commit_message = (
            _parse_auto_action_flags(remaining)
        )
        query = " ".join(remaining) if remaining else None

    if not query:
        print("Error: query is required when using -r/--resume")
        sys.exit(1)

    # Determine which history file to use
    if not history_file:
        # Use the most recent chat history
        histories = list_chat_histories()
        if not histories:
            print("Error: No chat histories found. Run 'gai run' first.")
            sys.exit(1)
        history_file = histories[0]
        print(f"Using most recent chat history: {history_file}")

    # Load previous chat history (with heading levels incremented)
    try:
        previous_history = load_chat_history(history_file, increment_headings=True)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    run_query(
        query,
        previous_history,
        accept_message=accept_message,
        commit_name=commit_name,
        commit_message=commit_message,
    )
    sys.exit(0)
