"""Agent file panel widget for the ace TUI."""

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.syntax import Syntax
from rich.text import Text
from running_field import get_workspace_directory
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Static
from textual.worker import Worker, WorkerState

from ..models.agent import Agent


class FileVisibilityChanged(Message):
    """Message posted when file panel visibility should change."""

    def __init__(self, has_file: bool) -> None:
        """Initialize the message.

        Args:
            has_file: True if there is a file to display, False if empty.
        """
        super().__init__()
        self.has_file = has_file


@dataclass
class _FileCacheEntry:
    """Cache entry for agent file output."""

    diff_output: str | None
    fetch_time: datetime


# Module-level cache for file outputs
_file_cache: dict[str, _FileCacheEntry] = {}


def _get_cache_key(agent: Agent) -> str:
    """Generate a unique cache key for an agent's file output.

    Includes agent type and workspace to ensure different agents
    don't share cached files incorrectly.
    """
    if agent.workspace_num is not None:
        return f"{agent.cl_name}:{agent.agent_type.value}:{agent.workspace_num}"
    return f"{agent.cl_name}:{agent.agent_type.value}"


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


class AgentFilePanel(Static):
    """Bottom panel showing agent file output (diffs, markdown, etc.)."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the file panel."""
        super().__init__(**kwargs)
        self._current_agent: Agent | None = None
        self._current_worker: Worker[str | None] | None = None
        self._has_displayed_content: bool = False
        self._last_file_content: str | None = None
        self._is_background_refreshing: bool = False

    def update_display(self, agent: Agent, stale_threshold_seconds: int = 10) -> None:
        """Update with agent file output.

        Args:
            agent: The Agent to display file for.
            stale_threshold_seconds: Files older than this are refetched.
        """
        self._current_agent = agent

        # Check cache
        cache_key = _get_cache_key(agent)
        cache_entry = _file_cache.get(cache_key)

        if cache_entry is not None:
            age_seconds = (datetime.now() - cache_entry.fetch_time).total_seconds()
            if age_seconds < stale_threshold_seconds:
                # Cache is fresh - use it directly
                self._display_file_with_timestamp(
                    cache_entry.diff_output,
                    cache_entry.fetch_time,
                    post_visibility_message=True,
                )
                return

            # Cache is stale - display stale content while fetching in background
            self._is_background_refreshing = True
            self._display_file_with_timestamp(
                cache_entry.diff_output,
                cache_entry.fetch_time,
                post_visibility_message=True,
                is_stale=True,
            )
        else:
            # No cache - show loading for first-time loads
            self._show_loading()

        # Cancel any existing worker
        if self._current_worker is not None and self._current_worker.is_running:
            self._current_worker.cancel()

        # Start background worker using closure to capture agent
        def fetch_task() -> str | None:
            return self._fetch_file_in_background(agent)

        self._current_worker = self.run_worker(fetch_task, thread=True)

    def refresh_file(self, agent: Agent) -> None:
        """Force refresh the file for an agent.

        Args:
            agent: The Agent to refresh file for.
        """
        self._current_agent = agent

        # Check for existing cache to display while refreshing
        cache_key = _get_cache_key(agent)
        cache_entry = _file_cache.get(cache_key)

        if cache_entry is not None:
            # Show existing content with "(refreshing...)" indicator
            self._is_background_refreshing = True
            self._display_file_with_timestamp(
                cache_entry.diff_output,
                cache_entry.fetch_time,
                post_visibility_message=True,
                is_stale=True,
            )
        else:
            # No cache - show loading for first-time loads
            self._show_loading()

        # Cancel any existing worker
        if self._current_worker is not None and self._current_worker.is_running:
            self._current_worker.cancel()

        # Start background worker using closure to capture agent
        def fetch_task() -> str | None:
            return self._fetch_file_in_background(agent)

        self._current_worker = self.run_worker(fetch_task, thread=True)

    def _show_loading(self) -> None:
        """Display loading indicator only if panel was previously visible."""
        if not self._has_displayed_content:
            return
        text = Text()
        text.append("Loading file...\n", style="bold #87D7FF")
        text.append("Please wait while fetching changes.", style="dim")
        self.update(text)

    def _get_scroll_container(self) -> VerticalScroll | None:
        """Get the parent scroll container for this file panel.

        Returns:
            The VerticalScroll container, or None if not found.
        """
        try:
            return self.app.query_one("#agent-file-scroll", VerticalScroll)
        except Exception:
            return None

    def _save_scroll_position(self) -> float:
        """Save the current scroll position.

        Returns:
            The current scroll Y position, or 0 if unavailable.
        """
        container = self._get_scroll_container()
        if container is not None:
            return container.scroll_y
        return 0.0

    def _restore_scroll_position(self, position: float) -> None:
        """Restore a previously saved scroll position.

        Args:
            position: The scroll Y position to restore.
        """
        container = self._get_scroll_container()
        if container is not None:
            self.call_after_refresh(
                lambda: container.scroll_to(y=position, animate=False)
            )

    def _display_file_with_timestamp(
        self,
        diff_output: str | None,
        fetch_time: datetime,
        *,
        post_visibility_message: bool = True,
        is_stale: bool = False,
    ) -> None:
        """Display file output with fetch timestamp.

        Args:
            diff_output: The diff output or None if no changes.
            fetch_time: When the file was fetched.
            post_visibility_message: Whether to post visibility change message.
                Set to False when displaying cached data to avoid flicker.
            is_stale: Whether the content is stale (showing while refreshing).
        """
        # Track last displayed content for change detection
        self._last_file_content = diff_output

        # Post visibility message to parent (only for fresh fetches to avoid flicker)
        if post_visibility_message:
            self.post_message(FileVisibilityChanged(has_file=diff_output is not None))

        # Build refresh indicator if stale and background refreshing
        refresh_indicator = ""
        if is_stale and self._is_background_refreshing:
            refresh_indicator = " (refreshing...)"

        if diff_output:
            # For simplicity, prepend timestamp to the diff output
            diff_with_header = (
                f"# Last fetched: {fetch_time.strftime('%H:%M:%S')}"
                f"{refresh_indicator}\n\n{diff_output}"
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
            if refresh_indicator:
                text.append(refresh_indicator, style="dim italic")
            text.append("\n\n")
            text.append("No changes detected.\n", style="dim italic")
            self.update(text)

        self._has_displayed_content = True

    def _fetch_file_in_background(self, agent: Agent) -> str | None:
        """Fetch file output in background thread.

        Args:
            agent: The agent to get file for.

        Returns:
            File output string, or None if unavailable.
        """
        diff_output = self._get_agent_diff(agent)

        # Store in cache
        cache_key = _get_cache_key(agent)
        _file_cache[cache_key] = _FileCacheEntry(
            diff_output=diff_output,
            fetch_time=datetime.now(),
        )

        return diff_output

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        if event.worker != self._current_worker:
            return

        # Always clear background refreshing flag when worker completes
        self._is_background_refreshing = False

        if event.state == WorkerState.SUCCESS:
            # Worker completed - display result from cache
            if self._current_agent:
                cache_key = _get_cache_key(self._current_agent)
                if cache_key in _file_cache:
                    cache_entry = _file_cache[cache_key]

                    # Skip update if content hasn't changed
                    if cache_entry.diff_output == self._last_file_content:
                        # Content unchanged - just update timestamp without scroll reset
                        # Re-display to update the timestamp (removes "refreshing...")
                        scroll_pos = self._save_scroll_position()
                        self._display_file_with_timestamp(
                            cache_entry.diff_output,
                            cache_entry.fetch_time,
                            post_visibility_message=False,
                        )
                        self._restore_scroll_position(scroll_pos)
                    else:
                        # Content changed - save scroll, update, restore scroll
                        scroll_pos = self._save_scroll_position()
                        self._display_file_with_timestamp(
                            cache_entry.diff_output, cache_entry.fetch_time
                        )
                        self._restore_scroll_position(scroll_pos)
        elif event.state == WorkerState.ERROR:
            # Show error state
            text = Text()
            text.append("Error fetching file\n", style="bold red")
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

            if agent.workspace_num:
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
                return result.stdout
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
        except Exception:
            text = Text("Could not read diff file.\n", style="dim italic")
            self.update(text)
            self.post_message(FileVisibilityChanged(has_file=False))
            return

        if not diff_content.strip():
            text = Text("Diff file is empty.\n", style="dim italic")
            self.update(text)
            self.post_message(FileVisibilityChanged(has_file=False))
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
        self.post_message(FileVisibilityChanged(has_file=True))

    def display_static_file(self, file_path: str) -> None:
        """Display a static file with syntax highlighting (no auto-refresh).

        Auto-detects the lexer from the file extension.

        Args:
            file_path: Path to the file (may use ~ for home).
        """
        expanded_path = os.path.expanduser(file_path)
        try:
            with open(expanded_path, encoding="utf-8") as f:
                content = f.read()
        except Exception:
            text = Text("Could not read file.\n", style="dim italic")
            self.update(text)
            self.post_message(FileVisibilityChanged(has_file=False))
            return

        if not content.strip():
            text = Text("File is empty.\n", style="dim italic")
            self.update(text)
            self.post_message(FileVisibilityChanged(has_file=False))
            return

        # Detect lexer from file extension
        _, ext = os.path.splitext(expanded_path)
        lexer = _EXTENSION_TO_LEXER.get(ext.lower(), "text")

        syntax = Syntax(
            content,
            lexer,
            theme="monokai",
            line_numbers=True,
            word_wrap=True,
        )
        self.update(syntax)
        self._has_displayed_content = True
        self.post_message(FileVisibilityChanged(has_file=True))
