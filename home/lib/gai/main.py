import argparse
import os
import sys
from typing import NoReturn

from accept_workflow import AcceptWorkflow
from amend_workflow import AmendWorkflow
from chat_history import list_chat_histories, load_chat_history, save_chat_history
from commit_workflow import CommitWorkflow
from crs_workflow import CrsWorkflow
from fix_tests_workflow.main import FixTestsWorkflow
from gemini_wrapper import process_xfile_references
from qa_workflow import QaWorkflow
from rich.console import Console
from running_field import (
    claim_workspace,
    release_workspace,
)
from search import SearchWorkflow
from search.query import QueryParseError
from shared_utils import (
    execute_change_action,
    generate_workflow_tag,
    prompt_for_change_action,
    run_shell_command,
)
from workflow_base import BaseWorkflow


def _get_project_file_and_workspace_num() -> tuple[str | None, int | None, str | None]:
    """Get the project file path and workspace number from the current directory.

    Returns:
        Tuple of (project_file, workspace_num, project_name)
        All None if not in a recognized workspace.
    """
    try:
        result = run_shell_command("workspace_name", capture_output=True)
        if result.returncode != 0:
            return (None, None, None)
        project_name = result.stdout.strip()
        if not project_name:
            return (None, None, None)
    except Exception:
        return (None, None, None)

    # Construct project file path
    project_file = os.path.expanduser(
        f"~/.gai/projects/{project_name}/{project_name}.gp"
    )
    if not os.path.exists(project_file):
        return (None, None, None)

    # Determine workspace number from current directory
    cwd = os.getcwd()

    # Check if we're in a numbered workspace share
    workspace_num = 1
    for n in range(2, 101):
        workspace_suffix = f"{project_name}_{n}"
        if workspace_suffix in cwd:
            workspace_num = n
            break

    return (project_file, workspace_num, project_name)


