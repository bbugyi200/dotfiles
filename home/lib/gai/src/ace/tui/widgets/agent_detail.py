"""Agent detail widget for the ace TUI."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static

from ..models.agent import Agent
from .file_panel import AgentFilePanel, FileVisibilityChanged
from .prompt_panel import AgentPromptPanel


class AgentDetail(Static):
    """Combined widget with prompt and file panels."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the agent detail view."""
        super().__init__(**kwargs)
        self._layout_swapped: bool = False

    def compose(self) -> ComposeResult:
        """Compose the two-panel layout (prompt and file)."""
        with Vertical(id="agent-detail-layout"):
            with VerticalScroll(id="agent-prompt-scroll"):
                yield AgentPromptPanel(id="agent-prompt-panel")
            with VerticalScroll(id="agent-file-scroll"):
                yield AgentFilePanel(id="agent-file-panel")

    def update_display(self, agent: Agent, stale_threshold_seconds: int = 10) -> None:
        """Update panels with agent information.

        For NO CHANGES agents, shows only prompt panel (with reply embedded).
        For NEW CL and NEW PROPOSAL agents, shows prompt and static file panels.
        For running agents, shows prompt and auto-refreshing file panels.

        Args:
            agent: The Agent to display.
            stale_threshold_seconds: Diffs older than this are refetched.
        """
        prompt_panel = self.query_one("#agent-prompt-panel", AgentPromptPanel)
        file_panel = self.query_one("#agent-file-panel", AgentFilePanel)
        file_scroll = self.query_one("#agent-file-scroll", VerticalScroll)
        prompt_scroll = self.query_one("#agent-prompt-scroll", VerticalScroll)

        prompt_panel.update_display(agent)

        # Hide file panel for bash/python workflow steps - they don't have files
        if agent.is_workflow_child and agent.step_type in ("bash", "python"):
            file_scroll.add_class("hidden")
            prompt_scroll.add_class("expanded")
            return

        if agent.status in ("RUNNING", "WAITING INPUT"):
            # Show auto-refreshing file panel for active agents
            # Don't change visibility here - let update_display() handle it
            # via FileVisibilityChanged message after fetching/validating the file
            file_panel.update_display(
                agent, stale_threshold_seconds=stale_threshold_seconds
            )
        else:
            # DONE, FAILED, REVIVED, etc.
            if agent.diff_path:
                file_panel.display_static_file(agent.diff_path)
            else:
                file_scroll.add_class("hidden")
                prompt_scroll.add_class("expanded")

    def show_empty(self) -> None:
        """Show empty state for both panels."""
        prompt_panel = self.query_one("#agent-prompt-panel", AgentPromptPanel)
        file_panel = self.query_one("#agent-file-panel", AgentFilePanel)

        prompt_panel.show_empty()
        file_panel.show_empty()

        # Hide file panel when no agent is selected
        prompt_scroll = self.query_one("#agent-prompt-scroll", VerticalScroll)
        file_scroll = self.query_one("#agent-file-scroll", VerticalScroll)
        file_scroll.add_class("hidden")
        prompt_scroll.add_class("expanded")

    def refresh_current_file(self, agent: Agent) -> None:
        """Force refresh the file for the given agent.

        Args:
            agent: The Agent to refresh file for.
        """
        file_panel = self.query_one("#agent-file-panel", AgentFilePanel)
        file_panel.refresh_file(agent)

    def on_file_visibility_changed(self, message: FileVisibilityChanged) -> None:
        """Handle file panel visibility changes.

        Args:
            message: The visibility change message.
        """
        prompt_scroll = self.query_one("#agent-prompt-scroll", VerticalScroll)
        file_scroll = self.query_one("#agent-file-scroll", VerticalScroll)

        if message.has_file:
            # Show file panel
            file_scroll.remove_class("hidden")
            prompt_scroll.remove_class("expanded")
            # Restore layout preference if swapped
            if self._layout_swapped:
                prompt_scroll.add_class("layout-priority")
                file_scroll.add_class("layout-secondary")
        else:
            # Hide file panel and expand prompt to full height
            file_scroll.add_class("hidden")
            prompt_scroll.add_class("expanded")
            # Remove layout classes so expanded (100%) takes effect
            prompt_scroll.remove_class("layout-priority")
            file_scroll.remove_class("layout-secondary")

    def toggle_layout(self) -> None:
        """Toggle between default (30/70) and swapped (70/30) layout."""
        prompt_scroll = self.query_one("#agent-prompt-scroll", VerticalScroll)
        file_scroll = self.query_one("#agent-file-scroll", VerticalScroll)

        self._layout_swapped = not self._layout_swapped

        if self._layout_swapped:
            prompt_scroll.add_class("layout-priority")
            file_scroll.add_class("layout-secondary")
        else:
            prompt_scroll.remove_class("layout-priority")
            file_scroll.remove_class("layout-secondary")

    def is_file_visible(self) -> bool:
        """Check if the file panel is currently visible.

        Returns:
            True if the file panel is visible, False otherwise.
        """
        file_scroll = self.query_one("#agent-file-scroll", VerticalScroll)
        return not file_scroll.has_class("hidden")

    def is_layout_swapped(self) -> bool:
        """Check if the layout is currently swapped.

        Returns:
            True if prompt has priority (70/30), False if default (30/70).
        """
        return self._layout_swapped
