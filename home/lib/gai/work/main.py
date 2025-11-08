"""Main workflow for the work subcommand."""

import os
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

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
            elif user_input == "q":
                self.console.print("[green]Exiting work workflow[/green]")
                return True
            else:
                self.console.print(f"[red]Invalid option: {user_input}[/red]")
                input("Press Enter to continue...")
