"""Resume handling for continuing previous conversations."""

import sys

from chat_history import list_chat_histories, load_chat_history

from ._query import run_query


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
    )
    sys.exit(0)
