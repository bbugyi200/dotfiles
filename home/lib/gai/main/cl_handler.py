"""CL subcommand handlers for the GAI CLI tool."""

import argparse
import sys
from typing import NoReturn

from accept_workflow import AcceptWorkflow
from amend_workflow import AmendWorkflow
from commit_workflow import CommitWorkflow
from rich.console import Console


def handle_cl_command(args: argparse.Namespace) -> NoReturn:
    """Handle all CL subcommands.

    Args:
        args: Parsed command-line arguments.
    """
    # CL subcommand handlers (keep sorted alphabetically)

    # --- cl accept ---
    if args.cl_command == "accept":
        from accept_workflow import parse_proposal_entries
        from rich_utils import print_status

        entries = parse_proposal_entries(args.proposals)
        if entries is None:
            print_status("Invalid proposal entry format", "error")
            sys.exit(1)

        accept_workflow = AcceptWorkflow(
            proposals=entries,
            cl_name=args.cl_name,
        )
        success = accept_workflow.run()
        sys.exit(0 if success else 1)

    # --- cl amend ---
    if args.cl_command == "amend":
        amend_workflow = AmendWorkflow(
            note=args.note,
            chat_path=args.chat_path,
            timestamp=args.timestamp,
            propose=getattr(args, "propose", False),
            target_dir=getattr(args, "target_dir", None),
        )
        success = amend_workflow.run()
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

        commit_workflow = CommitWorkflow(
            cl_name=args.cl_name,
            file_path=args.file_path,
            bug=args.bug,
            project=args.project,
            chat_path=args.chat_path,
            timestamp=args.timestamp,
            note=args.note,
            message=args.message,
        )
        success = commit_workflow.run()
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

    # Unknown cl_command - should never happen due to argparse validation
    print(f"Unknown CL command: {args.cl_command}")
    sys.exit(1)
