"""Verbose output handler for workflow execution."""

import time
from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from shared_utils import dump_yaml


@dataclass
class LoopInfo:
    """Information about a loop iteration."""

    loop_type: str  # "for", "repeat", "while"
    items: list[Any] | None = None  # For for: loops
    iteration: int = 0
    max_iterations: int | None = None


@dataclass
class ParentStepContext:
    """Context for parent step when executing embedded workflow steps."""

    step_index: int  # 0-based index of parent step
    total_steps: int  # Total steps in parent workflow


class WorkflowOutputHandler:
    """Handler for displaying verbose output during workflow execution."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize the workflow output handler.

        Args:
            console: Optional Rich console for output. Creates one if not provided.
        """
        self.console = console or Console()
        self._step_start_time: float | None = None
        self._workflow_start_time: float | None = None

    def on_workflow_start(
        self,
        workflow_name: str,
        inputs: dict[str, Any],
        total_steps: int,
    ) -> None:
        """Called when workflow execution begins.

        Args:
            workflow_name: Name of the workflow.
            inputs: Input arguments passed to the workflow.
            total_steps: Total number of steps in the workflow.
        """
        self._workflow_start_time = time.time()

        # Format inputs for display
        inputs_str = ", ".join(f"{k}={_format_value(v)}" for k, v in inputs.items())
        if len(inputs_str) > 60:
            inputs_str = inputs_str[:57] + "..."

        content = Text()
        content.append("  Workflow: ", style="bold")
        content.append(workflow_name, style="cyan bold")
        content.append("\n")
        content.append("  Inputs: ", style="bold")
        content.append(inputs_str if inputs_str else "(none)", style="dim")
        content.append("\n")
        content.append("  Steps: ", style="bold")
        content.append(str(total_steps), style="cyan")

        self.console.print()
        self.console.print(
            Panel(
                content,
                title="[bold cyan]Workflow Started[/bold cyan]",
                border_style="cyan",
                padding=(0, 1),
            )
        )
        self.console.print()

    def on_step_start(
        self,
        step_name: str,
        step_type: str,
        step_index: int,
        total_steps: int,
        condition: str | None = None,
        condition_result: bool | None = None,
        loop_info: LoopInfo | None = None,
        parent_step_context: ParentStepContext | None = None,
    ) -> None:
        """Called when a step begins execution.

        Args:
            step_name: Name of the step.
            step_type: Type of step (prompt, bash, python).
            step_index: Zero-based index of the step.
            total_steps: Total number of steps.
            condition: The condition expression (if present).
            condition_result: Result of condition evaluation (if applicable).
            loop_info: Information about loop iteration (if applicable).
            parent_step_context: Context for parent step when executing embedded
                workflow steps.
        """
        self._step_start_time = time.time()

        # Step header
        if parent_step_context is not None:
            # Embedded step: use parent step number with letter suffix
            parent_num = parent_step_context.step_index + 1
            suffix = get_substep_suffix(step_index)
            step_display = f"{parent_num}{suffix}"
            total_display = parent_step_context.total_steps
        else:
            # Normal step: use regular numbering
            step_display = str(step_index + 1)
            total_display = total_steps

        header = f"Step {step_display}/{total_display}: {step_name} ({step_type})"
        self.console.print(f"[bold cyan]{header}[/bold cyan]")
        self.console.print("[dim]" + "-" * len(header) + "[/dim]")

        # Condition info
        if condition is not None:
            result_str = "true" if condition_result else "false"
            result_style = "green" if condition_result else "yellow"
            self.console.print(
                f"  Condition: [dim]{condition}[/dim] -> [{result_style}]{result_str}[/{result_style}]"
            )

        # Loop info
        if loop_info:
            self._print_loop_info(loop_info)

    def on_step_iteration(
        self,
        _step_name: str,
        iteration: int,
        total_iterations: int,
        loop_vars: dict[str, Any],
    ) -> None:
        """Called at the start of each loop iteration.

        Args:
            _step_name: Name of the step (unused).
            iteration: Current iteration (1-based).
            total_iterations: Total number of iterations.
            loop_vars: Variables for this iteration (e.g., {"item": "alpha"}).
        """
        vars_str = ", ".join(f"{k}={_format_value(v)}" for k, v in loop_vars.items())
        self.console.print(f"  [dim][{iteration}/{total_iterations}][/dim] {vars_str}")

    def on_step_complete(
        self,
        _step_name: str,
        output: Any,
        duration: float | None = None,
    ) -> None:
        """Called when a step completes successfully.

        Args:
            _step_name: Name of the step (unused).
            output: The step's output data.
            duration: Execution duration in seconds.
        """
        if duration is None and self._step_start_time:
            duration = time.time() - self._step_start_time

        duration_str = f" ({duration:.2f}s)" if duration else ""
        self.console.print(f"\n  [green]Completed{duration_str}[/green]")

        # Display output
        if output:
            self._print_output(output)

        self.console.print()

    def on_step_skip(
        self,
        _step_name: str,
        reason: str | None = None,
    ) -> None:
        """Called when a step is skipped.

        Args:
            _step_name: Name of the step (unused).
            reason: Reason for skipping.
        """
        reason_str = f" ({reason})" if reason else ""
        self.console.print(f"  [yellow]Skipped{reason_str}[/yellow]")
        self.console.print()

    def on_repeat_iteration(
        self,
        _step_name: str,
        iteration: int,
        max_iterations: int,
        condition_result: bool,
    ) -> None:
        """Called during repeat/while loop iterations.

        Args:
            _step_name: Name of the step (unused).
            iteration: Current iteration (1-based).
            max_iterations: Maximum allowed iterations.
            condition_result: Result of the condition check.
        """
        result_style = "green" if condition_result else "dim"
        self.console.print(
            f"  [dim]Iteration {iteration}/{max_iterations}[/dim] -> [{result_style}]{condition_result}[/{result_style}]"
        )

    def on_parallel_start(
        self,
        step_name: str,
        nested_step_names: list[str],
    ) -> None:
        """Called when parallel execution begins.

        Args:
            step_name: Name of the parent parallel step.
            nested_step_names: Names of the steps that will run in parallel.
        """
        steps_str = ", ".join(nested_step_names)
        self.console.print(
            f"  [cyan]Parallel:[/cyan] Running {len(nested_step_names)} steps: {steps_str}"
        )

    def on_parallel_step_complete(
        self,
        _parent_step_name: str,
        nested_step_name: str,
        output: Any,
        error: str | None,
    ) -> None:
        """Called when a nested step within a parallel block completes.

        Args:
            _parent_step_name: Name of the parent parallel step (unused).
            nested_step_name: Name of the completed nested step.
            output: The step's output (or None on failure).
            error: Error message if failed, None on success.
        """
        if error:
            self.console.print(f"    [red]✗ {nested_step_name}:[/red] {error}")
        else:
            output_preview = _format_value(output) if output else "(no output)"
            if len(output_preview) > 50:
                output_preview = output_preview[:47] + "..."
            self.console.print(
                f"    [green]✓ {nested_step_name}:[/green] {output_preview}"
            )

    def on_parallel_complete(
        self,
        _step_name: str,
        combined_output: Any,
        errors: list[str] | None,
    ) -> None:
        """Called when all parallel steps complete.

        Args:
            _step_name: Name of the parallel step (unused).
            combined_output: The combined output from all parallel steps.
            errors: List of error messages if any steps failed.
        """
        if errors:
            self.console.print(f"  [red]Parallel failed: {len(errors)} error(s)[/red]")
        else:
            num_results = (
                len(combined_output) if isinstance(combined_output, dict) else 0
            )
            self.console.print(
                f"  [green]Parallel complete: {num_results} results[/green]"
            )

    def on_workflow_complete(
        self,
        _final_output: Any,
        total_duration: float | None = None,
    ) -> None:
        """Called when workflow execution completes.

        Args:
            _final_output: The final output from the last step (unused).
            total_duration: Total workflow duration in seconds.
        """
        if total_duration is None and self._workflow_start_time:
            total_duration = time.time() - self._workflow_start_time

        duration_str = (
            f"  Total duration: {total_duration:.2f}s" if total_duration else ""
        )

        content = Text()
        content.append("  Workflow completed successfully", style="green bold")
        if duration_str:
            content.append(f"\n{duration_str}", style="dim")

        self.console.print(
            Panel(
                content,
                title="[bold green]Complete[/bold green]",
                border_style="green",
                padding=(0, 1),
            )
        )
        self.console.print()

    def on_workflow_failed(
        self,
        error_message: str,
        total_duration: float | None = None,
    ) -> None:
        """Called when workflow execution fails.

        Args:
            error_message: Description of the failure.
            total_duration: Total workflow duration in seconds.
        """
        if total_duration is None and self._workflow_start_time:
            total_duration = time.time() - self._workflow_start_time

        duration_str = (
            f"  Total duration: {total_duration:.2f}s" if total_duration else ""
        )

        content = Text()
        content.append("  Workflow failed", style="red bold")
        content.append(f"\n  Error: {error_message}", style="red")
        if duration_str:
            content.append(f"\n{duration_str}", style="dim")

        self.console.print(
            Panel(
                content,
                title="[bold red]Failed[/bold red]",
                border_style="red",
                padding=(0, 1),
            )
        )
        self.console.print()

    def _print_loop_info(self, loop_info: LoopInfo) -> None:
        """Print loop information.

        Args:
            loop_info: The loop information to display.
        """
        if loop_info.loop_type == "for" and loop_info.items is not None:
            items_preview = _format_value(loop_info.items)
            if len(items_preview) > 50:
                items_preview = items_preview[:47] + "..."
            self.console.print(
                f"  Loop: for ... in {items_preview} ({len(loop_info.items)} items)"
            )
        elif loop_info.loop_type == "repeat":
            max_str = f"/{loop_info.max_iterations}" if loop_info.max_iterations else ""
            self.console.print(f"  Loop: repeat/until (max{max_str})")
        elif loop_info.loop_type == "while":
            max_str = f"/{loop_info.max_iterations}" if loop_info.max_iterations else ""
            self.console.print(f"  Loop: while (max{max_str})")

    def _print_output(self, output: Any) -> None:
        """Print step output with YAML syntax highlighting.

        Args:
            output: The output data to display.
        """
        self.console.print("  [bold]Output:[/bold]")

        if isinstance(output, dict):
            # Unwrap _data or _raw if present
            display_data = output.get("_data", output.get("_raw", output))
            output_str = dump_yaml(display_data, sort_keys=False)
        elif isinstance(output, list):
            output_str = dump_yaml(output, sort_keys=False)
        else:
            output_str = str(output)

        # Indent the output
        indented = "\n".join("    " + line for line in output_str.splitlines())

        syntax = Syntax(indented, "yaml", theme="monokai", background_color="default")
        self.console.print(syntax)


def get_substep_suffix(index: int) -> str:
    """Convert 0-based index to substep suffix (a, b, ..., z, aa, ab, ...).

    Args:
        index: 0-based index of the substep.

    Returns:
        Letter suffix for the substep (a-z, then aa, ab, etc.).
    """
    if index < 26:
        return chr(ord("a") + index)
    # For 26+, use aa, ab, etc.
    first = index // 26 - 1
    second = index % 26
    return chr(ord("a") + first) + chr(ord("a") + second)


def _format_value(value: Any) -> str:
    """Format a value for display.

    Args:
        value: The value to format.

    Returns:
        A string representation suitable for display.
    """
    if isinstance(value, str):
        if len(value) > 40:
            return f'"{value[:37]}..."'
        return f'"{value}"'
    elif isinstance(value, list):
        if len(value) <= 3:
            return str(value)
        return f"[{value[0]!r}, {value[1]!r}, ... ({len(value)} items)]"
    elif isinstance(value, dict):
        if len(value) <= 2:
            return str(value)
        return f"{{...}} ({len(value)} keys)"
    else:
        return str(value)
