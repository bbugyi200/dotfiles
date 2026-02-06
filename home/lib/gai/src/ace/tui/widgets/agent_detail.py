"""Agent detail widget for the ace TUI."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static

from ..models.agent import Agent
from .diff_panel import AgentDiffPanel, DiffVisibilityChanged
from .prompt_panel import AgentPromptPanel


class AgentDetail(Static):
    """Combined widget with prompt and diff panels."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the agent detail view."""
        super().__init__(**kwargs)
        self._layout_swapped: bool = False

    def compose(self) -> ComposeResult:
        """Compose the two-panel layout (prompt and diff)."""
        with Vertical(id="agent-detail-layout"):
            with VerticalScroll(id="agent-prompt-scroll"):
                yield AgentPromptPanel(id="agent-prompt-panel")
            with VerticalScroll(id="agent-diff-scroll"):
                yield AgentDiffPanel(id="agent-diff-panel")

    def update_display(self, agent: Agent, stale_threshold_seconds: int = 10) -> None:
        """Update panels with agent information.

        For NO CHANGES agents, shows only prompt panel (with reply embedded).
        For NEW CL and NEW PROPOSAL agents, shows prompt and static diff panels.
        For running agents, shows prompt and auto-refreshing diff panels.

        Args:
            agent: The Agent to display.
            stale_threshold_seconds: Diffs older than this are refetched.
        """
        prompt_panel = self.query_one("#agent-prompt-panel", AgentPromptPanel)
        diff_panel = self.query_one("#agent-diff-panel", AgentDiffPanel)
        diff_scroll = self.query_one("#agent-diff-scroll", VerticalScroll)
        prompt_scroll = self.query_one("#agent-prompt-scroll", VerticalScroll)

        prompt_panel.update_display(agent)

        # Hide diff panel for bash/python workflow steps - they don't have diffs
        if agent.is_workflow_child and agent.step_type in ("bash", "python"):
            diff_scroll.add_class("hidden")
            prompt_scroll.add_class("expanded")
            return

        if agent.status in ("RUNNING", "WAITING INPUT"):
            # Show auto-refreshing diff panel for active agents
            # Don't change visibility here - let update_display() handle it
            # via DiffVisibilityChanged message after fetching/validating the diff
            diff_panel.update_display(
                agent, stale_threshold_seconds=stale_threshold_seconds
            )
        else:
            # DONE, FAILED, REVIVED, etc. — no meaningful diff to show
            diff_scroll.add_class("hidden")
            prompt_scroll.add_class("expanded")

    def show_empty(self) -> None:
        """Show empty state for both panels."""
        prompt_panel = self.query_one("#agent-prompt-panel", AgentPromptPanel)
        diff_panel = self.query_one("#agent-diff-panel", AgentDiffPanel)

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
        diff_panel = self.query_one("#agent-diff-panel", AgentDiffPanel)
        diff_panel.refresh_diff(agent)

    def on_diff_visibility_changed(self, message: DiffVisibilityChanged) -> None:
        """Handle diff visibility changes.

        Args:
            message: The visibility change message.
        """
        prompt_scroll = self.query_one("#agent-prompt-scroll", VerticalScroll)
        diff_scroll = self.query_one("#agent-diff-scroll", VerticalScroll)

        if message.has_diff:
            # Show diff panel
            diff_scroll.remove_class("hidden")
            prompt_scroll.remove_class("expanded")
            # Restore layout preference if swapped
            if self._layout_swapped:
                prompt_scroll.add_class("layout-priority")
                diff_scroll.add_class("layout-secondary")
        else:
            # Hide diff panel and expand prompt to full height
            diff_scroll.add_class("hidden")
            prompt_scroll.add_class("expanded")
            # Remove layout classes so expanded (100%) takes effect
            prompt_scroll.remove_class("layout-priority")
            diff_scroll.remove_class("layout-secondary")

    def toggle_layout(self) -> None:
        """Toggle between default (30/70) and swapped (70/30) layout."""
        prompt_scroll = self.query_one("#agent-prompt-scroll", VerticalScroll)
        diff_scroll = self.query_one("#agent-diff-scroll", VerticalScroll)

        self._layout_swapped = not self._layout_swapped

        if self._layout_swapped:
            prompt_scroll.add_class("layout-priority")
            diff_scroll.add_class("layout-secondary")
        else:
            prompt_scroll.remove_class("layout-priority")
            diff_scroll.remove_class("layout-secondary")

    def is_diff_visible(self) -> bool:
        """Check if the diff panel is currently visible.

        Returns:
            True if the diff panel is visible, False otherwise.
        """
        diff_scroll = self.query_one("#agent-diff-scroll", VerticalScroll)
        return not diff_scroll.has_class("hidden")

    def is_layout_swapped(self) -> bool:
        """Check if the layout is currently swapped.

        Returns:
            True if prompt has priority (70/30), False if default (30/70).
        """
        return self._layout_swapped
