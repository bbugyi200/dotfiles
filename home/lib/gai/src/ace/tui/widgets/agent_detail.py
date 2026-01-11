"""Agent detail widget for the ace TUI."""

import subprocess
from pathlib import Path
from typing import Any

from rich.syntax import Syntax
from rich.text import Text
from running_field import get_workspace_directory
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static

from ..models.agent import Agent, AgentType


class _AgentPromptPanel(Static):
    """Top panel showing the prompt/metadata for the agent."""

    def update_display(self, agent: Agent) -> None:
        """Update with agent information.

        Args:
            agent: The Agent to display.
        """
        text = Text()

        # Header
        text.append("AGENT DETAILS\n", style="bold #87D7FF underline")
        text.append("\n")

        # Agent type
        text.append("Type: ", style="bold #87D7FF")
        text.append(f"{agent.display_type}\n", style="#00D7AF")

        # ChangeSpec name
        text.append("ChangeSpec: ", style="bold #87D7FF")
        text.append(f"{agent.cl_name}\n", style="#00D7AF")

        # Status
        text.append("Status: ", style="bold #87D7FF")
        if agent.status == "RUNNING":
            text.append(f"{agent.status}\n", style="bold #FFD700")
        else:
            text.append(f"{agent.status}\n")

        # Start time
        if agent.start_time:
            text.append("Started: ", style="bold #87D7FF")
            text.append(f"{agent.start_time_display}\n")

            text.append("Duration: ", style="bold #87D7FF")
            text.append(f"{agent.duration_display}\n", style="#D7AF5F")

        # Type-specific details
        text.append("\n")

        if agent.agent_type == AgentType.RUNNING:
            if agent.workspace_num is not None:
                text.append("Workspace: ", style="bold #87D7FF")
                text.append(f"#{agent.workspace_num}\n", style="#5FD7FF")
            if agent.workflow:
                text.append("Workflow: ", style="bold #87D7FF")
                text.append(f"{agent.workflow}\n")

        elif agent.agent_type in (AgentType.FIX_HOOK, AgentType.SUMMARIZE):
            if agent.hook_command:
                text.append("Hook Command: ", style="bold #87D7FF")
                text.append(f"{agent.hook_command}\n")
            if agent.commit_entry_id:
                text.append("Commit Entry: ", style="bold #87D7FF")
                text.append(f"({agent.commit_entry_id})\n")

        elif agent.agent_type == AgentType.MENTOR:
            if agent.mentor_profile:
                text.append("Profile: ", style="bold #87D7FF")
                text.append(f"{agent.mentor_profile}\n")
            if agent.mentor_name:
                text.append("Mentor: ", style="bold #87D7FF")
                text.append(f"{agent.mentor_name}\n")

        elif agent.agent_type == AgentType.CRS:
            if agent.reviewer:
                text.append("Reviewer: ", style="bold #87D7FF")
                text.append(f"{agent.reviewer}\n")

        # PID if available
        if agent.pid:
            text.append("\n")
            text.append("PID: ", style="bold #87D7FF")
            text.append(f"{agent.pid}\n", style="dim")

        # Project file
        text.append("\n")
        text.append("Project File: ", style="bold #87D7FF")
        text.append(f"{agent.project_file}\n", style="dim")

        self.update(text)

    def show_empty(self) -> None:
        """Show empty state."""
        text = Text("No agent selected", style="dim italic")
        self.update(text)


class _AgentDiffPanel(Static):
    """Bottom panel showing the diff of agent's changes."""

    def update_display(self, agent: Agent) -> None:
        """Update with agent diff output.

        Args:
            agent: The Agent to display diff for.
        """
        diff_output = self._get_agent_diff(agent)

        if diff_output:
            # Use Syntax for diff highlighting
            syntax = Syntax(
                diff_output,
                "diff",
                theme="monokai",
                line_numbers=True,
                word_wrap=True,
            )
            self.update(syntax)
        else:
            text = Text()
            text.append("No changes detected.\n\n", style="dim italic")
            text.append(
                "The agent may not have made any changes yet, "
                "or the workspace is not accessible.",
                style="dim",
            )
            self.update(text)

    def _get_agent_diff(self, agent: Agent) -> str | None:
        """Get diff output for an agent.

        For RUNNING type agents, use workspace_num to find directory.
        For other agents, try to determine workspace from project file.

        Args:
            agent: The agent to get diff for.

        Returns:
            Diff output string, or None if unavailable.
        """
        try:
            # Get project basename from file path
            project_basename = Path(agent.project_file).stem

            if agent.agent_type == AgentType.RUNNING and agent.workspace_num:
                workspace_dir = get_workspace_directory(
                    project_basename, agent.workspace_num
                )
            else:
                # Use primary workspace for other agent types
                # Loop agents use workspaces 100+, but we show diff from main
                workspace_dir = get_workspace_directory(project_basename, 1)

            # Run hg diff for the changespec
            result = subprocess.run(
                ["hg", "diff", "-c", agent.cl_name],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 and result.stdout.strip():
                # Limit output size to avoid UI issues
                output = result.stdout
                max_chars = 10000
                if len(output) > max_chars:
                    output = output[:max_chars] + "\n... (truncated)"
                return output
            return None

        except subprocess.TimeoutExpired:
            return None
        except subprocess.CalledProcessError:
            return None
        except RuntimeError:
            # bb_get_workspace command failed
            return None
        except Exception:
            return None

    def show_empty(self) -> None:
        """Show empty state."""
        text = Text("No agent selected", style="dim italic")
        self.update(text)


class AgentDetail(Static):
    """Combined widget with prompt and diff panels."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the agent detail view."""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Compose the two-panel layout."""
        with Vertical(id="agent-detail-layout"):
            with VerticalScroll(id="agent-prompt-scroll"):
                yield _AgentPromptPanel(id="agent-prompt-panel")
            with VerticalScroll(id="agent-diff-scroll"):
                yield _AgentDiffPanel(id="agent-diff-panel")

    def update_display(self, agent: Agent) -> None:
        """Update both panels with agent information.

        Args:
            agent: The Agent to display.
        """
        prompt_panel = self.query_one("#agent-prompt-panel", _AgentPromptPanel)
        diff_panel = self.query_one("#agent-diff-panel", _AgentDiffPanel)

        prompt_panel.update_display(agent)
        diff_panel.update_display(agent)

    def show_empty(self) -> None:
        """Show empty state for both panels."""
        prompt_panel = self.query_one("#agent-prompt-panel", _AgentPromptPanel)
        diff_panel = self.query_one("#agent-diff-panel", _AgentDiffPanel)

        prompt_panel.show_empty()
        diff_panel.show_empty()
