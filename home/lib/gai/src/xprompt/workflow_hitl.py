"""CLI human-in-the-loop handler for workflow execution."""

import json
from typing import Any

from rich.console import Console
from rich.syntax import Syntax

from xprompt.workflow_executor import HITLResult


class CLIHITLHandler:
    """CLI handler for human-in-the-loop prompts during workflow execution."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize the CLI HITL handler.

        Args:
            console: Optional Rich console for output. Creates one if not provided.
        """
        self.console = console or Console()

    def prompt(
        self,
        step_name: str,
        step_type: str,
        output: Any,
    ) -> HITLResult:
        """Prompt the user for action on step output.

        Args:
            step_name: Name of the step being reviewed.
            step_type: Either "agent" or "bash".
            output: The step's output data.

        Returns:
            HITLResult indicating the user's decision.
        """
        # Display step info and output
        self.console.print()
        self.console.print(
            f"[bold cyan]Step '{step_name}' ({step_type}) completed.[/bold cyan]"
        )
        self.console.print("[dim]" + "─" * 60 + "[/dim]")

        # Format and display output
        if isinstance(output, dict):
            output_str = json.dumps(output, indent=2)
            syntax = Syntax(output_str, "json", theme="monokai", line_numbers=True)
            self.console.print(syntax)
        else:
            self.console.print(str(output))

        self.console.print("[dim]" + "─" * 60 + "[/dim]")

        # Show available actions based on step type
        self.console.print()
        self.console.print("[bold cyan]What would you like to do?[/bold cyan]")
        self.console.print("  [green]a[/green] - Accept and continue")

        if step_type == "agent":
            self.console.print("  [yellow]e[/yellow] - Edit the output")
            self.console.print("  [blue]<text>[/blue] - Provide feedback to regenerate")
        elif step_type == "bash":
            self.console.print("  [yellow]r[/yellow] - Re-run the command")

        self.console.print("  [red]x[/red] - Reject and abort workflow")
        self.console.print()

        # Get user input
        response = input("Choice: ").strip()

        if response.lower() == "a":
            return HITLResult(action="accept", approved=True)
        elif response.lower() == "x":
            return HITLResult(action="reject", approved=False)
        elif response.lower() == "e" and step_type == "agent":
            return HITLResult(action="edit")
        elif response.lower() == "r" and step_type == "bash":
            return HITLResult(action="rerun")
        elif response and step_type == "agent":
            # Treat any other input as feedback for regeneration
            return HITLResult(action="feedback", feedback=response)
        else:
            # Default to accept for empty input
            return HITLResult(action="accept", approved=True)
