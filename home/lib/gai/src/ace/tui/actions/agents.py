"""Agent display mixin for the ace TUI app."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ...changespec import ChangeSpec
    from ..models import Agent

# Type alias for tab names
TabName = Literal["changespecs", "agents"]


class AgentsMixin:
    """Mixin providing agent loading and display methods."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    current_idx: int
    current_tab: TabName
    refresh_interval: int
    _countdown_remaining: int
    _agents: list[Agent]

    def _load_agents(self) -> None:
        """Load agents from all sources."""
        from ..models import load_all_agents

        self._agents = load_all_agents()

        # Clamp current_idx to bounds (preserves position on refresh)
        if self._agents:
            if self.current_idx >= len(self._agents):
                self.current_idx = len(self._agents) - 1
        else:
            self.current_idx = 0

        self._refresh_agents_display()

    def _refresh_agents_display(self) -> None:
        """Refresh the agents tab display."""
        from ..widgets import AgentDetail, AgentList, KeybindingFooter

        agent_list = self.query_one("#agent-list-panel", AgentList)  # type: ignore[attr-defined]
        agent_detail = self.query_one("#agent-detail-panel", AgentDetail)  # type: ignore[attr-defined]
        footer_widget = self.query_one("#keybinding-footer", KeybindingFooter)  # type: ignore[attr-defined]

        agent_list.update_list(self._agents, self.current_idx)

        current_agent = None
        if self._agents and 0 <= self.current_idx < len(self._agents):
            current_agent = self._agents[self.current_idx]
            agent_detail.update_display(
                current_agent, stale_threshold_seconds=self.refresh_interval
            )
        else:
            agent_detail.show_empty()

        footer_widget.update_agent_bindings(
            current_agent,
            self.current_idx,
            len(self._agents),
        )

        self._update_agents_info_panel()

    def _update_agents_info_panel(self) -> None:
        """Update the agents info panel with current position and countdown."""
        from ..widgets import AgentInfoPanel

        agent_info_panel = self.query_one("#agent-info-panel", AgentInfoPanel)  # type: ignore[attr-defined]
        # Position is 1-based for display (current_idx is 0-based)
        position = self.current_idx + 1 if self._agents else 0
        agent_info_panel.update_position(position, len(self._agents))
        agent_info_panel.update_countdown(
            self._countdown_remaining, self.refresh_interval
        )

    def action_show_diff(self) -> None:
        """Show diff - behavior depends on current tab."""
        if self.current_tab == "agents":
            self._refresh_agent_diff()
        else:
            # Call parent implementation for ChangeSpecs
            super().action_show_diff()  # type: ignore[misc]

    def _refresh_agent_diff(self) -> None:
        """Refresh the diff for the currently selected agent."""
        from ..widgets import AgentDetail

        if not self._agents or not (0 <= self.current_idx < len(self._agents)):
            self.notify("No agent selected", severity="warning")  # type: ignore[attr-defined]
            return

        agent = self._agents[self.current_idx]
        agent_detail = self.query_one("#agent-detail-panel", AgentDetail)  # type: ignore[attr-defined]
        agent_detail.refresh_current_diff(agent)
        self.notify("Refreshing diff...")  # type: ignore[attr-defined]
