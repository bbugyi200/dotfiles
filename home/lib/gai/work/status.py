"""Status-related operations for ChangeSpecs."""

import os
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from status_state_machine import VALID_STATUSES

# Status that requires additional input when selected
STATUS_FAILING_TESTS = "Failing Tests"

# Status that triggers revert workflow
STATUS_REVERTED = "Reverted"


def _get_available_statuses(current_status: str) -> list[str]:
    """Get list of available statuses for selection.

    Excludes:
    - Current status
    - Statuses ending with "..." (transient/automated states)

    Args:
        current_status: The current status value

    Returns:
        List of available status strings
    """
    return [
        status
        for status in VALID_STATUSES
        if status != current_status and not status.endswith("...")
    ]


def prompt_status_change(console: Console, current_status: str) -> str | None:
    """Prompt user to select a new status.

    Args:
        console: Rich Console object for output
        current_status: Current status value

    Returns:
        Selected status string, or None if cancelled
    """
    available_statuses = _get_available_statuses(current_status)

    if not available_statuses:
        console.print("[yellow]No available status changes[/yellow]")
        return None

    console.print("\n[bold cyan]Select new status:[/bold cyan]")
    for idx, status in enumerate(available_statuses, 1):
        console.print(f"  {idx}. {status}")
    console.print("  0. Cancel")

    console.print("\nEnter choice: ", end="")

    try:
        choice = input().strip()

        if choice == "0":
            return None

        choice_idx = int(choice)
        if 1 <= choice_idx <= len(available_statuses):
            return available_statuses[choice_idx - 1]
        else:
            console.print("[red]Invalid choice[/red]")
            return None
    except (ValueError, EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled[/yellow]")
        return None


def prompt_failing_test_targets(console: Console) -> list[str] | None:
    """Prompt user to enter failing test targets.

    Args:
        console: Rich Console object for output

    Returns:
        List of test target strings, or None if cancelled
    """
    console.print(
        "\n[bold cyan]Enter failing test targets (whitespace-separated):[/bold cyan]"
    )
    console.print("[dim]Example: //foo:bar //baz:qux[/dim]")
    console.print("Enter targets: ", end="")

    try:
        user_input = input().strip()

        if not user_input:
            console.print("[yellow]No targets entered, cancelled[/yellow]")
            return None

        # Split by whitespace to get individual targets
        targets = user_input.split()

        if not targets:
            console.print("[yellow]No valid targets entered, cancelled[/yellow]")
            return None

        return targets
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled[/yellow]")
        return None
