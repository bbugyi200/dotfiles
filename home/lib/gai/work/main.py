"""Main workflow for the work subcommand."""

import os
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from status_state_machine import VALID_STATUSES, transition_changespec_status
from workflow_base import BaseWorkflow

from .changespec import display_changespec, find_all_changespecs


class WorkWorkflow(BaseWorkflow):
    """Interactive workflow for navigating through ChangeSpecs."""

    def __init__(self) -> None:
        """Initialize the work workflow."""
        self.console = Console()

    @property
    def name(self) -> str:
        """Return the name of this workflow."""
        return "work"

    @property
    def description(self) -> str:
        """Return a description of what this workflow does."""
        return "Interactively navigate through all ChangeSpecs in project files"

    def _get_available_statuses(self, current_status: str) -> list[str]:
        """Get list of available statuses for selection.

        Excludes:
        - Current status
        - "Blocked" status

        Args:
            current_status: The current status value

        Returns:
            List of available status strings
        """
        return [
            status
            for status in VALID_STATUSES
            if status != current_status and status != "Blocked"
        ]

    def _prompt_status_change(self, current_status: str) -> str | None:
        """Prompt user to select a new status.

        Args:
            current_status: Current status value

        Returns:
            Selected status string, or None if cancelled
        """
        available_statuses = self._get_available_statuses(current_status)

        if not available_statuses:
            self.console.print("[yellow]No available status changes[/yellow]")
            input("Press Enter to continue...")
            return None

        self.console.print("\n[bold cyan]Select new status:[/bold cyan]")
        for idx, status in enumerate(available_statuses, 1):
            self.console.print(f"  {idx}. {status}")
        self.console.print("  0. Cancel")

        self.console.print("\nEnter choice: ", end="")

        try:
            choice = input().strip()

            if choice == "0":
                return None

            choice_idx = int(choice)
            if 1 <= choice_idx <= len(available_statuses):
                return available_statuses[choice_idx - 1]
            else:
                self.console.print("[red]Invalid choice[/red]")
                input("Press Enter to continue...")
                return None
        except (ValueError, EOFError, KeyboardInterrupt):
            self.console.print("\n[yellow]Cancelled[/yellow]")
            input("Press Enter to continue...")
            return None

    def run(self) -> bool:
        """Run the interactive ChangeSpec navigation workflow.

        Returns:
            True if workflow completed successfully, False otherwise
        """
        # Find all ChangeSpecs
        changespecs = find_all_changespecs()

        if not changespecs:
            self.console.print(
                "[yellow]No ChangeSpecs found in ~/.gai/projects/*.md files[/yellow]"
            )
            return True

        self.console.print(
            f"[bold green]Found {len(changespecs)} ChangeSpec(s)[/bold green]\n"
        )

        # Interactive navigation
        current_idx = 0

        while True:
            # Display current ChangeSpec
            changespec = changespecs[current_idx]
            self.console.clear()
            self.console.print(
                f"[bold]ChangeSpec {current_idx + 1} of {len(changespecs)}[/bold]\n"
            )
            display_changespec(changespec, self.console)

            # Show navigation prompt
            self.console.print()
            options = []
            if current_idx > 0:
                options.append("[cyan]p[/cyan] (prev)")
            if current_idx < len(changespecs) - 1:
                options.append("[cyan]n[/cyan] (next)")
            # Only show status change option if not blocked
            if changespec.status != "Blocked":
                options.append("[cyan]s[/cyan] (status)")
            options.append("[cyan]q[/cyan] (quit)")

            prompt_text = " | ".join(options) + ": "
            self.console.print(prompt_text, end="")

            # Get user input
            try:
                user_input = input().strip().lower()
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[yellow]Aborted[/yellow]")
                return True

            # Process input
            if user_input == "n":
                if current_idx < len(changespecs) - 1:
                    current_idx += 1
                else:
                    self.console.print("[yellow]Already at last ChangeSpec[/yellow]")
                    input("Press Enter to continue...")
            elif user_input == "p":
                if current_idx > 0:
                    current_idx -= 1
                else:
                    self.console.print("[yellow]Already at first ChangeSpec[/yellow]")
                    input("Press Enter to continue...")
            elif user_input == "s":
                # Handle status change
                if changespec.status == "Blocked":
                    self.console.print(
                        "[yellow]Cannot change status of blocked ChangeSpec[/yellow]"
                    )
                    input("Press Enter to continue...")
                else:
                    new_status = self._prompt_status_change(changespec.status)
                    if new_status:
                        # Update the status in the project file
                        success, old_status, error_msg = transition_changespec_status(
                            changespec.file_path,
                            changespec.name,
                            new_status,
                            validate=False,  # Don't validate - allow any transition
                        )
                        if success:
                            self.console.print(
                                f"[green]Status updated: {old_status} → {new_status}[/green]"
                            )
                            # Reload changespecs to reflect the update
                            changespecs = find_all_changespecs()
                            # Try to stay on the same changespec by name
                            for idx, cs in enumerate(changespecs):
                                if cs.name == changespec.name:
                                    current_idx = idx
                                    break
                        else:
                            self.console.print(f"[red]Error: {error_msg}[/red]")
                        input("Press Enter to continue...")
            elif user_input == "q":
                self.console.print("[green]Exiting work workflow[/green]")
                return True
            else:
                self.console.print(f"[red]Invalid option: {user_input}[/red]")
                input("Press Enter to continue...")
