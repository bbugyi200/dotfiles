"""Command handlers for CL-related operations."""

import argparse
import sys
from typing import NoReturn

from amend_workflow import AmendWorkflow
from commit_workflow import CommitWorkflow
from rich.console import Console


def handle_amend_command(args: argparse.Namespace) -> NoReturn:
    """Handle the 'amend' command.

    Args:
        args: Parsed command-line arguments.
    """
    from rich_utils import print_status

    # Handle --accept mode
    if getattr(args, "accept", False):
        from accept_workflow import AcceptWorkflow, parse_proposal_entries

        if not args.note:
            print_status("At least one proposal entry is required", "error")
            sys.exit(1)

        entries = parse_proposal_entries(args.note)
        if entries is None:
            print_status("Invalid proposal entry format", "error")
            sys.exit(1)

        accept_workflow = AcceptWorkflow(
            proposals=entries,
            cl_name=getattr(args, "cl_name", None),
        )
        success = accept_workflow.run()
        sys.exit(0 if success else 1)

    # Regular amend mode
    if not args.note:
        print_status("Note is required for amend", "error")
        sys.exit(1)

    if len(args.note) > 1:
        print_status(
            "Only one note is allowed for amend (use quotes for multi-word notes)",
            "error",
        )
        sys.exit(1)

    workflow = AmendWorkflow(
        note=args.note[0],
        chat_path=args.chat_path,
        timestamp=args.timestamp,
        propose=getattr(args, "propose", False),
        target_dir=getattr(args, "target_dir", None),
    )
    success = workflow.run()
    sys.exit(0 if success else 1)


def handle_commit_command(args: argparse.Namespace) -> NoReturn:
    """Handle the 'commit' command.

    Args:
        args: Parsed command-line arguments.
    """
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


def handle_restore_command(args: argparse.Namespace) -> NoReturn:
    """Handle the 'restore' command.

    Args:
        args: Parsed command-line arguments.
    """
    from ace.changespec import find_all_changespecs
    from ace.restore import list_reverted_changespecs, restore_changespec

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


def handle_revert_command(args: argparse.Namespace) -> NoReturn:
    """Handle the 'revert' command.

    Args:
        args: Parsed command-line arguments.
    """
    from ace.changespec import find_all_changespecs
    from ace.revert import revert_changespec

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
