"""Agent detail widget for the ace TUI."""

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text
from running_field import get_workspace_directory
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Static
from textual.worker import Worker, WorkerState

from ..models.agent import Agent, AgentType


class _DiffVisibilityChanged(Message):
    """Message posted when diff visibility should change."""

    def __init__(self, has_diff: bool) -> None:
        """Initialize the message.

        Args:
            has_diff: True if there is a diff to display, False if empty.
        """
        super().__init__()
        self.has_diff = has_diff


@dataclass
class _DiffCacheEntry:
    """Cache entry for agent diff output."""

    diff_output: str | None
    fetch_time: datetime


# Module-level cache for diff outputs
_diff_cache: dict[str, _DiffCacheEntry] = {}


def _get_cache_key(agent: Agent) -> str:
    """Generate a unique cache key for an agent's diff.

    Includes agent type and workspace to ensure different agents
    don't share cached diffs incorrectly.
    """
    if agent.agent_type == AgentType.RUNNING and agent.workspace_num is not None:
        return f"{agent.cl_name}:{agent.agent_type.value}:{agent.workspace_num}"
    return f"{agent.cl_name}:{agent.agent_type.value}"


class _AgentPromptPanel(Static):
    """Top panel showing agent details and the input prompt."""

    def update_display(self, agent: Agent) -> None:
        """Update with agent information and prompt.

        Args:
            agent: The Agent to display.
        """
        header_text = Text()

        # Header - AGENT DETAILS
        header_text.append("AGENT DETAILS\n", style="bold #D7AF5F underline")
        header_text.append("\n")

        # ChangeSpec name
        header_text.append("ChangeSpec: ", style="bold #87D7FF")
        header_text.append(f"{agent.cl_name}\n", style="#00D7AF")

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
            header_text.append(f"{agent.pid}\n", style="#5FD7FF bold")

        # Separator
        header_text.append("\n")
        header_text.append("─" * 50 + "\n", style="dim")
        header_text.append("\n")

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

            # For completed agents, also show the response
            if agent.status in ("NO CHANGES", "NEW CL", "NEW PROPOSAL"):
                reply_header = Text()
                reply_header.append("\n")
                reply_header.append("─" * 50 + "\n", style="dim")
                reply_header.append("\n")
                reply_header.append("AGENT REPLY\n", style="bold #D7AF5F underline")
                reply_header.append("\n")

                response_content = agent.get_response_content()
                if response_content:
                    # Truncate if too long
                    max_chars = 10000
                    if len(response_content) > max_chars:
                        response_content = (
                            response_content[:max_chars] + "\n\n... (truncated)"
                        )

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

        # Sort by modification time to get the most recent
        prompt_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        try:
            with open(prompt_files[0], encoding="utf-8") as f:
                content = f.read()
                # Truncate if too long
                max_chars = 10000
                if len(content) > max_chars:
                    content = content[:max_chars] + "\n\n... (truncated)"
                return content
        except Exception:
            return None

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
        self._has_displayed_content: bool = False

    def update_display(self, agent: Agent, stale_threshold_seconds: int = 10) -> None:
        """Update with agent diff output.

        Args:
            agent: The Agent to display diff for.
            stale_threshold_seconds: Diffs older than this are refetched.
        """
        self._current_agent = agent

        # Check cache - only use if fresh (less than threshold seconds old)
        cache_key = _get_cache_key(agent)
        if cache_key in _diff_cache:
            cache_entry = _diff_cache[cache_key]
            age_seconds = (datetime.now() - cache_entry.fetch_time).total_seconds()
            if age_seconds < stale_threshold_seconds:
                # Cache is fresh - use it (skip visibility message to avoid flicker)
                self._display_diff_with_timestamp(
                    cache_entry.diff_output,
                    cache_entry.fetch_time,
                    post_visibility_message=False,
                )
                return
            # Cache is stale - fall through to fetch

        # Not in cache or stale - show loading and start background fetch
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
        cache_key = _get_cache_key(agent)
        if cache_key in _diff_cache:
            del _diff_cache[cache_key]

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
        """Display loading indicator only if panel was previously visible."""
        if not self._has_displayed_content:
            return
        text = Text()
        text.append("Loading diff...\n", style="bold #87D7FF")
        text.append("Please wait while fetching changes.", style="dim")
        self.update(text)

    def _display_diff_with_timestamp(
        self,
        diff_output: str | None,
        fetch_time: datetime,
        *,
        post_visibility_message: bool = True,
    ) -> None:
        """Display diff output with fetch timestamp.

        Args:
            diff_output: The diff output or None if no changes.
            fetch_time: When the diff was fetched.
            post_visibility_message: Whether to post visibility change message.
                Set to False when displaying cached data to avoid flicker.
        """
        # Post visibility message to parent (only for fresh fetches to avoid flicker)
        if post_visibility_message:
            self.post_message(_DiffVisibilityChanged(has_diff=diff_output is not None))

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
            text.append("No changes detected.\n", style="dim italic")
            self.update(text)

        self._has_displayed_content = True

    def _fetch_diff_in_background(self, agent: Agent) -> str | None:
        """Fetch diff output in background thread.

        Args:
            agent: The agent to get diff for.

        Returns:
            Diff output string, or None if unavailable.
        """
        diff_output = self._get_agent_diff(agent)

        # Store in cache
        cache_key = _get_cache_key(agent)
        _diff_cache[cache_key] = _DiffCacheEntry(
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
            if self._current_agent:
                cache_key = _get_cache_key(self._current_agent)
                if cache_key in _diff_cache:
                    cache_entry = _diff_cache[cache_key]
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
        self._has_displayed_content = False
        text = Text("No agent selected", style="dim italic")
        self.update(text)

    def display_static_diff(self, diff_path: str) -> None:
        """Display a static diff from a file (no auto-refresh).

        Args:
            diff_path: Path to the diff file (may use ~ for home).
        """
        expanded_path = os.path.expanduser(diff_path)
        try:
            with open(expanded_path, encoding="utf-8") as f:
                diff_content = f.read()
                # Truncate if too long
                max_chars = 10000
                if len(diff_content) > max_chars:
                    diff_content = diff_content[:max_chars] + "\n... (truncated)"
        except Exception:
            text = Text("Could not read diff file.\n", style="dim italic")
            self.update(text)
            self.post_message(_DiffVisibilityChanged(has_diff=False))
            return

        if not diff_content.strip():
            text = Text("Diff file is empty.\n", style="dim italic")
            self.update(text)
            self.post_message(_DiffVisibilityChanged(has_diff=False))
            return

        # Display diff with "static" indicator instead of timestamp
        diff_with_header = f"# Static diff (from saved file)\n\n{diff_content}"
        syntax = Syntax(
            diff_with_header,
            "diff",
            theme="monokai",
            line_numbers=True,
            word_wrap=True,
        )
        self.update(syntax)
        self._has_displayed_content = True
        self.post_message(_DiffVisibilityChanged(has_diff=True))


class AgentDetail(Static):
    """Combined widget with prompt and diff panels."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the agent detail view."""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Compose the two-panel layout (prompt and diff)."""
        with Vertical(id="agent-detail-layout"):
            with VerticalScroll(id="agent-prompt-scroll"):
                yield _AgentPromptPanel(id="agent-prompt-panel")
            with VerticalScroll(id="agent-diff-scroll"):
                yield _AgentDiffPanel(id="agent-diff-panel")

    def update_display(self, agent: Agent, stale_threshold_seconds: int = 10) -> None:
        """Update panels with agent information.

        For NO CHANGES agents, shows only prompt panel (with reply embedded).
        For NEW CL and NEW PROPOSAL agents, shows prompt and static diff panels.
        For running agents, shows prompt and auto-refreshing diff panels.

        Args:
            agent: The Agent to display.
            stale_threshold_seconds: Diffs older than this are refetched.
        """
        prompt_panel = self.query_one("#agent-prompt-panel", _AgentPromptPanel)
        diff_panel = self.query_one("#agent-diff-panel", _AgentDiffPanel)
        diff_scroll = self.query_one("#agent-diff-scroll", VerticalScroll)
        prompt_scroll = self.query_one("#agent-prompt-scroll", VerticalScroll)

        prompt_panel.update_display(agent)

        if agent.status == "NO CHANGES":
            # Hide diff panel, expand prompt panel (reply is embedded in it)
            diff_scroll.add_class("hidden")
            prompt_scroll.add_class("expanded")
        elif agent.status in ("NEW CL", "NEW PROPOSAL"):
            # Show static diff panel (from saved diff file)
            if agent.diff_path:
                diff_scroll.remove_class("hidden")
                prompt_scroll.remove_class("expanded")
                diff_panel.display_static_diff(agent.diff_path)
            else:
                # No diff path - hide diff panel
                diff_scroll.add_class("hidden")
                prompt_scroll.add_class("expanded")
        else:
            # RUNNING - show auto-refreshing diff panel
            diff_scroll.remove_class("hidden")
            prompt_scroll.remove_class("expanded")
            diff_panel.update_display(
                agent, stale_threshold_seconds=stale_threshold_seconds
            )

    def show_empty(self) -> None:
        """Show empty state for both panels."""
        prompt_panel = self.query_one("#agent-prompt-panel", _AgentPromptPanel)
        diff_panel = self.query_one("#agent-diff-panel", _AgentDiffPanel)

        prompt_panel.show_empty()
        diff_panel.show_empty()

        # Hide diff panel when no agent is selected
        prompt_scroll = self.query_one("#agent-prompt-scroll", VerticalScroll)
        diff_scroll = self.query_one("#agent-diff-scroll", VerticalScroll)
        diff_scroll.add_class("hidden")
        prompt_scroll.add_class("expanded")

    def refresh_current_diff(self, agent: Agent) -> None:
        """Force refresh the diff for the given agent.

        Args:
            agent: The Agent to refresh diff for.
        """
        diff_panel = self.query_one("#agent-diff-panel", _AgentDiffPanel)
        diff_panel.refresh_diff(agent)

    def on__diff_visibility_changed(self, message: _DiffVisibilityChanged) -> None:
        """Handle diff visibility changes.

        Args:
            message: The visibility change message.
        """
        prompt_scroll = self.query_one("#agent-prompt-scroll", VerticalScroll)
        diff_scroll = self.query_one("#agent-diff-scroll", VerticalScroll)

        if message.has_diff:
            # Show diff panel with 30/70 split
            diff_scroll.remove_class("hidden")
            prompt_scroll.remove_class("expanded")
        else:
            # Hide diff panel and expand prompt
            diff_scroll.add_class("hidden")
            prompt_scroll.add_class("expanded")
