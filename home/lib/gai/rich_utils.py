"""
Rich formatting utilities for GAI workflow system.

This module provides utilities for creating visually appealing command-line output
using the Rich library for status messages, progress indicators, and structured data display.
"""

from typing import Dict, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress,
    track,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.syntax import Syntax


# Global console instance for consistent styling
console = Console()


def _print_workflow_header(workflow_name: str, tag: str) -> None:
    """Print a formatted workflow header."""
    header_text = f"🚀 GAI {workflow_name.upper()} Workflow"
    if tag:
        header_text += f" ({tag})"

    console.print(
        Panel(
            f"[bold blue]{header_text}[/bold blue]",
            title="System",
            border_style="blue",
            padding=(1, 2),
        )
    )


def _print_workflow_success(workflow_name: str, message: str) -> None:
    """Print a formatted workflow success message."""
    console.print(
        Panel(
            f"[bold green]🎉 {message}[/bold green]",
            title=f"{workflow_name.title()} Complete",
            border_style="green",
            padding=(1, 2),
        )
    )


def _print_workflow_failure(
    workflow_name: str, message: str, details: Optional[str] = None
) -> None:
    """Print a formatted workflow failure message."""
    content = f"[bold red]❌ {message}[/bold red]"
    if details:
        content += f"\n\n[dim]{details}[/dim]"

    console.print(
        Panel(
            content,
            title=f"{workflow_name.title()} Failed",
            border_style="red",
            padding=(1, 2),
        )
    )


def _print_status(message: str, status_type: str = "info") -> None:
    """Print a status message with appropriate styling."""
    icons = {
        "info": "ℹ️",
        "success": "✅",
        "warning": "⚠️",
        "error": "❌",
        "progress": "🔄",
    }

    styles = {
        "info": "blue",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "progress": "cyan",
    }

    icon = icons.get(status_type, "ℹ️")
    style = styles.get(status_type, "white")

    console.print(f"[{style}]{icon} {message}[/{style}]")


def _print_agent_response(
    content: str, agent_type: str, iteration: Optional[int] = None
) -> None:
    """Print a formatted agent response."""
    agent_configs = {
        "editor": ("🛠️ Editor Agent", "cyan"),
        "planner": ("📋 Planner Agent", "magenta"),
        "research": ("🔍 Research Agent", "yellow"),
        "verification": ("✅ Verification Agent", "green"),
        "add_tests": ("🧪 Add Tests Agent", "blue"),
        "test_failure_comparison": ("📊 Test Comparison Agent", "orange"),
    }

    title, border_color = agent_configs.get(
        agent_type, (f"🤖 {agent_type.title()} Agent", "white")
    )

    if iteration is not None:
        title += f" (Iteration {iteration})"

    console.print(
        Panel(content, title=title, border_style=border_color, padding=(1, 2))
    )


def _print_command_execution(
    command: str, success: bool, output: Optional[str] = None
) -> None:
    """Print formatted command execution results."""
    status_icon = "✅" if success else "❌"
    status_color = "green" if success else "red"

    console.print(
        f"[{status_color}]{status_icon} Executing:[/{status_color}] [bold]{command}[/bold]"
    )

    if output and output.strip():
        # Truncate very long output
        if len(output) > 1000:
            output = output[:1000] + "\n... (output truncated)"

        console.print(Panel(output, title="Output", border_style="dim", padding=(0, 1)))


def _print_todo_list(
    todos: List[Dict[str, str]], title: str = "Workflow Tasks"
) -> None:
    """Print a formatted todo list as a table."""
    if not todos:
        return

    table = Table(title=f"📋 {title}", show_header=True, header_style="bold magenta")
    table.add_column("Status", width=12, style="cyan")
    table.add_column("Task", style="white")

    status_symbols = {
        "pending": "⏳ Pending",
        "in_progress": "🔄 Active",
        "completed": "✅ Done",
        "failed": "❌ Failed",
    }

    for todo in todos:
        status = todo.get("status", "pending")
        content = todo.get("content", "Unknown task")

        table.add_row(status_symbols.get(status, "❓ Unknown"), content)

    console.print(table)


def _create_progress_tracker(description: str, total: Optional[int] = None) -> Progress:
    """Create a progress tracker for long-running operations."""
    return Progress(
        TextColumn("[bold blue]{task.description}"),
        SpinnerColumn(),
        BarColumn(bar_width=40),
        "[progress.percentage]{task.percentage:>3.1f}%",
        TimeElapsedColumn(),
        console=console,
    )


def _track_operation(items: List, description: str):
    """Track an operation with a progress bar."""
    return track(items, description=description, console=console)


def _status_context(message: str):
    """Create a status context manager for indeterminate operations."""
    return console.status(f"[bold green]{message}")


