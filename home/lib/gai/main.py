import argparse
import os
import sys
from typing import NoReturn

from chat_history import list_chat_histories, load_chat_history, save_chat_history
from create_project_workflow import CreateProjectWorkflow
from crs_workflow import CrsWorkflow
from fix_tests_workflow.main import FixTestsWorkflow
from new_ez_feature_workflow.main import NewEzFeatureWorkflow
from new_failing_tests_workflow.main import NewFailingTestWorkflow
from new_tdd_feature_workflow.main import NewTddFeatureWorkflow
from qa_workflow import QaWorkflow
from shared_utils import run_shell_command
from work import WorkWorkflow
from workflow_base import BaseWorkflow


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

    # create-project subcommand
    create_project_parser = subparsers.add_parser(
        "create-project",
        help="Create a project plan with proposed CLs based on design documents and prior work",
    )
    create_project_parser.add_argument(
        "bug_id",
        help="Bug ID to track this project (can be plain ID like '12345' or URL like 'http://b/12345'; will be written as URL)",
    )
    create_project_parser.add_argument(
        "clquery", help="Critique query for clsurf to analyze prior work"
    )
    create_project_parser.add_argument(
        "design_docs_dir",
        help="Directory containing markdown design documents",
    )
    create_project_parser.add_argument(
        "filename",
        help="Filename (basename only, without .gp extension) for the project. File will be created at ~/.gai/projects/<filename>/<filename>.gp. This will also be used as the NAME field in all ChangeSpecs.",
    )
    create_project_parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="Print the project file contents to STDOUT instead of writing to ~/.gai/projects/<project>/<project>.gp",
    )

    # new-failing-tests subcommand
    new_failing_tests_parser = subparsers.add_parser(
        "new-failing-tests",
        help="Add failing tests using TDD - adds failing tests before implementing the feature",
    )
    new_failing_tests_parser.add_argument(
        "-P",
        "--project-name",
        help="Name of the project (defaults to output of workspace_name command)",
    )
    new_failing_tests_parser.add_argument(
        "-D",
        "--context-file-directory",
        help="Optional file or directory containing markdown context (defaults to ~/.gai/projects/<PROJECT>/context/ where <PROJECT> is from -P option)",
    )
    new_failing_tests_parser.add_argument(
        "-g",
        "--guidance",
        help="Optional guidance text to append to the agent prompt (will be placed after 'TEST CASE GUIDANCE: ')",
    )

    # new-tdd-feature subcommand
    new_tdd_feature_parser = subparsers.add_parser(
        "new-tdd-feature",
        help="Implement new features using TDD based on failing tests created by new-failing-tests workflow",
    )
    new_tdd_feature_parser.add_argument(
        "test_output_file",
        help="Path to the test output file from new-failing-tests workflow (must contain 'Test command:' line)",
    )
    new_tdd_feature_parser.add_argument(
        "-u",
        "--user-instructions-file",
        help="Optional path to a file containing additional instructions for the implementation",
    )
    new_tdd_feature_parser.add_argument(
        "-m",
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum number of implementation iterations before giving up (default: 10)",
    )
    new_tdd_feature_parser.add_argument(
        "-D",
        "--context-file-directory",
        help="Optional directory containing markdown files to add to the agent prompt (defaults to ~/.gai/projects/<PROJECT>/context/ where <PROJECT> is from workspace_name)",
    )

    # new-ez-feature subcommand
    new_ez_feature_parser = subparsers.add_parser(
        "new-ez-feature",
        help="Implement simple changes that do not require tests",
    )
    new_ez_feature_parser.add_argument(
        "project_name",
        help="Name of the project (used for context)",
    )
    new_ez_feature_parser.add_argument(
        "design_docs_dir",
        help="Directory containing markdown design documents",
    )
    new_ez_feature_parser.add_argument(
        "-D",
        "--context-file-directory",
        help="Optional directory containing markdown files to add to the agent prompt (defaults to ~/.gai/projects/<PROJECT>/context/ where <PROJECT> is from workspace_name)",
    )
    new_ez_feature_parser.add_argument(
        "-g",
        "--guidance",
        help="Optional guidance text to append to the agent prompt (will be placed after 'IMPLEMENTATION GUIDANCE: ')",
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

    return parser


def main() -> NoReturn:
    # Check for 'gai run <query>' before argparse processes it
    # This allows us to handle queries that contain spaces
    if len(sys.argv) >= 3 and sys.argv[1] == "run":
        potential_query = sys.argv[2]
        # Known workflow subcommands
        known_workflows = {
            "fix-tests",
            "create-project",
            "new-failing-tests",
            "new-tdd-feature",
            "new-ez-feature",
            "crs",
            "qa",
        }
        # If the argument is not a known workflow and contains spaces, treat it as a query
        if potential_query not in known_workflows and " " in potential_query:
            # This is a query - run it through Gemini
            from gemini_wrapper import GeminiCommandWrapper
            from langchain_core.messages import HumanMessage
            from shared_utils import ensure_str_content

            # Convert escaped newlines to actual newlines
            query = potential_query.replace("\\n", "\n")
            wrapper = GeminiCommandWrapper(model_size="big")
            wrapper.set_logging_context(agent_type="query", suppress_output=False)

            ai_result = wrapper.invoke([HumanMessage(content=query)])

            # Save the conversation history for potential future reruns
            response_content = ensure_str_content(ai_result.content)
            saved_path = save_chat_history(
                prompt=query,
                response=response_content,
                workflow="run",
            )
            print(f"\nChat history saved to: {saved_path}")

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

        # Save the conversation history for potential future reruns
        from shared_utils import ensure_str_content

        response_content = ensure_str_content(ai_result.content)
        saved_path = save_chat_history(
            prompt=args.query,
            response=response_content,
            workflow="rerun",
            previous_history=previous_history,
        )
        print(f"\nChat history saved to: {saved_path}")

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
    elif args.workflow == "create-project":
        workflow = CreateProjectWorkflow(
            args.bug_id,
            args.clquery,
            args.design_docs_dir,
            args.filename,
            dry_run=args.dry_run,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "new-failing-tests":
        # Read ChangeSpec from STDIN
        changespec_text = sys.stdin.read()
        if not changespec_text.strip():
            print("Error: No ChangeSpec provided on STDIN")
            sys.exit(1)

        # Determine project_name (default to workspace_name if not provided)
        project_name = args.project_name
        if not project_name:
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

        workflow = NewFailingTestWorkflow(
            project_name=project_name,
            changespec_text=changespec_text,
            test_targets=[],
            context_file_directory=context_file_directory,
            guidance=getattr(args, "guidance", None),
        )
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "new-tdd-feature":
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

        workflow = NewTddFeatureWorkflow(
            test_output_file=args.test_output_file,
            user_instructions_file=args.user_instructions_file,
            max_iterations=args.max_iterations,
            context_file_directory=context_file_directory,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "new-ez-feature":
        # Read ChangeSpec from STDIN
        changespec_text = sys.stdin.read()
        if not changespec_text.strip():
            print("Error: No ChangeSpec provided on STDIN")
            sys.exit(1)

        # Determine context_file_directory (default to ~/.gai/projects/<project>/context/)
        context_file_directory = args.context_file_directory
        if not context_file_directory:
            context_file_directory = os.path.expanduser(
                f"~/.gai/projects/{args.project_name}/context/"
            )

        workflow = NewEzFeatureWorkflow(
            project_name=args.project_name,
            design_docs_dir=args.design_docs_dir,
            changespec_text=changespec_text,
            context_file_directory=context_file_directory,
            guidance=getattr(args, "guidance", None),
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
