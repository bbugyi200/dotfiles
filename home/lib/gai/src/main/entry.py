"""Main entry point for the GAI CLI tool."""

import sys
from typing import NoReturn

from ace.query import QueryParseError

from .cl_handler import (
    handle_amend_command,
    handle_commit_command,
    handle_restore_command,
    handle_revert_command,
)
from .parser import create_parser
from .query_handler import handle_run_special_cases, handle_run_workflows


def main() -> NoReturn:
    """Main entry point for the GAI CLI tool."""
    # Check for 'gai run' special cases before argparse processes it
    # This allows us to handle queries that contain spaces
    if len(sys.argv) >= 2 and sys.argv[1] == "run":
        args_after_run = sys.argv[2:]
        handle_run_special_cases(args_after_run)
        # If we get here, no special case was handled, continue to argparse

    parser = create_parser()
    args = parser.parse_args()

    # =========================================================================
    # COMMAND HANDLERS (keep sorted alphabetically to match parser order)
    # =========================================================================

    # --- amend ---
    if args.command == "amend":
        handle_amend_command(args)

    # --- commit ---
    if args.command == "commit":
        handle_commit_command(args)

    # --- loop ---
    if args.command == "loop":
        from ace.loop import LoopWorkflow

        try:
            loop_workflow = LoopWorkflow(
                interval_seconds=args.interval,
                verbose=args.verbose,
                hook_interval_seconds=args.hook_interval,
                zombie_timeout_seconds=args.zombie_timeout,
                max_runners=args.max_runners,
                query=args.query,
            )
        except QueryParseError as e:
            print(f"Error: Invalid query: {e}")
            sys.exit(1)
        success = loop_workflow.run()
        sys.exit(0 if success else 1)

    # --- restore ---
    if args.command == "restore":
        handle_restore_command(args)

    # --- search ---
    if args.command == "search":
        from pathlib import Path

        from ace.changespec import find_all_changespecs
        from ace.display import display_changespec
        from ace.query import evaluate_query, parse_query
        from rich.console import Console

        try:
            parsed_query = parse_query(args.query)
        except QueryParseError as e:
            print(f"Error: Invalid query: {e}")
            sys.exit(1)

        all_changespecs = find_all_changespecs()
        matching = [
            cs
            for cs in all_changespecs
            if evaluate_query(parsed_query, cs, all_changespecs)
        ]

        if not matching:
            print("No ChangeSpecs match the query.")
            sys.exit(0)

        if args.format == "rich":
            console = Console()
            for cs in matching:
                display_changespec(cs, console)
        else:
            # Plain format: NAME [STATUS] - file_path:line_number
            for cs in matching:
                file_path = cs.file_path.replace(str(Path.home()), "~")
                print(f"{cs.name} [{cs.status}] - {file_path}:{cs.line_number}")

        sys.exit(0)

    # --- revert ---
    if args.command == "revert":
        handle_revert_command(args)

    # --- ace ---
    if args.command == "ace":
        from ace.tui import AceApp

        try:
            app = AceApp(
                query=args.query,
                model_size_override=getattr(args, "model_size", None),
                refresh_interval=args.refresh_interval,
            )
        except QueryParseError as e:
            print(f"Error: Invalid query: {e}")
            sys.exit(1)
        app.run()
        sys.exit(0)

    # --- xprompt ---
    if args.command == "xprompt":
        from gemini_wrapper import (
            format_with_prettier,
            process_command_substitution,
            process_snippet_references,
            process_xcmd_references,
            validate_file_references,
        )

        prompt = args.prompt if args.prompt else sys.stdin.read()
        prompt = process_snippet_references(prompt)
        prompt = process_command_substitution(prompt)
        prompt = process_xcmd_references(prompt)
        validate_file_references(prompt)  # Validates but doesn't modify
        print(format_with_prettier(prompt), end="")
        sys.exit(0)

    # --- run workflows ---
    if args.command != "run":
        print(f"Unknown command: {args.command}")
        sys.exit(1)

    # Workflow handlers under 'run'
    handle_run_workflows(args)


if __name__ == "__main__":
    main()
