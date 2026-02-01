"""CLI human-in-the-loop handler for workflow execution."""

import os
import subprocess
import tempfile
from typing import Any

import yaml  # type: ignore[import-untyped]
from rich.console import Console
from rich.syntax import Syntax
from shared_utils import dump_yaml

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
            # Unwrap _data if present for cleaner display
            display_data = output.get("_data", output)
            output_str = dump_yaml(display_data, sort_keys=False)
            syntax = Syntax(output_str, "yaml", theme="monokai", line_numbers=True)
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
            edited_output = self._edit_output(output)
            if edited_output is not None:
                return HITLResult(action="edit", edited_output=edited_output)
            else:
                # User cancelled edit, treat as reject
                return HITLResult(action="reject")
        elif response.lower() == "r" and step_type == "bash":
            return HITLResult(action="rerun")
        elif response and step_type == "agent":
            # Treat any other input as feedback for regeneration
            return HITLResult(action="feedback", feedback=response)
        else:
            # Default to accept for empty input
            return HITLResult(action="accept", approved=True)

    def _edit_output(self, output: Any) -> Any | None:
        """Open output in editor for user modification.

        Args:
            output: The output dict to edit.

        Returns:
            Edited output as dict, or None if cancelled.
        """
        # Unwrap _data if present
        data = output.get("_data", output) if isinstance(output, dict) else output

        # Convert to YAML
        yaml_content = dump_yaml(data, sort_keys=False)

        # Create temp file
        fd, temp_path = tempfile.mkstemp(suffix=".yml", prefix="workflow_edit_")
        os.close(fd)

        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)

        # Open in editor
        editor = os.environ.get("EDITOR", "nvim")
        subprocess.run([editor, temp_path], check=False)

        # Read edited content
        with open(temp_path, encoding="utf-8") as f:
            edited_content = f.read()

        os.unlink(temp_path)

        if not edited_content.strip():
            return None

        # Parse YAML back to dict/list
        try:
            edited_data = yaml.safe_load(edited_content)
            # Re-wrap in _data if original was wrapped
            if isinstance(output, dict) and "_data" in output:
                return {"_data": edited_data}
            return edited_data
        except yaml.YAMLError as e:
            self.console.print(f"[red]Invalid YAML: {e}[/red]")
            return None