def _print_artifact_created(artifact_path: str) -> None:
    """Print notification about artifact creation."""
    console.print(f"[dim]📄 Created artifact: {artifact_path}[/dim]")


def _print_test_result(
    test_cmd: str, success: bool, output: Optional[str] = None
) -> None:
    """Print formatted test execution results."""
    if success:
        _print_status(f"Test PASSED: {test_cmd}", "success")
    else:
        _print_status(f"Test FAILED: {test_cmd}", "error")

    if output and output.strip():
        # Show syntax highlighted output for common test frameworks
        if any(
            framework in output.lower() for framework in ["pytest", "unittest", "nose"]
        ):
            try:
                console.print(
                    Syntax(output, "python", theme="monokai", line_numbers=False)
                )
            except Exception:
                # Fallback to plain text if syntax highlighting fails
                console.print(Panel(output, title="Test Output", border_style="dim"))
        else:
            console.print(Panel(output, title="Test Output", border_style="dim"))


def _print_code_diff(diff_content: str, title: str = "Code Changes") -> None:
    """Print formatted code diff."""
    if not diff_content.strip():
        _print_status("No code changes detected", "info")
        return

    console.print(
        Panel(
            Syntax(diff_content, "diff", theme="monokai", line_numbers=False),
            title=title,
            border_style="yellow",
        )
    )


def _print_file_operation(operation: str, file_path: str, success: bool = True) -> None:
    """Print formatted file operation message."""
    icon = "✅" if success else "❌"
    color = "green" if success else "red"
    console.print(f"[{color}]{icon} {operation}: {file_path}[/{color}]")


def _print_iteration_header(iteration: int, workflow_type: str) -> None:
    """Print formatted iteration header."""
    console.print(f"\n[bold magenta]{'='*60}[/bold magenta]")
    console.print(
        f"[bold magenta]🔄 {workflow_type.upper()} ITERATION {iteration}[/bold magenta]"
    )
    console.print(f"[bold magenta]{'='*60}[/bold magenta]\n")


def _print_section_separator(title: str) -> None:
    """Print a section separator with title."""
    console.print(f"\n[bold blue]--- {title} ---[/bold blue]")


# Public API functions that should be used by the GAI modules
def print_workflow_header(workflow_name: str, tag: str = "") -> None:
    """Print a formatted workflow header."""
    _print_workflow_header(workflow_name, tag)


def print_workflow_success(workflow_name: str, message: str) -> None:
    """Print a formatted workflow success message."""
    _print_workflow_success(workflow_name, message)


def print_workflow_failure(
    workflow_name: str, message: str, details: Optional[str] = None
) -> None:
    """Print a formatted workflow failure message."""
    _print_workflow_failure(workflow_name, message, details)


def print_status(message: str, status_type: str = "info") -> None:
    """Print a status message with appropriate styling."""
    _print_status(message, status_type)


def print_agent_response(
    content: str, agent_type: str, iteration: Optional[int] = None
) -> None:
    """Print a formatted agent response."""
    _print_agent_response(content, agent_type, iteration)


def print_command_execution(
    command: str, success: bool, output: Optional[str] = None
) -> None:
    """Print formatted command execution results."""
    _print_command_execution(command, success, output)


def print_todo_list(todos: List[Dict[str, str]], title: str = "Workflow Tasks") -> None:
    """Print a formatted todo list as a table."""
    _print_todo_list(todos, title)


def create_progress_tracker(description: str, total: Optional[int] = None) -> Progress:
    """Create a progress tracker for long-running operations."""
    return _create_progress_tracker(description, total)


def track_operation(items: List, description: str):
    """Track an operation with a progress bar."""
    return _track_operation(items, description)


def status_context(message: str):
    """Create a status context manager for indeterminate operations."""
    return _status_context(message)


def print_artifact_created(artifact_path: str) -> None:
    """Print notification about artifact creation."""
    _print_artifact_created(artifact_path)


def print_test_result(
    test_cmd: str, success: bool, output: Optional[str] = None
) -> None:
    """Print formatted test execution results."""
    _print_test_result(test_cmd, success, output)


def print_code_diff(diff_content: str, title: str = "Code Changes") -> None:
    """Print formatted code diff."""
    _print_code_diff(diff_content, title)


def print_file_operation(operation: str, file_path: str, success: bool = True) -> None:
    """Print formatted file operation message."""
    _print_file_operation(operation, file_path, success)


def print_iteration_header(iteration: int, workflow_type: str) -> None:
    """Print formatted iteration header."""
    _print_iteration_header(iteration, workflow_type)


def print_section_separator(title: str) -> None:
    """Print a section separator with title."""
    _print_section_separator(title)
