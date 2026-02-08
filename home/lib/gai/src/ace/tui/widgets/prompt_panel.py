"""Agent prompt panel widget for the ace TUI."""

import json
from pathlib import Path
from typing import Any

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text
from textual.widgets import Static

from ..models.agent import Agent, AgentType


class AgentPromptPanel(Static):
    """Top panel showing agent details and the input prompt."""

    def update_display(self, agent: Agent) -> None:
        """Update with agent information and prompt.

        Args:
            agent: The Agent to display.
        """
        # Check if this is a top-level workflow agent that should display as workflow
        # Workflows with appears_as_agent=True should show as regular agents
        # Workflow children (steps) should show the normal agent view with prompt/chat
        if (
            agent.agent_type == AgentType.WORKFLOW
            and not agent.is_workflow_child
            and not agent.appears_as_agent
        ):
            self._update_workflow_display(agent)
            return

        header_text = Text()

        # Header - AGENT DETAILS
        header_text.append("AGENT DETAILS\n", style="bold #D7AF5F underline")
        header_text.append("\n")

        # For workflow step agents, show "Step" instead of "ChangeSpec"
        if agent.is_workflow_child and agent.step_name:
            header_text.append("Step: ", style="bold #87D7FF")
            header_text.append(f"{agent.step_name}\n", style="#00D7AF")
        else:
            # ChangeSpec name
            header_text.append("ChangeSpec: ", style="bold #87D7FF")
            header_text.append(f"{agent.cl_name}", style="#00D7AF")
            if agent.cl_num:
                cl_id = agent.cl_num.removeprefix("http://cl/")
                header_text.append(" (")
                header_text.append(f"http://cl/{cl_id}", style="bold underline #569CD6")
                header_text.append(")")
            header_text.append("\n")

        # Workspace (if available)
        if agent.workspace_num is not None:
            header_text.append("Workspace: ", style="bold #87D7FF")
            header_text.append(f"#{agent.workspace_num}\n", style="#5FD7FF")

        # Workflow (if available)
        if agent.workflow:
            header_text.append("Workflow: ", style="bold #87D7FF")
            header_text.append(f"{agent.workflow}\n")

        # PID (if available)
        if agent.pid:
            header_text.append("PID: ", style="bold #87D7FF")
            header_text.append(f"{agent.pid}\n", style="#FF87D7 bold")

        # BUG field (if available)
        if agent.bug:
            header_text.append("BUG: ", style="bold #87D7FF")
            header_text.append(f"{agent.bug}\n", style="bold underline #569CD6")

        # Timestamp (when agent started)
        header_text.append("Timestamp: ", style="bold #87D7FF")
        header_text.append(f"{agent.start_time_display}\n", style="#D7D7FF")

        # Meta fields from step output
        if agent.step_output and isinstance(agent.step_output, dict):
            meta_fields = _extract_meta_fields(agent.step_output)
            if meta_fields:
                header_text.append("\n")
                for name, value in meta_fields:
                    header_text.append(f"{name}: ", style="bold #87D7FF")
                    header_text.append(f"{value}\n", style="#5FD75F")

        # Error message (for failed agents)
        if agent.error_message:
            header_text.append("\n")
            header_text.append("ERROR\n", style="bold #FF5F5F underline")
            header_text.append(f"{agent.error_message}\n", style="bold #FF5F5F")

        # Separator
        header_text.append("\n")
        header_text.append("─" * 50 + "\n", style="dim")
        header_text.append("\n")

        # Check if this is a bash/python workflow step - display differently
        if agent.is_workflow_child and agent.step_type in ("bash", "python"):
            self._update_bash_python_display(agent, header_text)
            return

        # Check if this is a parallel workflow step - show output only, no prompt
        if agent.is_workflow_child and agent.step_type == "parallel":
            self._update_parallel_display(agent, header_text)
            return

        # AGENT PROMPT section
        header_text.append("AGENT PROMPT\n", style="bold #D7AF5F underline")
        header_text.append("\n")

        # Get and display prompt content
        prompt_content = self._get_prompt_content(agent)
        if prompt_content:
            # Render markdown with syntax highlighting
            prompt_syntax = Syntax(
                prompt_content,
                "markdown",
                theme="monokai",
                word_wrap=True,
            )

            # For completed agents/steps, also show the response
            if agent.status == "DONE":
                reply_header = Text()
                reply_header.append("\n")
                reply_header.append("─" * 50 + "\n", style="dim")
                reply_header.append("\n")
                reply_header.append("AGENT CHAT\n", style="bold #D7AF5F underline")
                reply_header.append("\n")

                response_content = agent.get_response_content()

                # Fallback: for workflow step agents, try step_output if no response file
                if (
                    response_content is None
                    and agent.is_workflow_child
                    and agent.step_output
                ):
                    response_content = _format_output(agent.step_output)

                if response_content:
                    response_syntax = Syntax(
                        response_content,
                        "markdown",
                        theme="monokai",
                        word_wrap=True,
                    )
                    self.update(
                        Group(header_text, prompt_syntax, reply_header, response_syntax)
                    )
                else:
                    reply_header.append("No response file found.\n", style="dim italic")
                    self.update(Group(header_text, prompt_syntax, reply_header))
            else:
                self.update(Group(header_text, prompt_syntax))
        else:
            header_text.append("No prompt file found.\n", style="dim italic")
            self.update(header_text)

    def _get_prompt_content(self, agent: Agent) -> str | None:
        """Get the prompt content for the agent.

        Args:
            agent: The agent to get prompt for.

        Returns:
            Prompt content, or None if not found.
        """
        artifacts_dir = agent.get_artifacts_dir()
        if artifacts_dir is None:
            return None

        artifacts_path = Path(artifacts_dir)

        # Look for any *_prompt.md file
        prompt_files = list(artifacts_path.glob("*_prompt.md"))

        if not prompt_files:
            return None

        # For workflow child agents, filter to the step-specific prompt file.
        # All workflow steps share the same artifacts_dir, so without filtering
        # we'd always show the most recently modified prompt (usually the last
        # step).
        if agent.is_workflow_child and agent.step_name:
            step_specific = [
                p
                for p in prompt_files
                if p.name.endswith(f"-{agent.step_name}_prompt.md")
            ]
            if step_specific:
                prompt_files = step_specific

        # Sort by modification time to get the most recent
        prompt_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        try:
            with open(prompt_files[0], encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None

    def _update_bash_python_display(self, agent: Agent, header_text: Text) -> None:
        """Display bash command or python code with output.

        Args:
            agent: The workflow step agent to display.
            header_text: The Text object with header content to append to.
        """
        if agent.step_type == "bash":
            source_label = "BASH COMMAND"
            syntax_lang = "bash"
        else:
            source_label = "PYTHON CODE"
            syntax_lang = "python"

        # Show source header
        header_text.append(f"{source_label}\n", style="bold #D7AF5F underline")
        header_text.append("\n")

        source_content: Syntax | Text
        if agent.step_source:
            source_content = Syntax(
                agent.step_source, syntax_lang, theme="monokai", word_wrap=True
            )
        else:
            source_content = Text("No source available.\n", style="dim italic")

        # Show output section
        output_header = Text()
        output_header.append("\n")
        output_header.append("─" * 50 + "\n", style="dim")
        output_header.append("\n")
        output_header.append("STEP OUTPUT\n", style="bold #D7AF5F underline")
        output_header.append("\n")

        if agent.step_output:
            output_str = _format_output(agent.step_output)
            output_syntax = Syntax(output_str, "json", theme="monokai", word_wrap=True)
            self.update(
                Group(header_text, source_content, output_header, output_syntax)
            )
        else:
            output_header.append("No output available.\n", style="dim italic")
            self.update(Group(header_text, source_content, output_header))

    def _update_parallel_display(self, agent: Agent, header_text: Text) -> None:
        """Display output for a parallel workflow step (no prompt section).

        Args:
            agent: The workflow step agent to display.
            header_text: The Text object with header content to append to.
        """
        header_text.append("STEP OUTPUT\n", style="bold #D7AF5F underline")
        header_text.append("\n")

        if agent.step_output:
            output_str = _format_output(agent.step_output)
            output_syntax = Syntax(output_str, "json", theme="monokai", word_wrap=True)
            self.update(Group(header_text, output_syntax))
        else:
            header_text.append("No output available.\n", style="dim italic")
            self.update(header_text)

    def _update_workflow_display(self, agent: Agent) -> None:
        """Update display for a workflow agent.

        Args:
            agent: The workflow agent to display.
        """
        header_text = Text()

        # Header - WORKFLOW DETAILS
        header_text.append("WORKFLOW DETAILS\n", style="bold #D7AF5F underline")
        header_text.append("\n")

        # Workflow name (stored in workflow field)
        header_text.append("Workflow: ", style="bold #87D7FF")
        header_text.append(f"{agent.workflow or 'unknown'}\n", style="#AF87D7 bold")

        # ChangeSpec name
        header_text.append("ChangeSpec: ", style="bold #87D7FF")
        header_text.append(f"{agent.cl_name}\n", style="#00D7AF")

        # Status
        header_text.append("Status: ", style="bold #87D7FF")
        status_style = {
            "RUNNING": "#87D7FF",
            "WAITING INPUT": "#FFAF5F",
            "DONE": "#5FD75F",
            "FAILED": "#FF5F5F",
        }.get(agent.status, "#D7D7FF")
        header_text.append(f"{agent.status}\n", style=status_style)

        # Timestamp
        header_text.append("Timestamp: ", style="bold #87D7FF")
        header_text.append(f"{agent.start_time_display}\n", style="#D7D7FF")

        # PID (if available)
        if agent.pid:
            header_text.append("PID: ", style="bold #87D7FF")
            header_text.append(f"{agent.pid}\n", style="#FF87D7 bold")

        # Meta fields aggregated from all step outputs
        meta_fields = self._load_workflow_meta_fields(agent)
        if meta_fields:
            header_text.append("\n")
            for name, value in meta_fields:
                header_text.append(f"{name}: ", style="bold #87D7FF")
                header_text.append(f"{value}\n", style="#5FD75F")

        # Inputs (if available)
        inputs = self._load_workflow_inputs(agent)
        if inputs:
            header_text.append("\n")
            header_text.append("INPUTS\n", style="bold #D7AF5F underline")
            for key, value in inputs.items():
                header_text.append(f"  {key}: ", style="bold #87D7FF")
                if isinstance(value, str):
                    header_text.append(f'"{value}"\n', style="#5FD75F")
                else:
                    header_text.append(f"{value}\n", style="#5FD75F")

        # Separator
        header_text.append("\n")
        header_text.append("─" * 50 + "\n", style="dim")
        header_text.append("\n")
        header_text.append("WORKFLOW STEPS\n", style="bold #D7AF5F underline")
        header_text.append("\n")

        # Load and format workflow steps from workflow_state.json
        steps_content = self._load_workflow_steps(agent)
        if steps_content:
            # Render as YAML with syntax highlighting
            steps_syntax = Syntax(
                steps_content,
                "yaml",
                theme="monokai",
                word_wrap=True,
            )
            self.update(Group(header_text, steps_syntax))
        else:
            header_text.append("No workflow state found.\n", style="dim italic")
            self.update(header_text)

    def _load_workflow_inputs(self, agent: Agent) -> dict[str, Any] | None:
        """Load workflow inputs from workflow_state.json.

        Args:
            agent: The workflow agent.

        Returns:
            Dict of workflow inputs, or None if not found.
        """
        artifacts_dir = agent.get_artifacts_dir()
        if artifacts_dir is None:
            return None

        state_file = Path(artifacts_dir) / "workflow_state.json"
        if not state_file.exists():
            return None

        try:
            with open(state_file, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return None

        return data.get("inputs")

    def _load_workflow_meta_fields(self, agent: Agent) -> list[tuple[str, str]]:
        """Load aggregated meta_* fields from workflow step outputs.

        Args:
            agent: The workflow agent.

        Returns:
            List of (display_name, value) tuples.
        """
        artifacts_dir = agent.get_artifacts_dir()
        if artifacts_dir is None:
            return []

        state_file = Path(artifacts_dir) / "workflow_state.json"
        if not state_file.exists():
            return []

        try:
            with open(state_file, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return []

        steps = data.get("steps", [])
        return _aggregate_meta_fields(steps)

    def _load_workflow_steps(self, agent: Agent) -> str | None:
        """Load and format workflow steps from workflow_state.json.

        Args:
            agent: The workflow agent.

        Returns:
            Formatted string of step details, or None if not found.
        """
        artifacts_dir = agent.get_artifacts_dir()
        if artifacts_dir is None:
            return None

        state_file = Path(artifacts_dir) / "workflow_state.json"
        if not state_file.exists():
            return None

        try:
            with open(state_file, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return None

        steps = data.get("steps", [])
        if not steps:
            # Check for workflow-level error (e.g., validation failure)
            error = data.get("error")
            if error:
                return f"Error: {error}"
            return None

        return self._format_workflow_steps(steps, data.get("context", {}))

    def _format_workflow_steps(
        self, steps: list[dict[str, Any]], _context: dict[str, Any]
    ) -> str:
        """Format workflow steps for display.

        Args:
            steps: List of step state dictionaries from workflow_state.json.
            _context: The workflow context with variables (unused, for future use).

        Returns:
            Formatted string for display.
        """
        lines: list[str] = []
        total_steps = len(steps)

        for i, step in enumerate(steps):
            step_name = step.get("name", "unknown")
            status = step.get("status", "pending")
            output = step.get("output")
            error = step.get("error")

            # Step header
            status_indicator = _get_status_indicator(status)
            lines.append(f"Step {i + 1}/{total_steps}: {step_name} {status_indicator}")
            lines.append("-" * 40)

            # Status
            lines.append(f"  Status: {status}")

            # Error (if any)
            if error:
                lines.append(f"  Error: {error}")

            # Output (if any)
            if output:
                output_str = _format_output(output)
                lines.append("  Output:")
                for line in output_str.splitlines():
                    lines.append(f"    {line}")

            lines.append("")

        return "\n".join(lines)

    def show_empty(self) -> None:
        """Show empty state."""
        text = Text("No agent selected", style="dim italic")
        self.update(text)


def _get_status_indicator(status: str) -> str:
    """Get a status indicator emoji/symbol.

    Args:
        status: The status string.

    Returns:
        A status indicator character.
    """
    indicators = {
        "completed": "[OK]",
        "in_progress": "[...]",
        "pending": "[ ]",
        "skipped": "[SKIP]",
        "failed": "[FAIL]",
        "waiting_hitl": "[WAIT]",
    }
    return indicators.get(status, f"[{status}]")


def _format_output(output: Any) -> str:
    """Format step output for display.

    Args:
        output: The output data (dict, list, or primitive).

    Returns:
        Formatted string representation.
    """
    if output is None:
        return "(none)"

    if isinstance(output, dict):
        # Unwrap _data or _raw if present
        display_data = output.get("_data", output.get("_raw", output))
        if isinstance(display_data, str):
            return display_data
        try:
            return json.dumps(display_data, indent=2, default=str)
        except Exception:
            return str(display_data)
    elif isinstance(output, list):
        try:
            return json.dumps(output, indent=2, default=str)
        except Exception:
            return str(output)
    else:
        return str(output)


def _format_meta_key(key: str) -> str:
    """Format a meta_* key for display.

    Strips the 'meta_' prefix, replaces underscores with spaces, and
    title-cases the result.

    Args:
        key: The raw meta key (e.g. 'meta_new_cl').

    Returns:
        Formatted display name (e.g. 'New Cl').
    """
    return key.removeprefix("meta_").replace("_", " ").title()


def _extract_meta_fields(output: dict[str, Any]) -> list[tuple[str, str]]:
    """Extract meta_* fields from a step output dict.

    Args:
        output: A step output dictionary.

    Returns:
        List of (display_name, value) tuples for meta fields.
    """
    results: list[tuple[str, str]] = []
    for key, value in output.items():
        if key.startswith("meta_"):
            results.append((_format_meta_key(key), str(value)))
    return results


def _aggregate_meta_fields(
    steps: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    """Aggregate meta_* fields from all workflow steps.

    If a raw key appears in more than one step, each occurrence gets a
    ' #N' suffix (N starting at 1).

    Args:
        steps: List of step state dicts (each may have an 'output' dict).

    Returns:
        List of (display_name, value) tuples.
    """
    # First pass: collect all (raw_key, display_name, value) triples and count keys
    entries: list[tuple[str, str, str]] = []
    key_counts: dict[str, int] = {}
    for step in steps:
        output = step.get("output")
        if not isinstance(output, dict):
            continue
        for key, value in output.items():
            if key.startswith("meta_"):
                key_counts[key] = key_counts.get(key, 0) + 1
                entries.append((key, _format_meta_key(key), str(value)))

    # Second pass: build results, adding #N suffix for duplicates
    counters: dict[str, int] = {}
    results: list[tuple[str, str]] = []
    for raw_key, display_name, value in entries:
        if key_counts[raw_key] > 1:
            counters[raw_key] = counters.get(raw_key, 0) + 1
            display_name = f"{display_name} #{counters[raw_key]}"
        results.append((display_name, value))
    return results
