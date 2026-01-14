"""Argument parser creation for the GAI CLI tool."""

import argparse

from ace.saved_queries import load_last_query


def create_parser() -> argparse.ArgumentParser:
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

    # --- ace ---
    ace_parser = top_level_subparsers.add_parser(
        "ace",
        help="Interactively navigate through ChangeSpecs matching a query",
    )
    # Optional positional argument with default
    ace_parser.add_argument(
        "query",
        nargs="?",
        default=load_last_query() or "!!!",
        help="Query string for filtering ChangeSpecs (default: '!!!' for error suffixes). "
        'Examples: \'"feature" AND "Drafted"\', \'"myproject" OR "bugfix"\', '
        "'!!! AND @myproject'",
    )
    # Options for 'ace' (keep sorted alphabetically by long option name)
    ace_parser.add_argument(
        "-m",
        "--model-size",
        choices=["big", "little"],
        help="Override model size for ALL GeminiCommandWrapper instances (big or little)",
    )
    ace_parser.add_argument(
        "-r",
        "--refresh-interval",
        type=int,
        default=10,
        help="Auto-refresh interval in seconds (default: 10, 0 to disable)",
    )

    # --- amend ---
    amend_parser = top_level_subparsers.add_parser(
        "amend",
        help="Amend the current Mercurial commit with HISTORY tracking",
    )
    amend_parser.add_argument(
        "note",
        nargs="*",
        help='The note for this amend (e.g., "Fixed typo in README"). '
        "When using --accept, this should be proposal entries instead.",
    )
    # Options for 'amend' (keep sorted alphabetically by long option name)
    amend_parser.add_argument(
        "-a",
        "--accept",
        action="store_true",
        help="Accept one or more proposed HISTORY entries by applying their diffs. "
        "When used, positional args are proposal entries (format: <id>[(<msg>)]). "
        "Examples: '2a', '2b(Add foobar field)'.",
    )
    amend_parser.add_argument(
        "--chat",
        dest="chat_path",
        help="Path to the chat file associated with this amend.",
    )
    amend_parser.add_argument(
        "--cl",
        dest="cl_name",
        help="CL name (defaults to current branch name). Only used with --accept.",
    )
    amend_parser.add_argument(
        "-p",
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

    # --- commit ---
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
    # Options for 'commit' (keep sorted alphabetically by long option name)
    # Bug options are mutually exclusive - use either BUG= or FIXED= tag
    bug_group = commit_parser.add_mutually_exclusive_group()
    bug_group.add_argument(
        "-b",
        "--bug",
        help="Bug number for BUG= tag. Defaults to output of 'branch_bug'.",
    )
    bug_group.add_argument(
        "-B",
        "--fixed-bug",
        help="Bug number for FIXED= tag (bug is fixed by this CL).",
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
    commit_parser.add_argument(
        "--end-timestamp",
        dest="end_timestamp",
        help="End timestamp for duration calculation (YYmmdd_HHMMSS format).",
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
        default=1,
        help="Hook check interval in seconds (default: 1)",
    )
    loop_parser.add_argument(
        "-i",
        "--interval",
        type=int,
        default=300,
        help="Polling interval in seconds (default: 300 = 5 minutes)",
    )
    loop_parser.add_argument(
        "-r",
        "--max-runners",
        type=int,
        default=4,
        help="Maximum concurrent runners (hooks, agents, mentors) across all ChangeSpecs (default: 4)",
    )
    loop_parser.add_argument(
        "-q",
        "--query",
        default="",
        help="Query string for filtering ChangeSpecs (empty = all ChangeSpecs). "
        "Examples: '\"feature\" AND %%d', '+myproject', '!!! OR @@@'",
    )
    loop_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show skipped ChangeSpecs in output",
    )
    loop_parser.add_argument(
        "--zombie-timeout",
        type=int,
        default=7200,
        help="Zombie detection timeout in seconds (default: 7200 = 2 hours). "
        "Hooks and CRS workflows running longer than this are marked as ZOMBIE.",
    )

    # --- restore ---
    restore_parser = top_level_subparsers.add_parser(
        "restore",
        help="Restore a reverted ChangeSpec by re-applying its diff and creating a new CL",
    )
    restore_parser.add_argument(
        "name",
        nargs="?",
        help="NAME of the reverted ChangeSpec to restore (e.g., 'foobar_feature__2')",
    )
    # Options for 'restore' (keep sorted alphabetically by long option name)
    restore_parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List all reverted ChangeSpecs",
    )

    # --- search ---
    search_parser = top_level_subparsers.add_parser(
        "search",
        help="Search for ChangeSpecs matching a query and display them",
    )
    search_parser.add_argument(
        "query",
        help="Query string for filtering ChangeSpecs. "
        "Examples: '\"feature\" AND \"Drafted\"', '+myproject', '!!! OR @@@'",
    )
    # Options for 'search' (keep sorted alphabetically by long option name)
    search_parser.add_argument(
        "-f",
        "--format",
        choices=["plain", "rich"],
        default="rich",
        help="Output format: 'plain' for simple text, 'rich' for styled panels (default: rich)",
    )

    # --- revert ---
    revert_parser = top_level_subparsers.add_parser(
        "revert",
        help="Revert a ChangeSpec by pruning its CL and archiving the diff",
    )
    revert_parser.add_argument(
        "name",
        help="NAME of the ChangeSpec to revert",
    )

    # --- run ---
    run_parser = top_level_subparsers.add_parser(
        "run",
        help="Run a workflow or execute a query directly (e.g., 'gai run \"Your question here\"')",
    )

    # Options for 'run' (keep sorted alphabetically by long option name)
    run_parser.add_argument(
        "-a",
        "--accept",
        dest="accept_message",
        metavar="MSG",
        help="Auto-select 'a' (accept) option with MSG as the accept message. Skips the a/p/n/x prompt.",
    )
    run_parser.add_argument(
        "-c",
        "--commit",
        dest="commit_name",
        nargs=2,
        metavar=("NAME", "MSG"),
        help="Override auto-generated CL name and commit message with custom NAME and MSG values.",
    )
    run_parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List all available chat history files",
    )
    run_parser.add_argument(
        "-r",
        "--resume",
        dest="continue_history",
        nargs="?",
        const="",  # Empty string means "use most recent"
        help="Resume a previous conversation. Optionally specify history file basename or path (defaults to most recent).",
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

    # --- run fix-hook ---
    fix_hook_parser = subparsers.add_parser(
        "fix-hook",
        help="Fix a failing hook command using AI assistance",
    )
    fix_hook_parser.add_argument(
        "hook_output_file",
        help="Path to the file containing the hook command output",
    )
    fix_hook_parser.add_argument(
        "hook_command",
        help="The hook command string that is failing",
    )

    # --- run mentor ---
    mentor_parser = subparsers.add_parser(
        "mentor",
        help="Run a mentor agent on a CL to enforce specific coding standards",
    )
    mentor_parser.add_argument(
        "mentor_spec",
        help="Profile and mentor name in format 'profile:mentor' (e.g., 'code:comments')",
    )
    # Options for 'run mentor' (keep sorted alphabetically by long option name)
    mentor_parser.add_argument(
        "--cl",
        dest="cl_name",
        help="CL name to work on (defaults to output of 'branch_name' command)",
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

    # --- xprompt ---
    xprompt_parser = top_level_subparsers.add_parser(
        "xprompt",
        help="Expand gai references (snippets, file refs) in a prompt",
    )
    xprompt_parser.add_argument(
        "prompt",
        nargs="?",
        help="Prompt text to expand. If not provided, reads from STDIN.",
    )

    return parser
