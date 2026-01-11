"""Agent detail widget for the ace TUI."""

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.syntax import Syntax
from rich.text import Text
from running_field import get_workspace_directory
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static
from textual.worker import Worker, WorkerState

from ..models.agent import Agent, AgentType


@dataclass
class _DiffCacheEntry:
    """Cache entry for agent diff output."""

    diff_output: str | None
    fetch_time: datetime


# Module-level cache for diff outputs
_diff_cache: dict[str, _DiffCacheEntry] = {}


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

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the diff panel."""
        super().__init__(**kwargs)
        self._current_agent: Agent | None = None
        self._current_worker: Worker[str | None] | None = None

    def update_display(self, agent: Agent) -> None:
        """Update with agent diff output.

        Args:
            agent: The Agent to display diff for.
        """
        self._current_agent = agent

        # Check cache first
        if agent.cl_name in _diff_cache:
            cache_entry = _diff_cache[agent.cl_name]
            self._display_diff_with_timestamp(
                cache_entry.diff_output, cache_entry.fetch_time
            )
            return

        # Not in cache - show loading and start background fetch
        self._show_loading()

        # Cancel any existing worker
        if self._current_worker is not None and self._current_worker.is_running:
            self._current_worker.cancel()

        # Start background worker using closure to capture agent
        def fetch_task() -> str | None:
            return self._fetch_diff_in_background(agent)

        self._current_worker = self.run_worker(fetch_task, thread=True)

    def refresh_diff(self, agent: Agent) -> None:
        """Force refresh the diff for an agent.

        Args:
            agent: The Agent to refresh diff for.
        """
        # Clear cache entry
        if agent.cl_name in _diff_cache:
            del _diff_cache[agent.cl_name]

        # Show loading and start fetch
        self._current_agent = agent
        self._show_loading()

        # Cancel any existing worker
        if self._current_worker is not None and self._current_worker.is_running:
            self._current_worker.cancel()

        # Start background worker using closure to capture agent
        def fetch_task() -> str | None:
            return self._fetch_diff_in_background(agent)

        self._current_worker = self.run_worker(fetch_task, thread=True)

    def _show_loading(self) -> None:
        """Display loading indicator."""
        text = Text()
        text.append("Loading diff...\n", style="bold #87D7FF")
        text.append("Please wait while fetching changes.", style="dim")
        self.update(text)

    def _display_diff_with_timestamp(
        self, diff_output: str | None, fetch_time: datetime
    ) -> None:
        """Display diff output with fetch timestamp.

        Args:
            diff_output: The diff output or None if no changes.
            fetch_time: When the diff was fetched.
        """
        if diff_output:
            # Build text with timestamp header
            text = Text()
            text.append("Last fetched: ", style="dim")
            text.append(fetch_time.strftime("%H:%M:%S"), style="#87D7FF")
            text.append("\n\n")

            # Create syntax-highlighted diff
            syntax = Syntax(
                diff_output,
                "diff",
                theme="monokai",
                line_numbers=True,
                word_wrap=True,
            )
            # We need to render both - use a Group or just update with syntax
            # For simplicity, prepend timestamp to the diff output
            diff_with_header = (
                f"# Last fetched: {fetch_time.strftime('%H:%M:%S')}\n\n{diff_output}"
            )
            syntax = Syntax(
                diff_with_header,
                "diff",
                theme="monokai",
                line_numbers=True,
                word_wrap=True,
            )
            self.update(syntax)
        else:
            text = Text()
            text.append("Last fetched: ", style="dim")
            text.append(fetch_time.strftime("%H:%M:%S"), style="#87D7FF")
            text.append("\n\n")
            text.append("No changes detected.\n\n", style="dim italic")
            text.append(
                "The agent may not have made any changes yet, "
                "or the workspace is not accessible.",
                style="dim",
            )
            self.update(text)

    def _fetch_diff_in_background(self, agent: Agent) -> str | None:
        """Fetch diff output in background thread.

        Args:
            agent: The agent to get diff for.

        Returns:
            Diff output string, or None if unavailable.
        """
        diff_output = self._get_agent_diff(agent)

        # Store in cache
        _diff_cache[agent.cl_name] = _DiffCacheEntry(
            diff_output=diff_output,
            fetch_time=datetime.now(),
        )

        return diff_output

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        if event.worker != self._current_worker:
            return

        if event.state == WorkerState.SUCCESS:
            # Worker completed - display result from cache
            if self._current_agent and self._current_agent.cl_name in _diff_cache:
                cache_entry = _diff_cache[self._current_agent.cl_name]
                self._display_diff_with_timestamp(
                    cache_entry.diff_output, cache_entry.fetch_time
                )
        elif event.state == WorkerState.ERROR:
            # Show error state
            text = Text()
            text.append("Error fetching diff\n", style="bold red")
            text.append("The diff command failed or timed out.", style="dim")
            self.update(text)
        elif event.state == WorkerState.CANCELLED:
            # Cancelled - do nothing, new worker will handle display
            pass

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

            # Run hg diff to show working directory changes
            result = subprocess.run(
                ["hg", "diff"],
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

    def refresh_current_diff(self, agent: Agent) -> None:
        """Force refresh the diff for the given agent.

        Args:
            agent: The Agent to refresh diff for.
        """
        diff_panel = self.query_one("#agent-diff-panel", _AgentDiffPanel)
        diff_panel.refresh_diff(agent)
