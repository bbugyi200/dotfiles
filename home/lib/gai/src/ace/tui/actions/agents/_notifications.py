"""Agent completion tracking and notification methods for the ace TUI app."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ...models import Agent
    from ...models.agent import AgentType

# Type alias for tab names
TabName = Literal["changespecs", "agents", "axe"]


class AgentNotificationMixin:
    """Mixin providing agent completion tracking and notification methods.

    Type hints below declare attributes that are defined at runtime by AceApp.
    """

    _tracked_running_agents: set[tuple[AgentType, str, str | None]]
    _pending_attention_count: int
    _viewed_agents: set[tuple[AgentType, str, str | None]]
    _dismissed_agents: set[tuple[AgentType, str, str | None]]
    _revived_agents: list[Agent]
    current_tab: TabName

    def _poll_agent_completions(self) -> None:
        """Poll agents for completions and update notification state.

        Detects when user-initiated agents complete and triggers notifications.
        Called on every auto-refresh regardless of current tab.
        """
        from ...models import load_all_agents
        from ...models.agent import AgentType
        from ._core import DISMISSABLE_STATUSES, is_axe_spawned_agent

        all_agents = load_all_agents()
        all_agents.extend(self._revived_agents)

        current_running: set[tuple[AgentType, str, str | None]] = set()
        current_dismissible_non_axe: set[tuple[AgentType, str, str | None]] = set()

        for agent in all_agents:
            # Skip workflow children — only top-level agents trigger notifications
            if agent.is_workflow_child:
                continue
            is_axe = is_axe_spawned_agent(agent)
            is_dismissible = agent.status in DISMISSABLE_STATUSES

            if not is_dismissible:
                current_running.add(agent.identity)
            elif not is_axe:
                current_dismissible_non_axe.add(agent.identity)

        # Detect newly completed (was running, now dismissible non-axe)
        newly_completed = self._tracked_running_agents & current_dismissible_non_axe

        if newly_completed:
            self._ring_tmux_bell()

        self._tracked_running_agents = current_running

        # Only count agents that haven't been viewed yet
        unviewed_dismissible = current_dismissible_non_axe - self._viewed_agents
        self._pending_attention_count = len(unviewed_dismissible)

        if self.current_tab != "agents":
            self._update_tab_bar_emphasis()
        else:
            # Mark all dismissable agents as viewed when on agents tab and persist
            self._viewed_agents.update(current_dismissible_non_axe)
            from ...viewed_agents import save_viewed_agents

            save_viewed_agents(self._viewed_agents)
            self._clear_tab_bar_emphasis()

    def _ring_tmux_bell(self) -> None:
        """Ring tmux bell to notify user of agent completion."""
        import os
        import subprocess

        # Get current tmux pane from environment
        tmux_pane = os.environ.get("TMUX_PANE")
        if not tmux_pane:
            return  # Not in tmux

        try:
            subprocess.run(
                ["tmux_ring_bell", tmux_pane, "3", "0.1"],
                check=False,
                capture_output=True,
            )
        except FileNotFoundError:
            pass  # Script not available

    def _update_tab_bar_emphasis(self) -> None:
        """Update tab bar with attention count badge."""
        from ...widgets import TabBar

        tab_bar = self.query_one("#tab-bar", TabBar)  # type: ignore[attr-defined]
        tab_bar.set_attention_count(self._pending_attention_count)

    def _clear_tab_bar_emphasis(self) -> None:
        """Clear tab bar attention badge."""
        from ...widgets import TabBar

        tab_bar = self.query_one("#tab-bar", TabBar)  # type: ignore[attr-defined]
        tab_bar.set_attention_count(0)

    def _mark_current_agents_as_viewed(self) -> None:
        """Mark all current dismissable non-axe agents as viewed immediately.

        This is called when switching to the agents tab to ensure agents are
        marked as viewed right away, rather than waiting for the next auto-refresh.
        This prevents the badge from reappearing when quickly switching away.
        """
        from ...models import load_all_agents
        from ...models.agent import AgentType
        from ...viewed_agents import save_viewed_agents
        from ._core import DISMISSABLE_STATUSES, is_axe_spawned_agent

        all_agents = load_all_agents()
        all_agents.extend(self._revived_agents)

        # Collect all dismissable non-axe agents
        current_dismissible_non_axe: set[tuple[AgentType, str, str | None]] = set()
        for agent in all_agents:
            # Skip workflow children — only top-level agents trigger notifications
            if agent.is_workflow_child:
                continue
            is_axe = is_axe_spawned_agent(agent)
            is_dismissible = agent.status in DISMISSABLE_STATUSES

            if is_dismissible and not is_axe:
                current_dismissible_non_axe.add(agent.identity)

        # Update viewed agents and persist to disk
        self._viewed_agents.update(current_dismissible_non_axe)
        save_viewed_agents(self._viewed_agents)