def _create_parser() -> argparse.ArgumentParser:
    """Create the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        description="GAI - Google AI LangGraph workflow runner", prog="gai"
    )

    # Top-level subparsers
    top_level_subparsers = parser.add_subparsers(
        dest="command", help="Available commands", required=True
    )

    # =========================================================================
    # TOP-LEVEL SUBCOMMANDS (keep sorted alphabetically)
    # =========================================================================

    # --- cl ---
    cl_parser = top_level_subparsers.add_parser(
        "cl",
        help="CL management commands (accept, amend, commit, restore, revert)",
    )

    # CL subparsers (keep sorted alphabetically)
    cl_subparsers = cl_parser.add_subparsers(
        dest="cl_command",
        help="Available CL commands",
        required=True,
    )

    # --- cl accept ---
    accept_parser = cl_subparsers.add_parser(
        "accept",
        help="Accept one or more proposed HISTORY entries by applying their diffs",
    )
    accept_parser.add_argument(
        "proposals",
        nargs="+",
        help="Proposal entries to accept. Format: <id>[(<msg>)]. "
        "Examples: '2a', '2b(Add foobar field)'.",
    )
    # Options for 'cl accept' (keep sorted alphabetically by long option name)
    accept_parser.add_argument(
        "--cl",
        dest="cl_name",
        help="CL name (defaults to current branch name).",
    )

    # --- cl amend ---
    amend_parser = cl_subparsers.add_parser(
        "amend",
        help="Amend the current Mercurial commit with HISTORY tracking",
    )
    amend_parser.add_argument(
        "note",
        help='The note for this amend (e.g., "Fixed typo in README").',
    )
    # Options for 'cl amend' (keep sorted alphabetically by long option name)
    amend_parser.add_argument(
        "--chat",
        dest="chat_path",
        help="Path to the chat file associated with this amend.",
    )
    amend_parser.add_argument(
        "--propose",
        action="store_true",
        help="Create a proposed HISTORY entry instead of amending. "
        "Saves the diff, adds a proposed entry (e.g., 2a), and cleans workspace.",
    )
    amend_parser.add_argument(
        "--target-dir",
        dest="target_dir",
        help="Directory to run commands in (default: current directory).",
    )
    amend_parser.add_argument(
        "--timestamp",
        help="Shared timestamp for synced chat/diff files (YYmmdd_HHMMSS format).",
    )

    # --- cl commit ---
    commit_parser = cl_subparsers.add_parser(
        "commit",
        help="Create a Mercurial commit with formatted CL description and metadata",
    )
    commit_parser.add_argument(
        "cl_name",
        help="CL name to use for the commit (e.g., 'baz_feature'). The project name "
        "will be automatically prepended if not already present.",
    )
    commit_parser.add_argument(
        "file_path",
        nargs="?",
        help="Path to the file containing the CL description. "
        "If not provided, vim will be opened to write the commit message.",
    )
    # Options for 'cl commit' (keep sorted alphabetically by long option name)
    commit_parser.add_argument(
        "-b",
        "--bug",
        help="Bug number to include in the metadata tags. Defaults to output of 'branch_bug'.",
    )
    commit_parser.add_argument(
        "--chat",
        dest="chat_path",
        help="Path to the chat file associated with this commit (for HISTORY entry).",
    )
    commit_parser.add_argument(
        "-m",
        "--message",
        help="Commit message to use directly (mutually exclusive with file_path).",
    )
    commit_parser.add_argument(
        "-n",
        "--note",
        help="Custom note for the initial HISTORY entry (default: 'Initial Commit').",
    )
    commit_parser.add_argument(
        "-p",
        "--project",
        help="Project name to prepend to the CL description. Defaults to output of 'workspace_name'.",
    )
    commit_parser.add_argument(
        "--timestamp",
        help="Shared timestamp for synced chat/diff files (YYmmdd_HHMMSS format).",
    )

    # --- cl restore ---
    restore_parser = cl_subparsers.add_parser(
        "restore",
        help="Restore a reverted ChangeSpec by re-applying its diff and creating a new CL",
    )
    restore_parser.add_argument(
        "name",
        nargs="?",
        help="NAME of the reverted ChangeSpec to restore (e.g., 'foobar_feature__2')",
    )
    # Options for 'cl restore' (keep sorted alphabetically by long option name)
    restore_parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List all reverted ChangeSpecs",
    )

    # --- cl revert ---
    revert_parser = cl_subparsers.add_parser(
        "revert",
        help="Revert a ChangeSpec by pruning its CL and archiving the diff",
    )
    revert_parser.add_argument(
        "name",
        help="NAME of the ChangeSpec to revert",
    )

    # --- loop ---
    loop_parser = top_level_subparsers.add_parser(
        "loop",
        help="Continuously loop through all ChangeSpecs for status updates",
    )
    # Options for 'loop' (keep sorted alphabetically by long option name)
    loop_parser.add_argument(
        "--hook-interval",
        type=int,
        default=10,
        help="Hook check interval in seconds (default: 10)",
    )
    loop_parser.add_argument(
        "-i",
        "--interval",
        type=int,
        default=300,
        help="Polling interval in seconds (default: 300 = 5 minutes)",
    )
    loop_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show skipped ChangeSpecs in output",
    )

    # --- run ---
    run_parser = top_level_subparsers.add_parser(
        "run",
        help="Run a workflow or execute a query directly (e.g., 'gai run \"Your question here\"')",
    )
    # Options for 'run' (keep sorted alphabetically by long option name)
    run_parser.add_argument(
        "-c",
        "--continue",
        dest="continue_history",
        nargs="?",
        const="",  # Empty string means "use most recent"
        help="Continue a previous conversation. Optionally specify history file basename or path (defaults to most recent).",
    )
    run_parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List all available chat history files",
    )
    run_parser.add_argument(
        "-m",
        "--amend-message",
        dest="amend_message",
        metavar="MSG",
        help="Auto-select 'a' (amend) option with MSG as the amend message. Skips the a/c/n/x prompt.",
    )
    run_parser.add_argument(
        "-M",
        "--commit-name-and-message",
        dest="commit_name",
        nargs=2,
        metavar=("NAME", "MSG"),
        help="Auto-select 'c' (commit) option with NAME as the CL name and MSG as the commit message. Skips the a/c/n/x prompt.",
    )

    # Workflow subparsers under 'run' (keep sorted alphabetically)
    subparsers = run_parser.add_subparsers(
        dest="workflow",
        help="Available workflows. Or pass a quoted string with spaces to execute a query directly.",
        required=False,
    )

    # --- run crs ---
    crs_parser = subparsers.add_parser(
        "crs",
        help="Address Critique change request comments on a CL",
    )
    # Options for 'run crs' (keep sorted alphabetically by long option name)
    crs_parser.add_argument(
        "-D",
        "--context-file-directory",
        help="Optional directory containing markdown files to add to the agent prompt (defaults to ~/.gai/projects/<PROJECT>/context/ where <PROJECT> is from workspace_name)",
    )

    # --- run fix-tests ---
    fix_tests_parser = subparsers.add_parser(
        "fix-tests",
        help="Fix failing tests using planning, editor, and research agents with persistent blackboards",
    )
    fix_tests_parser.add_argument(
        "test_cmd", help="Test command that produces the test failure"
    )
    fix_tests_parser.add_argument(
        "test_output_file", help="Path to the file containing test failure output"
    )
    # Options for 'run fix-tests' (keep sorted alphabetically by long option name)
    fix_tests_parser.add_argument(
        "-q",
        "--clquery",
        help="Optional query for CLs/PRs to run 'clsurf a:me is:submitted <QUERY>' command and analyze previous work",
    )
    fix_tests_parser.add_argument(
        "-D",
        "--context-file-directory",
        help="Optional directory containing markdown files to add to the planner agent prompt (defaults to ~/.gai/projects/<PROJECT>/context/ where <PROJECT> is from workspace_name)",
    )
    fix_tests_parser.add_argument(
        "-r",
        "--initial-research-file",
        help="Optional path to a file containing initial research to use instead of running research agents",
    )
    fix_tests_parser.add_argument(
        "-m",
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum number of fix iterations before giving up (default: 10)",
    )
    fix_tests_parser.add_argument(
        "-u",
        "--user-instructions-file",
        help="Optional path to a file to copy as the initial user_instructions.md",
    )

    # --- run qa ---
    qa_parser = subparsers.add_parser(
        "qa",
        help="QA a CL for anti-patterns and suggest improvements",
    )
    # Options for 'run qa' (keep sorted alphabetically by long option name)
    qa_parser.add_argument(
        "-D",
        "--context-file-directory",
        help="Optional directory containing markdown files to add to the agent prompt (defaults to ~/.gai/projects/<PROJECT>/context/ where <PROJECT> is from workspace_name)",
    )

    # --- run split ---
    split_parser = subparsers.add_parser(
        "split",
        help="Split a CL into multiple smaller CLs based on a SplitSpec",
    )
    split_parser.add_argument(
        "name",
        nargs="?",
        help="NAME of the ChangeSpec to split (defaults to current branch name)",
    )
    # Options for 'run split' (keep sorted alphabetically by long option name)
    split_parser.add_argument(
        "-s",
        "--spec",
        nargs="?",
        const="",  # Allows -s without argument
        help="Path to SplitSpec YAML file. If -s is provided without a path, opens editor to create one.",
    )
    split_parser.add_argument(
        "-y",
        "--yolo",
        action="store_true",
        help="Auto-approve all prompts (spec approval and CL revert).",
    )

    # --- run summarize ---
    summarize_parser = subparsers.add_parser(
        "summarize",
        help="Summarize a file in <=20 words",
    )
    summarize_parser.add_argument(
        "target_file",
        help="Path to the file to summarize",
    )
    summarize_parser.add_argument(
        "usage",
        help="Description of how the summary will be used (e.g., 'a commit message header')",
    )

    # --- search ---
    search_parser = top_level_subparsers.add_parser(
        "search",
        help="Interactively navigate through ChangeSpecs matching a query",
    )
    # Required positional argument
    search_parser.add_argument(
        "query",
        help='Query string for filtering ChangeSpecs (e.g., \'"feature" AND "Drafted"\', \'"myproject" OR "bugfix"\')',
    )
    # Options for 'search' (keep sorted alphabetically by long option name)
    search_parser.add_argument(
        "-m",
        "--model-size",
        choices=["big", "little"],
        help="Override model size for ALL GeminiCommandWrapper instances (big or little)",
    )
    search_parser.add_argument(
        "-r",
        "--refresh-interval",
        type=int,
        default=60,
        help="Auto-refresh interval in seconds (default: 60, 0 to disable)",
    )

    return parser


def _run_query(
    query: str,
    previous_history: str | None = None,
    amend_message: str | None = None,
    commit_name: str | None = None,
    commit_message: str | None = None,
) -> None:
    """Execute a query through Gemini, optionally continuing a previous conversation.

    Args:
        query: The query to send to the agent.
        previous_history: Optional previous conversation history to continue from.
        amend_message: If provided, auto-select 'a' (amend) with this message.
        commit_name: If provided along with commit_message, auto-select 'c' (commit).
        commit_message: The commit message to use with commit_name.
    """
    from gemini_wrapper import GeminiCommandWrapper
    from history_utils import generate_timestamp
    from langchain_core.messages import HumanMessage
    from shared_utils import ensure_str_content

    # Claim workspace if in a recognized project
    project_file, workspace_num, _ = _get_project_file_and_workspace_num()
    if project_file and workspace_num:
        claim_workspace(project_file, workspace_num, "run", None)

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

        wrapper = GeminiCommandWrapper(model_size="big")
        agent_type = "run" if previous_history is None else "run-continue"
        wrapper.set_logging_context(agent_type=agent_type, suppress_output=False)

        ai_result = wrapper.invoke([HumanMessage(content=full_prompt)])

        # Check for file modifications and prompt for action
        console = Console()
        target_dir = os.getcwd()

        shared_timestamp = generate_timestamp()

        # Prepare and save chat history BEFORE prompting so we have chat_path
        rendered_query = process_xfile_references(query)
        response_content = ensure_str_content(ai_result.content)
        saved_path = save_chat_history(
            prompt=rendered_query,
            response=response_content,
            workflow="run",
            previous_history=previous_history,
            timestamp=shared_timestamp,
        )

        prompt_result = prompt_for_change_action(
            console,
            target_dir,
            workflow_name="run",
            chat_path=saved_path,
            shared_timestamp=shared_timestamp,
            amend_message=amend_message,
            commit_name=commit_name,
            commit_message=commit_message,
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
                )

        print(f"\nChat history saved to: {saved_path}")
    finally:
        # Release workspace when done
        if project_file and workspace_num:
            release_workspace(project_file, workspace_num, "run", None)


def _handle_run_with_continuation(
    args_after_run: list[str],
) -> bool:
    """Handle 'gai run' with -c flag for continuing previous conversations.

    Args:
        args_after_run: Arguments after 'run' (e.g., ['-c', 'query'] or ['-c', 'history', 'query'])

    Returns:
        True if this was a continuation request that was handled, False otherwise.
    """
    if not args_after_run:
        return False

    # Check for -c or --continue flag
    if args_after_run[0] not in ("-c", "--continue"):
        return False

    remaining = args_after_run[1:]

    # Determine history file and query
    history_file: str | None = None
    query: str | None = None

    if len(remaining) == 0:
        # Just -c with no arguments - error
        print("Error: query is required when using -c/--continue")
        sys.exit(1)
    elif len(remaining) == 1:
        # -c "query" - use most recent history
        query = remaining[0]
    else:
        # -c history_file "query" OR -c "query with" "more parts"
        # Check if first arg looks like a history file (no spaces, could be a basename)
        potential_history = remaining[0]
        # If it doesn't contain spaces and remaining[1] exists, treat as history file
        if " " not in potential_history:
            history_file = potential_history
            query = " ".join(remaining[1:])
        else:
            # First arg has spaces, so it's part of the query
            query = " ".join(remaining)

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

    _run_query(query, previous_history)
    sys.exit(0)


def main() -> NoReturn:
    # Check for 'gai run' special cases before argparse processes it
    # This allows us to handle queries that contain spaces
    if len(sys.argv) >= 2 and sys.argv[1] == "run":
        args_after_run = sys.argv[2:]

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

        # Handle -c/--continue flag
        if args_after_run and args_after_run[0] in ("-c", "--continue"):
            _handle_run_with_continuation(args_after_run)
            # _handle_run_with_continuation calls sys.exit, but just in case:
            sys.exit(0)

        # Handle -m/--amend-message and -M/--commit-name-and-message flags
        amend_message: str | None = None
        commit_name: str | None = None
        commit_message: str | None = None
        query_start_idx = 0

        if args_after_run and args_after_run[0] in ("-m", "--amend-message"):
            if len(args_after_run) < 3:
                print("Error: -m/--amend-message requires MSG and query arguments")
                sys.exit(1)
            # Verify there's a branch to amend to
            branch_result = run_shell_command("branch_name", capture_output=True)
            if branch_result.returncode != 0 or not branch_result.stdout.strip():
                print("Error: -m/--amend-message requires an existing branch to amend")
                sys.exit(1)
            amend_message = args_after_run[1]
            query_start_idx = 2
        elif args_after_run and args_after_run[0] in (
            "-M",
            "--commit-name-and-message",
        ):
            if len(args_after_run) < 4:
                print(
                    "Error: -M/--commit-name-and-message requires NAME, MSG, and query arguments"
                )
                sys.exit(1)
            commit_name = args_after_run[1]
            commit_message = args_after_run[2]
            query_start_idx = 3

        if amend_message is not None or commit_name is not None:
            # We have auto-action flags, get the query
            remaining_args = args_after_run[query_start_idx:]
            if not remaining_args:
                print("Error: query is required")
                sys.exit(1)
            query = remaining_args[0]
            _run_query(
                query,
                amend_message=amend_message,
                commit_name=commit_name,
                commit_message=commit_message,
            )
            sys.exit(0)

        # Handle direct query (not a known workflow, contains spaces)
        if args_after_run:
            potential_query = args_after_run[0]
            known_workflows = {
                "crs",
                "fix-tests",
                "qa",
                "split",
                "summarize",
            }
            if potential_query not in known_workflows and " " in potential_query:
                _run_query(potential_query)
                sys.exit(0)

    parser = _create_parser()
    args = parser.parse_args()

    workflow: BaseWorkflow

    # =========================================================================
    # COMMAND HANDLERS (keep sorted alphabetically to match parser order)
    # =========================================================================

    # --- cl ---
    if args.command == "cl":
        # CL subcommand handlers (keep sorted alphabetically)

        # --- cl accept ---
        if args.cl_command == "accept":
            from accept_workflow import parse_proposal_entries
            from rich_utils import print_status

            entries = parse_proposal_entries(args.proposals)
            if entries is None:
                print_status("Invalid proposal entry format", "error")
                sys.exit(1)

            workflow = AcceptWorkflow(
                proposals=entries,
                cl_name=args.cl_name,
            )
            success = workflow.run()
            sys.exit(0 if success else 1)

        # --- cl amend ---
        if args.cl_command == "amend":
            workflow = AmendWorkflow(
                note=args.note,
                chat_path=args.chat_path,
                timestamp=args.timestamp,
                propose=getattr(args, "propose", False),
                target_dir=getattr(args, "target_dir", None),
            )
            success = workflow.run()
            sys.exit(0 if success else 1)

        # --- cl commit ---
        if args.cl_command == "commit":
            # Validate mutual exclusivity of file_path and message
            if args.file_path and args.message:
                print(
                    "Error: --message and file_path are mutually exclusive. "
                    "Please provide only one.",
                    file=sys.stderr,
                )
                sys.exit(1)

            workflow = CommitWorkflow(
                cl_name=args.cl_name,
                file_path=args.file_path,
                bug=args.bug,
                project=args.project,
                chat_path=args.chat_path,
                timestamp=args.timestamp,
                note=args.note,
                message=args.message,
            )
            success = workflow.run()
            sys.exit(0 if success else 1)

        # --- cl restore ---
        if args.cl_command == "restore":
            from search.changespec import find_all_changespecs
            from search.restore import list_reverted_changespecs, restore_changespec

            console = Console()

            # Handle --list flag
            if args.list:
                reverted = list_reverted_changespecs()
                if not reverted:
                    console.print("[yellow]No reverted ChangeSpecs found.[/yellow]")
                else:
                    console.print("[bold]Reverted ChangeSpecs:[/bold]")
                    for cs in reverted:
                        console.print(f"  {cs.name}")
                sys.exit(0)

            # Validate required argument when not using --list
            if not args.name:
                console.print(
                    "[red]Error: name is required (unless using --list)[/red]"
                )
                sys.exit(1)

            # Find the ChangeSpec by name
            all_changespecs = find_all_changespecs()
            target_changespec = None
            for cs in all_changespecs:
                if cs.name == args.name:
                    target_changespec = cs
                    break

            if target_changespec is None:
                console.print(f"[red]Error: ChangeSpec '{args.name}' not found[/red]")
                sys.exit(1)

            success, error = restore_changespec(target_changespec, console)
            if not success:
                console.print(f"[red]Error: {error}[/red]")
                sys.exit(1)

            console.print("[green]ChangeSpec restored successfully[/green]")
            sys.exit(0)

        # --- cl revert ---
        if args.cl_command == "revert":
            from search.changespec import find_all_changespecs
            from search.revert import revert_changespec

            console = Console()

            # Find the ChangeSpec by name
            all_changespecs = find_all_changespecs()
            target_changespec = None
            for cs in all_changespecs:
                if cs.name == args.name:
                    target_changespec = cs
                    break

            if target_changespec is None:
                console.print(f"[red]Error: ChangeSpec '{args.name}' not found[/red]")
                sys.exit(1)

            success, error = revert_changespec(target_changespec, console)
            if not success:
                console.print(f"[red]Error: {error}[/red]")
                sys.exit(1)

            console.print("[green]ChangeSpec reverted successfully[/green]")
            sys.exit(0)

    # --- loop ---
    if args.command == "loop":
        from search.loop import LoopWorkflow

        loop_workflow = LoopWorkflow(
            interval_seconds=args.interval,
            verbose=args.verbose,
            hook_interval_seconds=args.hook_interval,
        )
        success = loop_workflow.run()
        sys.exit(0 if success else 1)

    # --- search ---
    if args.command == "search":
        try:
            workflow = SearchWorkflow(
                query=args.query,
                model_size_override=getattr(args, "model_size", None),
                refresh_interval=args.refresh_interval,
            )
        except QueryParseError as e:
            print(f"Error: Invalid query: {e}")
            sys.exit(1)
        success = workflow.run()
        sys.exit(0 if success else 1)

    # --- run workflows ---
    if args.command != "run":
        print(f"Unknown command: {args.command}")
        sys.exit(1)

    # Workflow handlers under 'run' (keep sorted alphabetically)
    if args.workflow == "crs":
        # Determine project_name from workspace_name command
        try:
            result = run_shell_command("workspace_name", capture_output=True)
            if result.returncode == 0:
                project_name = result.stdout.strip()
            else:
                print(
                    "Error: Could not determine project name from workspace_name command"
                )
                print(f"workspace_name failed: {result.stderr}")
                sys.exit(1)
        except Exception as e:
            print(f"Error: Could not run workspace_name command: {e}")
            sys.exit(1)

        # Determine context_file_directory (default to ~/.gai/projects/<project>/context/)
        context_file_directory = args.context_file_directory
        if not context_file_directory:
            context_file_directory = os.path.expanduser(
                f"~/.gai/projects/{project_name}/context/"
            )

        workflow = CrsWorkflow(context_file_directory=context_file_directory)
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "fix-tests":
        # Determine project_name from workspace_name command
        try:
            result = run_shell_command("workspace_name", capture_output=True)
            if result.returncode == 0:
                project_name = result.stdout.strip()
            else:
                print(
                    "Error: Could not determine project name from workspace_name command"
                )
                print(f"workspace_name failed: {result.stderr}")
                sys.exit(1)
        except Exception as e:
            print(f"Error: Could not run workspace_name command: {e}")
            sys.exit(1)

        # Determine context_file_directory (default to ~/.gai/projects/<project>/context/)
        context_file_directory = args.context_file_directory
        if not context_file_directory:
            context_file_directory = os.path.expanduser(
                f"~/.gai/projects/{project_name}/context/"
            )

        workflow = FixTestsWorkflow(
            args.test_cmd,
            args.test_output_file,
            args.user_instructions_file,
            args.max_iterations,
            args.clquery,
            args.initial_research_file,
            context_file_directory,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "qa":
        # Determine project_name from workspace_name command
        try:
            result = run_shell_command("workspace_name", capture_output=True)
            if result.returncode == 0:
                project_name = result.stdout.strip()
            else:
                print(
                    "Error: Could not determine project name from workspace_name command"
                )
                print(f"workspace_name failed: {result.stderr}")
                sys.exit(1)
        except Exception as e:
            print(f"Error: Could not run workspace_name command: {e}")
            sys.exit(1)

        # Determine context_file_directory (default to ~/.gai/projects/<project>/context/)
        context_file_directory = args.context_file_directory
        if not context_file_directory:
            context_file_directory = os.path.expanduser(
                f"~/.gai/projects/{project_name}/context/"
            )

        workflow = QaWorkflow(context_file_directory=context_file_directory)
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "split":
        from search.split_workflow import SplitWorkflow

        # Determine spec handling mode
        if args.spec is None:
            # No -s option: use agent to generate spec
            spec_path = None
            create_spec = False
            generate_spec = True
        elif args.spec == "":
            # -s without argument: create new spec in editor
            spec_path = None
            create_spec = True
            generate_spec = False
        else:
            # -s with path: load existing spec
            spec_path = args.spec
            create_spec = False
            generate_spec = False

        workflow = SplitWorkflow(
            name=args.name,
            spec_path=spec_path,
            create_spec=create_spec,
            generate_spec=generate_spec,
            yolo=args.yolo,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "summarize":
        from summarize_workflow import SummarizeWorkflow

        workflow = SummarizeWorkflow(
            target_file=args.target_file,
            usage=args.usage,
        )
        success = workflow.run()
        if success and workflow.summary:
            print(workflow.summary)
        sys.exit(0 if success else 1)
    else:
        print(f"Unknown workflow: {args.workflow}")
        sys.exit(1)


if __name__ == "__main__":
    main()
