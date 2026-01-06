"""
Rich formatting utilities for GAI workflow system.

This module provides utilities for creating visually appealing command-line output
using the Rich library for status messages, progress indicators, and structured data display.
"""

import time
from collections.abc import Generator
from contextlib import contextmanager

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

# Global console instance for consistent styling
console = Console()


def print_workflow_header(workflow_name: str, tag: str = "") -> None:
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


def print_status(message: str, status_type: str = "info") -> None:
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


def print_command_execution(
    command: str, success: bool, output: str | None = None
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


def create_progress_tracker(description: str, total: int | None = None) -> Progress:
    """Create a progress tracker for long-running operations."""
    return Progress(
        TextColumn("[bold blue]{task.description}"),
        SpinnerColumn(),
        BarColumn(bar_width=40),
        "[progress.percentage]{task.percentage:>3.1f}%",
        TimeElapsedColumn(),
        console=console,
    )


def print_artifact_created(artifact_path: str) -> None:
    """Print notification about artifact creation."""
    console.print(f"[dim]📄 Created artifact: {artifact_path}[/dim]")


def print_file_operation(operation: str, file_path: str, success: bool = True) -> None:
    """Print formatted file operation message."""
    icon = "✅" if success else "❌"
    color = "green" if success else "red"
    console.print(f"[{color}]{icon} {operation}: {file_path}[/{color}]")


def print_iteration_header(iteration: int, workflow_type: str) -> None:
    """Print formatted iteration header."""
    console.print(f"\n[bold magenta]{'=' * 60}[/bold magenta]")
    console.print(
        f"[bold magenta]🔄 {workflow_type.upper()} ITERATION {iteration}[/bold magenta]"
    )
    console.print(f"[bold magenta]{'=' * 60}[/bold magenta]\n")


def print_prompt_and_response(
    prompt: str,
    response: str,
    agent_type: str = "agent",
    iteration: int | None = None,
    show_prompt: bool = True,
    show_response: bool = True,
) -> None:
    """Print formatted prompt and response using Rich."""
    # Configure agent display based on type
    agent_configs = {
        "editor": ("🛠️ Editor Agent", "cyan"),
        "planner": ("📋 Planner Agent", "magenta"),
        "research_cl_scope": ("🔍 CL Scope Research", "yellow"),
        "research_similar_tests": ("🔍 Similar Tests Research", "yellow"),
        "research_test_failure": ("🔍 Test Failure Research", "yellow"),
        "research_prior_work_analysis": ("🔍 Prior Work Research", "yellow"),
        "research_cl_analysis": ("🔍 CL Analysis Research", "yellow"),
        "research_synthesis": ("🔬 Research Synthesis", "bright_magenta"),
        "verification": ("✅ Verification Agent", "green"),
        "add_tests": ("🧪 Add Tests Agent", "blue"),
        "test_failure_comparison": ("📊 Test Comparison Agent", "bright_yellow"),
        "postmortem": ("🔍 Postmortem Agent", "red"),
    }

    title, border_color = agent_configs.get(
        agent_type, (f"🤖 {agent_type.title()} Agent", "white")
    )

    if iteration is not None:
        title += f" (Iteration {iteration})"

    # Print prompt if requested
    if show_prompt and prompt:
        console.print(
            Panel(
                Syntax(prompt, "markdown", theme="monokai", word_wrap=True),
                title=f"{title} - Prompt",
                border_style=border_color,
                padding=(1, 2),
            )
        )

    # Print response if requested
    if show_response and response:
        console.print(
            Panel(
                Syntax(response, "markdown", theme="monokai", word_wrap=True),
                title=f"{title} - Response",
                border_style=border_color,
                padding=(1, 2),
            )
        )


def print_decision_counts(decision_counts: dict) -> None:
    """Print planning agent decision counts using Rich formatting."""
    if not decision_counts:
        return

    table = Table(
        title="🎯 Planning Agent Decision Counts",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Decision Type", style="cyan")
    table.add_column("Count", style="yellow", justify="right")

    table.add_row("New Editor", str(decision_counts.get("new_editor", 0)))
    table.add_row("Existing Editor", str(decision_counts.get("next_editor", 0)))
    table.add_row("Researcher", str(decision_counts.get("research", 0)))

    console.print(table)


@contextmanager
def gemini_timer(message: str = "Waiting for Gemini") -> Generator[None, None, None]:
    """
    Display a live updating timer showing elapsed time while waiting for Gemini.

    This context manager displays a timer that updates every second, showing
    how long the Gemini API call has been running. The timer appears directly
    below the pretty-printed prompt.

    Args:
        message: The message to display alongside the timer

    Yields:
        None

    Example:
        >>> with gemini_timer("Waiting for Gemini"):
        ...     result = subprocess.run(["gemini", "--yolo"], ...)
    """
    start_time = time.time()

    def _format_elapsed(elapsed_seconds: float) -> str:
        """Format elapsed time as MM:SS or HH:MM:SS."""
        total_seconds = int(elapsed_seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    # Create a Text object for the timer display
    def _get_timer_text() -> Text:
        elapsed = time.time() - start_time
        elapsed_str = _format_elapsed(elapsed)
        # Use a spinner and elapsed time format similar to TimeElapsedColumn
        text = Text()
        text.append("⏱️  ", style="bold cyan")
        text.append(message, style="bold")
        text.append(f" [{elapsed_str}]", style="cyan")
        return text

    # Use Rich Live to update the timer in place
    with Live(_get_timer_text(), refresh_per_second=2, console=console) as live:
        try:
            # Update the timer while the code block runs
            def _update_timer() -> None:
                while True:
                    live.update(_get_timer_text())
                    time.sleep(0.5)

            # Start the timer in the background (it will stop when we exit the context)
            import threading

            timer_thread = threading.Thread(target=_update_timer, daemon=True)
            timer_thread.start()

            # Yield control back to the caller
            yield

        finally:
            # Final update with the total elapsed time
            elapsed = time.time() - start_time
            elapsed_str = _format_elapsed(elapsed)
            final_text = Text()
            final_text.append("✅ ", style="bold green")
            final_text.append(message, style="bold")
            final_text.append(f" completed in {elapsed_str}", style="green")
            live.update(final_text)
            # Give a moment to show the final message
            time.sleep(0.3)


def format_countdown(
    seconds_remaining: int, message: str = "Next full check in"
) -> str:
    """Format a countdown timer string with Rich styling.

    Creates a styled countdown display similar to gemini_timer but counting down.
    Returns an ANSI-escaped string suitable for terminal output.

    Args:
        seconds_remaining: Number of seconds remaining until the event.
        message: The message to display alongside the countdown.

    Returns:
        A formatted string with ANSI escape codes for terminal styling.
    """
    minutes = seconds_remaining // 60
    seconds = seconds_remaining % 60
    time_str = f"{minutes}:{seconds:02d}"

    # Create styled text using Rich
    text = Text()
    text.append("⏳ ", style="bold yellow")
    text.append(message, style="bold")
    text.append(f" [{time_str}]", style="yellow")

    # Render to string with ANSI codes using a temporary console
    temp_console = Console(force_terminal=True, no_color=False)
    with temp_console.capture() as capture:
        temp_console.print(text, end="")
    return capture.get()
