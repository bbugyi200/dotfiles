"""Main entry point for the GAI CLI tool."""

import sys
from typing import NoReturn

from search import SearchWorkflow
from search.query import QueryParseError

from .cl_handler import handle_cl_command
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

    # --- cl ---
    if args.command == "cl":
        handle_cl_command(args)

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

    # Workflow handlers under 'run'
    handle_run_workflows(args)


if __name__ == "__main__":
    main()
