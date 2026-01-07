"""Run command handlers for the GAI CLI tool."""

import argparse
import os
import subprocess
import sys
import tempfile
from typing import NoReturn

from change_actions import (
    execute_change_action,
    prompt_for_change_action,
)
from chat_history import list_chat_histories, load_chat_history, save_chat_history
from crs_workflow import CrsWorkflow
from fix_tests_workflow.main import FixTestsWorkflow
from gemini_wrapper import process_xfile_references
from mentor_workflow import MentorWorkflow
from rich.console import Console
from running_field import claim_workspace, release_workspace
from shared_utils import (
    generate_workflow_tag,
    run_shell_command,
)
from workflow_base import BaseWorkflow

from .utils import get_project_file_and_workspace_num


def _get_editor() -> str:
    """Get the editor to use for prompts.

    Returns:
        The editor command to use. Checks $EDITOR first, then falls back to
        nvim if available, otherwise vim.
    """
    editor = os.environ.get("EDITOR")
    if editor:
        return editor

    # Fall back to nvim if it exists
    try:
        result = subprocess.run(
            ["which", "nvim"], capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            return "nvim"
    except Exception:
        pass

    return "vim"


def _open_editor_for_prompt() -> str | None:
    """Open the user's editor with a blank file for writing a prompt.

    Returns:
        The prompt content, or None if the user didn't write anything
        or the editor failed.
    """
    fd, temp_path = tempfile.mkstemp(suffix=".md", prefix="gai_prompt_")
    os.close(fd)

    editor = _get_editor()

    try:
        result = subprocess.run([editor, temp_path], check=False)
        if result.returncode != 0:
            print("Editor exited with non-zero status.")
            os.unlink(temp_path)
            return None

        with open(temp_path, encoding="utf-8") as f:
            content = f.read().strip()

        os.unlink(temp_path)

        if not content:
            return None

        return content

    except Exception as e:
        print(f"Failed to open editor: {e}")
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        return None


def _open_editor_with_content(initial_content: str) -> str | None:
    """Open the user's editor with pre-filled content for editing.

    Args:
        initial_content: The content to pre-fill in the editor.

    Returns:
        The edited content, or None if the user left it empty or the editor failed.
    """
    fd, temp_path = tempfile.mkstemp(suffix=".md", prefix="gai_prompt_")

    # Write initial content to temp file
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(initial_content)

    editor = _get_editor()

    try:
        result = subprocess.run([editor, temp_path], check=False)
        if result.returncode != 0:
            print("Editor exited with non-zero status.")
            os.unlink(temp_path)
            return None

        with open(temp_path, encoding="utf-8") as f:
            content = f.read().strip()

        os.unlink(temp_path)

        if not content:
            return None

        return content

    except Exception as e:
        print(f"Failed to open editor: {e}")
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        return None


def _show_prompt_history_picker() -> str | None:
    """Show fzf picker for prompt history, open editor, return edited prompt.

    Returns:
        The edited prompt content, or None if cancelled or no history.
    """
    from prompt_history import get_prompts_for_fzf

    items = get_prompts_for_fzf()

    if not items:
        print("No prompt history found. Run 'gai run \"your prompt\"' first.")
        return None

    # Check if fzf is available
    fzf_check = subprocess.run(
        ["which", "fzf"], capture_output=True, text=True, check=False
    )
    if fzf_check.returncode != 0:
        print("Error: fzf is not installed. Please install fzf to use prompt history.")
        return None

    # Build display lines for fzf
    display_lines = "\n".join(display for display, _ in items)

    # Run fzf
    cmd = [
        "fzf",
        "--prompt",
        "Select prompt> ",
        "--header",
        "* = current branch/workspace",
    ]

    result = subprocess.run(
        cmd,
        input=display_lines,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        # User cancelled (Escape or Ctrl-C)
        return None

    selected_display = result.stdout.strip()
    if not selected_display:
        return None

    # Find the matching entry
    selected_entry = None
    for display, entry in items:
        if display == selected_display:
            selected_entry = entry
            break

    if selected_entry is None:
        return None

    # Open editor with selected prompt pre-filled
    return _open_editor_with_content(selected_entry.text)


def _run_query(
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
    from commit_utils import generate_timestamp
    from gemini_wrapper import GeminiCommandWrapper
    from langchain_core.messages import HumanMessage
    from shared_utils import ensure_str_content

    # Claim workspace if in a recognized project
    project_file, workspace_num, _ = get_project_file_and_workspace_num()
    if project_file and workspace_num:
        claim_workspace(project_file, workspace_num, "run", None)

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

        wrapper = GeminiCommandWrapper(model_size="big")
        agent_type = "run" if previous_history is None else "run-continue"
        wrapper.set_logging_context(agent_type=agent_type, suppress_output=False)

        # Capture start timestamp for accurate duration calculation
        shared_timestamp = generate_timestamp()

        ai_result = wrapper.invoke([HumanMessage(content=full_prompt)])

        # Check for file modifications and prompt for action
        console = Console()
        target_dir = os.getcwd()

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
            accept_message=accept_message,
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


def _handle_run_with_resume(
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

    _run_query(
        query,
        previous_history,
        accept_message=accept_message,
        commit_name=commit_name,
        commit_message=commit_message,
    )
    sys.exit(0)


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
        prompt = _show_prompt_history_picker()
        if prompt is None:
            print("No prompt selected. Aborting.")
            sys.exit(1)
        _run_query(prompt)
        sys.exit(0)

    # Handle no arguments - open editor for prompt
    if not args_after_run:
        prompt = _open_editor_for_prompt()
        if prompt is None:
            print("No prompt provided. Aborting.")
            sys.exit(1)
        _run_query(prompt)
        sys.exit(0)

    # Handle -r/--resume flag
    if args_after_run and args_after_run[0] in ("-r", "--resume"):
        _handle_run_with_resume(args_after_run)
        # _handle_run_with_resume calls sys.exit, but just in case:
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
        _run_query(
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
            "fix-tests",
            "mentor",
            "split",
            "summarize",
        }
        if potential_query not in known_workflows and " " in potential_query:
            _run_query(potential_query)
            sys.exit(0)

    # No special case handled
    return False


def handle_run_workflows(args: argparse.Namespace) -> NoReturn:
    """Handle run workflow subcommands.

    Args:
        args: Parsed command-line arguments.
    """
    workflow: BaseWorkflow

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
    elif args.workflow == "fix-hook":
        from fix_hook_workflow import FixHookWorkflow

        workflow = FixHookWorkflow(
            hook_output_file=args.hook_output_file,
            hook_command=args.hook_command,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "mentor":
        workflow = MentorWorkflow(
            mentor_name=args.mentor_name,
            cl_name=args.cl_name,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "split":
        from ace.split_workflow import SplitWorkflow

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
