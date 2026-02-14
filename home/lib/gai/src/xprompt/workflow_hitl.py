"""CLI human-in-the-loop handler for workflow execution."""

import json
import os
import subprocess
import tempfile
import time
from typing import Any

import yaml  # type: ignore[import-untyped]
from rich.console import Console
from rich.syntax import Syntax
from shared_utils import dump_yaml

from xprompt.workflow_executor_types import HITLResult

_EXTENSION_TO_LEXER: dict[str, str] = {
    ".diff": "diff",
    ".patch": "diff",
    ".py": "python",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".sh": "bash",
    ".bash": "bash",
    ".js": "javascript",
    ".ts": "typescript",
    ".md": "markdown",
    ".toml": "toml",
    ".xml": "xml",
    ".html": "html",
    ".css": "css",
}

# Poll interval for TUI HITL handler (seconds)
_TUI_HITL_POLL_INTERVAL = 0.5
# Timeout for TUI HITL handler (seconds) - 1 hour
_TUI_HITL_TIMEOUT = 3600


class TUIHITLHandler:
    """HITL handler for TUI contexts that uses file-based communication.

    This handler writes a request file and blocks waiting for a response file,
    allowing the TUI to present the HITL options to the user asynchronously.
    """

    def __init__(self, artifacts_dir: str) -> None:
        """Initialize the TUI HITL handler.

        Args:
            artifacts_dir: Directory for workflow artifacts where HITL files are written.
        """
        self.artifacts_dir = artifacts_dir

    def prompt(
        self,
        step_name: str,
        step_type: str,
        output: Any,
        *,
        has_output: bool = False,
        output_types: dict[str, str] | None = None,
    ) -> HITLResult:
        """Write HITL request and block waiting for response.

        Args:
            step_name: Name of the step being reviewed.
            step_type: Either "prompt" or "bash".
            output: The step's output data.
            has_output: Whether the step has an output field defined.
            output_types: Mapping of field names to their types (e.g. "path").

        Returns:
            HITLResult based on the user's response from the TUI.
        """
        request_path = os.path.join(self.artifacts_dir, "hitl_request.json")
        response_path = os.path.join(self.artifacts_dir, "hitl_response.json")

        # Clean up any stale response file
        if os.path.exists(response_path):
            os.unlink(response_path)

        # Write the request file
        request_data: dict[str, Any] = {
            "step_name": step_name,
            "step_type": step_type,
            "output": output,
            "has_output": has_output,
        }
        if output_types is not None:
            request_data["output_types"] = output_types
        with open(request_path, "w", encoding="utf-8") as f:
            json.dump(request_data, f, indent=2, default=str)

        # Poll for response file
        start_time = time.time()
        while time.time() - start_time < _TUI_HITL_TIMEOUT:
            if os.path.exists(response_path):
                try:
                    with open(response_path, encoding="utf-8") as f:
                        response_data = json.load(f)

                    # Clean up request file after reading response
                    if os.path.exists(request_path):
                        os.unlink(request_path)
                    os.unlink(response_path)

                    # Parse response into HITLResult
                    action = response_data.get("action", "reject")
                    if action == "accept":
                        return HITLResult(action="accept", approved=True)
                    elif action == "reject":
                        return HITLResult(action="reject", approved=False)
                    elif action == "edit":
                        edited_output = response_data.get("edited_output")
                        return HITLResult(action="edit", edited_output=edited_output)
                    elif action == "feedback":
                        feedback = response_data.get("feedback", "")
                        return HITLResult(action="feedback", feedback=feedback)
                    elif action == "rerun":
                        return HITLResult(action="rerun")
                    else:
                        return HITLResult(action="reject", approved=False)
                except (json.JSONDecodeError, OSError):
                    # Response file exists but couldn't be read, wait and retry
                    pass

            time.sleep(_TUI_HITL_POLL_INTERVAL)

        # Timeout - clean up and reject
        if os.path.exists(request_path):
            os.unlink(request_path)
        return HITLResult(action="reject", approved=False)


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
        *,
        has_output: bool = False,
        output_types: dict[str, str] | None = None,
    ) -> HITLResult:
        """Prompt the user for action on step output.

        Args:
            step_name: Name of the step being reviewed.
            step_type: Either "prompt" or "bash".
            output: The step's output data.
            has_output: Whether the step has an output field defined.
            output_types: Mapping of field names to their types (e.g. "path").

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

        # Display file contents for path-typed output fields
        if output_types and isinstance(output, dict):
            for field_name, field_type in output_types.items():
                if field_type == "path":
                    path_value = output.get(field_name)
                    if path_value and os.path.isfile(str(path_value)):
                        self._display_path_file(str(path_value), field_name)

        self.console.print("[dim]" + "─" * 60 + "[/dim]")

        # Show available actions based on step type
        self.console.print()
        self.console.print("[bold cyan]What would you like to do?[/bold cyan]")
        self.console.print("  [green]a[/green] - Accept and continue")

        # Edit option available for prompt steps, or bash/python with output field
        can_edit = step_type == "prompt" or (
            step_type in ("bash", "python") and has_output
        )
        if can_edit:
            self.console.print("  [yellow]e[/yellow] - Edit the output")

        if step_type == "prompt":
            self.console.print("  [blue]<text>[/blue] - Provide feedback to regenerate")
        elif step_type in ("bash", "python"):
            self.console.print("  [yellow]r[/yellow] - Re-run the command")

        self.console.print("  [red]x[/red] - Reject and abort workflow")
        self.console.print()

        # Get user input
        response = input("Choice: ").strip()

        if response.lower() == "a":
            return HITLResult(action="accept", approved=True)
        elif response.lower() == "x":
            return HITLResult(action="reject", approved=False)
        elif response.lower() == "e" and can_edit:
            edited_output = self._edit_output(output)
            if edited_output is not None:
                return HITLResult(action="edit", edited_output=edited_output)
            else:
                # User cancelled edit, treat as reject
                return HITLResult(action="reject")
        elif response.lower() == "r" and step_type in ("bash", "python"):
            return HITLResult(action="rerun")
        elif response and step_type == "prompt":
            # Treat any other input as feedback for regeneration
            return HITLResult(action="feedback", feedback=response)
        else:
            # Default to accept for empty input
            return HITLResult(action="accept", approved=True)

    def _display_path_file(self, file_path: str, field_name: str) -> None:
        """Display the contents of a path-typed output file with syntax highlighting.

        Args:
            file_path: Path to the file to display.
            field_name: Name of the output field (for the header).
        """
        self.console.print()
        self.console.print(
            f"[bold green]File contents ({field_name}):[/bold green] {file_path}"
        )
        self.console.print("[dim]" + "─" * 60 + "[/dim]")
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
            ext = os.path.splitext(file_path)[1].lower()
            lexer = _EXTENSION_TO_LEXER.get(ext, "text")
            syntax = Syntax(
                content, lexer, theme="monokai", line_numbers=True, word_wrap=True
            )
            self.console.print(syntax)
        except Exception as e:
            self.console.print(f"[red]Error reading file: {e}[/red]")

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
