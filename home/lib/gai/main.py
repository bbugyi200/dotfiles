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
from shared_utils import (
    execute_change_action,
    generate_workflow_tag,
    prompt_for_change_action,
    run_shell_command,
)
from work import WorkWorkflow
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

    # Create 'run' subcommand
    run_parser = top_level_subparsers.add_parser(
        "run",
        help="Run a workflow or execute a query directly (e.g., 'gai run \"Your question here\"')",
    )

    # Workflow subparsers under 'run'
    subparsers = run_parser.add_subparsers(
        dest="workflow",
        help="Available workflows. Or pass a quoted string with spaces to execute a query directly.",
        required=False,
    )

    # fix-tests subcommand
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
    fix_tests_parser.add_argument(
        "-u",
        "--user-instructions-file",
        help="Optional path to a file to copy as the initial user_instructions.md",
    )
    fix_tests_parser.add_argument(
        "-m",
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum number of fix iterations before giving up (default: 10)",
    )
    fix_tests_parser.add_argument(
        "-q",
        "--clquery",
        help="Optional query for CLs/PRs to run 'clsurf a:me is:submitted <QUERY>' command and analyze previous work",
    )
    fix_tests_parser.add_argument(
        "-r",
        "--initial-research-file",
        help="Optional path to a file containing initial research to use instead of running research agents",
    )
    fix_tests_parser.add_argument(
        "-D",
        "--context-file-directory",
        help="Optional directory containing markdown files to add to the planner agent prompt (defaults to ~/.gai/projects/<PROJECT>/context/ where <PROJECT> is from workspace_name)",
    )

    # crs subcommand
    crs_parser = subparsers.add_parser(
        "crs",
        help="Address Critique change request comments on a CL",
    )
    crs_parser.add_argument(
        "-D",
        "--context-file-directory",
        help="Optional directory containing markdown files to add to the agent prompt (defaults to ~/.gai/projects/<PROJECT>/context/ where <PROJECT> is from workspace_name)",
    )

    # qa subcommand
    qa_parser = subparsers.add_parser(
        "qa",
        help="QA a CL for anti-patterns and suggest improvements",
    )
    qa_parser.add_argument(
        "-D",
        "--context-file-directory",
        help="Optional directory containing markdown files to add to the agent prompt (defaults to ~/.gai/projects/<PROJECT>/context/ where <PROJECT> is from workspace_name)",
    )

    # rerun subcommand (top-level, not under 'run')
    rerun_parser = top_level_subparsers.add_parser(
        "rerun",
        help="Continue a previous conversation with a gai agent",
    )
    rerun_parser.add_argument(
        "query",
        nargs="?",
        help="The query to send to the agent (required unless --list is specified)",
    )
    rerun_parser.add_argument(
        "history_file",
        nargs="?",
        help="Basename (e.g., 'foobar-run-251128104155') or full path to previous chat history (defaults to most recent)",
    )
    rerun_parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List all available chat history files",
    )

    # work subcommand (top-level, not under 'run')
    work_parser = top_level_subparsers.add_parser(
        "work",
        help="Interactively navigate through all ChangeSpecs in project files",
    )
    work_parser.add_argument(
        "-s",
        "--status",
        action="append",
        help="Filter by status (can be specified multiple times). Only ChangeSpecs matching ANY of these statuses will be included.",
    )
    work_parser.add_argument(
        "-p",
        "--project",
        action="append",
        help="Filter by project file basename (can be specified multiple times). Only ChangeSpecs from ANY of these project files will be included.",
    )
    work_parser.add_argument(
        "-m",
        "--model-size",
        choices=["big", "little"],
        help="Override model size for ALL GeminiCommandWrapper instances (big or little)",
    )
    work_parser.add_argument(
        "-r",
        "--refresh-interval",
        type=int,
        default=60,
        help="Auto-refresh interval in seconds (default: 60, 0 to disable)",
    )

    # loop subcommand (top-level, not under 'run')
    loop_parser = top_level_subparsers.add_parser(
        "loop",
        help="Continuously loop through all ChangeSpecs for status updates",
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
    loop_parser.add_argument(
        "--hook-interval",
        type=int,
        default=10,
        help="Hook check interval in seconds (default: 10)",
    )

    # commit subcommand (top-level, not under 'run')
    commit_parser = top_level_subparsers.add_parser(
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
    commit_parser.add_argument(
        "-b",
        "--bug",
        help="Bug number to include in the metadata tags. Defaults to output of 'branch_bug'.",
    )
    commit_parser.add_argument(
        "-p",
        "--project",
        help="Project name to prepend to the CL description. Defaults to output of 'workspace_name'.",
    )
    commit_parser.add_argument(
        "--chat",
        dest="chat_path",
        help="Path to the chat file associated with this commit (for HISTORY entry).",
    )
    commit_parser.add_argument(
        "--timestamp",
        help="Shared timestamp for synced chat/diff files (YYmmddHHMMSS format).",
    )
    commit_parser.add_argument(
        "-n",
        "--note",
        help="Custom note for the initial HISTORY entry (default: 'Initial Commit').",
    )

    # amend subcommand (top-level, not under 'run')
    amend_parser = top_level_subparsers.add_parser(
        "amend",
        help="Amend the current Mercurial commit with HISTORY tracking",
    )
    amend_parser.add_argument(
        "note",
        help='The note for this amend (e.g., "Fixed typo in README").',
    )
    amend_parser.add_argument(
        "--chat",
        dest="chat_path",
        help="Path to the chat file associated with this amend.",
    )
    amend_parser.add_argument(
        "--timestamp",
        help="Shared timestamp for synced chat/diff files (YYmmddHHMMSS format).",
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

    # accept subcommand (top-level, not under 'run')
    accept_parser = top_level_subparsers.add_parser(
        "accept",
        help="Accept a proposed HISTORY entry by applying its diff",
    )
    accept_parser.add_argument(
        "proposal",
        help="Proposal ID to accept (e.g., '2a').",
    )
    accept_parser.add_argument(
        "msg",
        nargs="?",
        default=None,
        help="Optional message to amend the commit message.",
    )
    accept_parser.add_argument(
        "--cl",
        dest="cl_name",
        help="CL name (defaults to current branch name).",
    )

    # revert subcommand (top-level, not under 'run')
    revert_parser = top_level_subparsers.add_parser(
        "revert",
        help="Revert a ChangeSpec by pruning its CL and archiving the diff",
    )
    revert_parser.add_argument(
        "name",
        help="NAME of the ChangeSpec to revert",
    )

    # restore subcommand (top-level, not under 'run')
    restore_parser = top_level_subparsers.add_parser(
        "restore",
        help="Restore a reverted ChangeSpec by re-applying its diff and creating a new CL",
    )
    restore_parser.add_argument(
        "name",
        nargs="?",
        help="NAME of the reverted ChangeSpec to restore (e.g., 'foobar_feature__2')",
    )
    restore_parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List all reverted ChangeSpecs",
    )

    # split subcommand (top-level, not under 'run')
    split_parser = top_level_subparsers.add_parser(
        "split",
        help="Split a CL into multiple smaller CLs based on a SplitSpec",
    )
    split_parser.add_argument(
        "name",
        nargs="?",
        help="NAME of the ChangeSpec to split (defaults to current branch name)",
    )
    split_parser.add_argument(
        "-s",
        "--spec",
        nargs="?",
        const="",  # Allows -s without argument
        help="Path to SplitSpec YAML file. If -s is provided without a path, opens editor to create one.",
    )

    return parser


def main() -> NoReturn:
    # Check for 'gai run <query>' before argparse processes it
    # This allows us to handle queries that contain spaces
    if len(sys.argv) >= 3 and sys.argv[1] == "run":
        potential_query = sys.argv[2]
        # Known workflow subcommands
        known_workflows = {
            "fix-tests",
            "crs",
            "qa",
        }
        # If the argument is not a known workflow and contains spaces, treat it as a query
        if potential_query not in known_workflows and " " in potential_query:
            # This is a query - run it through Gemini
            from gemini_wrapper import GeminiCommandWrapper
            from langchain_core.messages import HumanMessage
            from shared_utils import ensure_str_content

            # Claim workspace if in a recognized project
            project_file, workspace_num, _ = _get_project_file_and_workspace_num()
            if project_file and workspace_num:
                claim_workspace(project_file, workspace_num, "run", None)

            try:
                # Convert escaped newlines to actual newlines
                query = potential_query.replace("\\n", "\n")
                wrapper = GeminiCommandWrapper(model_size="big")
                wrapper.set_logging_context(agent_type="query", suppress_output=False)

                ai_result = wrapper.invoke([HumanMessage(content=query)])

                # Check for file modifications and prompt for action
                console = Console()
                target_dir = os.getcwd()

                # Generate timestamp for proposal before prompting
                from history_utils import generate_timestamp

                shared_timestamp = generate_timestamp()

                # Prepare and save chat history BEFORE prompting so we have chat_path
                rendered_query = process_xfile_references(query)
                response_content = ensure_str_content(ai_result.content)
                saved_path = save_chat_history(
                    prompt=rendered_query,
                    response=response_content,
                    workflow="run",
                    timestamp=shared_timestamp,
                )

                prompt_result = prompt_for_change_action(
                    console,
                    target_dir,
                    workflow_name="run",
                    chat_path=saved_path,
                    shared_timestamp=shared_timestamp,
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

            sys.exit(0)

    parser = _create_parser()
    args = parser.parse_args()

    workflow: BaseWorkflow

    # Handle 'work' command (top-level)
    if args.command == "work":
        workflow = WorkWorkflow(
            status_filters=args.status,
            project_filters=args.project,
            model_size_override=getattr(args, "model_size", None),
            refresh_interval=args.refresh_interval,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)

    # Handle 'loop' command (top-level)
    if args.command == "loop":
        from work.loop import LoopWorkflow

        loop_workflow = LoopWorkflow(
            interval_seconds=args.interval,
            verbose=args.verbose,
            hook_interval_seconds=args.hook_interval,
        )
        success = loop_workflow.run()
        sys.exit(0 if success else 1)

    # Handle 'commit' command (top-level)
    if args.command == "commit":
        workflow = CommitWorkflow(
            cl_name=args.cl_name,
            file_path=args.file_path,
            bug=args.bug,
            project=args.project,
            chat_path=args.chat_path,
            timestamp=args.timestamp,
            note=args.note,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)

    # Handle 'amend' command (top-level)
    if args.command == "amend":
        workflow = AmendWorkflow(
            note=args.note,
            chat_path=args.chat_path,
            timestamp=args.timestamp,
            propose=getattr(args, "propose", False),
            target_dir=getattr(args, "target_dir", None),
        )
        success = workflow.run()
        sys.exit(0 if success else 1)

    # Handle 'accept' command (top-level)
    if args.command == "accept":
        workflow = AcceptWorkflow(
            proposal=args.proposal,
            msg=args.msg,
            cl_name=args.cl_name,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)

    # Handle 'revert' command (top-level)
    if args.command == "revert":
        from work.changespec import find_all_changespecs
        from work.revert import revert_changespec

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

    # Handle 'restore' command (top-level)
    if args.command == "restore":
        from work.changespec import find_all_changespecs
        from work.restore import list_reverted_changespecs, restore_changespec

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
            console.print("[red]Error: name is required (unless using --list)[/red]")
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

    # Handle 'split' command (top-level)
    if args.command == "split":
        from split_workflow import SplitWorkflow

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
        )
        success = workflow.run()
        sys.exit(0 if success else 1)

    # Handle 'rerun' command (top-level)
    if args.command == "rerun":
        # Handle --list flag
        if args.list:
            histories = list_chat_histories()
            if not histories:
                print("No chat histories found.")
            else:
                print("Available chat histories:")
                for history in histories:
                    print(f"  {history}")
            sys.exit(0)

        # Validate required arguments when not using --list
        if not args.query:
            print("Error: query is required (unless using --list)")
            sys.exit(1)

        # Determine which history file to use
        history_file = args.history_file
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

        # Claim workspace if in a recognized project
        project_file, workspace_num, _ = _get_project_file_and_workspace_num()
        if project_file and workspace_num:
            claim_workspace(project_file, workspace_num, "rerun", None)

        try:
            # Build the full prompt with previous history
            from gemini_wrapper import GeminiCommandWrapper
            from langchain_core.messages import HumanMessage

            full_prompt = f"""# Previous Conversation

{previous_history}

---

# New Query

{args.query}"""

            # Convert escaped newlines to actual newlines
            full_prompt = full_prompt.replace("\\n", "\n")

            wrapper = GeminiCommandWrapper(model_size="big")
            wrapper.set_logging_context(agent_type="rerun", suppress_output=False)

            ai_result = wrapper.invoke([HumanMessage(content=full_prompt)])

            # Check for file modifications and prompt for action
            console = Console()
            target_dir = os.getcwd()

            # Generate timestamp for proposal
            from history_utils import generate_timestamp

            shared_timestamp = generate_timestamp()

            # Save chat history BEFORE prompting so we have chat_path
            # Process xfile references so no x:: patterns are saved
            from shared_utils import ensure_str_content

            rendered_query = process_xfile_references(args.query)
            response_content = ensure_str_content(ai_result.content)
            saved_path = save_chat_history(
                prompt=rendered_query,
                response=response_content,
                workflow="rerun",
                previous_history=previous_history,
                timestamp=shared_timestamp,
            )

            prompt_result = prompt_for_change_action(
                console,
                target_dir,
                workflow_name="rerun",
                chat_path=saved_path,
                shared_timestamp=shared_timestamp,
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
                        chat_path=saved_path,
                        shared_timestamp=shared_timestamp,
                    )

            print(f"\nChat history saved to: {saved_path}")
        finally:
            # Release workspace when done
            if project_file and workspace_num:
                release_workspace(project_file, workspace_num, "rerun", None)

        sys.exit(0)

    # Verify we're using the 'run' command
    if args.command != "run":
        print(f"Unknown command: {args.command}")
        sys.exit(1)

    if args.workflow == "fix-tests":
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
    elif args.workflow == "crs":
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
    else:
        print(f"Unknown workflow: {args.workflow}")
        sys.exit(1)


if __name__ == "__main__":
    main()
