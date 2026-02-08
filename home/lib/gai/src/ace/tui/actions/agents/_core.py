"""Core agent display and interaction methods for the ace TUI app."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from ._folding import AgentFoldingMixin
from ._interaction import AgentInteractionMixin
from ._killing import AgentKillingMixin
from ._notifications import AgentNotificationMixin
from ._revival import AgentRevivalMixin
from ._workflow_hitl import AgentWorkflowHITLMixin

if TYPE_CHECKING:
    from ...models import Agent
    from ...models.agent import AgentType
    from ...models.fold_state import FoldStateManager

# Import ChangeSpec unconditionally since it's used as a type annotation
# in attribute declarations (not just in function signatures)
from ....changespec import ChangeSpec

# Type alias for tab names
TabName = Literal["changespecs", "agents", "axe"]

# Statuses that indicate an agent is dismissable (shows "x dismiss" in footer)
DISMISSABLE_STATUSES = {
    "DONE",
    "REVIVED",
    "FAILED",
}


def _is_always_visible(agent: Agent) -> bool:
    """Check if agent should always be visible (dismissable or running).

    Args:
        agent: The agent to check.

    Returns:
        True if agent should always be visible, False if it's hideable.
    """
    from ...models.agent import AgentType

    # Workflow children: visibility managed by fold state, not hide toggle
    if agent.is_workflow_child:
        return True

    # Axe-spawned agents are hideable (hidden by default, shown with '.' toggle)
    if is_axe_spawned_agent(agent):
        return False

    return (
        agent.agent_type in (AgentType.RUNNING, AgentType.WORKFLOW)
        or agent.status in DISMISSABLE_STATUSES
    )


def is_axe_spawned_agent(agent: Agent) -> bool:
    """Check if agent was spawned by gai axe (not user-initiated).

    Agents spawned by axe should not trigger notifications since they're
    automated background tasks.

    Args:
        agent: The agent to check.

    Returns:
        True if agent was spawned by axe, False if user-initiated.
    """
    from ...models.agent import AgentType

    # Hook-based types are always axe-spawned
    if agent.agent_type in (
        AgentType.FIX_HOOK,
        AgentType.SUMMARIZE,
        AgentType.MENTOR,
        AgentType.CRS,
    ):
        return True

    # RUNNING/WORKFLOW types spawned by axe have specific workflow patterns
    if agent.agent_type in (AgentType.RUNNING, AgentType.WORKFLOW):
        if agent.workflow:
            # axe-spawned workflows start with axe(...)
            if agent.workflow.startswith(("axe(mentor)", "axe(fix-hook)", "axe(crs)")):
                return True
            # Plain workflow names for axe-spawned types (from workflow_state.json)
            if agent.workflow in ("fix-hook", "crs", "mentor", "summarize-hook"):
                return True

    return False


class AgentsMixinCore(
    AgentFoldingMixin,
    AgentInteractionMixin,
    AgentWorkflowHITLMixin,
    AgentNotificationMixin,
    AgentKillingMixin,
    AgentRevivalMixin,
):
    """Core mixin providing agent loading, display, and user interaction methods.

    Type hints below declare attributes that are defined at runtime by AceApp.
    """

    # ChangeSpec state
    changespecs: list[ChangeSpec]
    current_idx: int
    current_tab: TabName
    refresh_interval: int
    hide_non_run_agents: bool
    _countdown_remaining: int
    _agents: list[Agent]
    _agents_last_idx: int
    _revived_agents: list[Agent]
    _has_always_visible: bool
    _hidden_count: int

    # Fold state for workflow steps
    _fold_manager: FoldStateManager
    _fold_counts: dict[str, tuple[int, int]]

    # Agent completion tracking for notifications
    _tracked_running_agents: set[tuple[AgentType, str, str | None]]
    _pending_attention_count: int
    _viewed_agents: set[tuple[AgentType, str, str | None]]
    _dismissed_agents: set[tuple[AgentType, str, str | None]]

    def _load_agents(self) -> None:
        """Load agents from all sources including revived agents."""
        from ...models import load_all_agents
        from ...models.agent import AgentType

        # Only capture selection identity if we're on the agents tab
        # (current_idx refers to changespecs when on changespecs tab)
        on_agents_tab = self.current_tab == "agents"

        selected_identity: tuple[AgentType, str, str | None] | None = None
        if on_agents_tab and self._agents and 0 <= self.current_idx < len(self._agents):
            selected_identity = self._agents[self.current_idx].identity

        # Load fresh agent list
        all_agents = load_all_agents()

        # Merge revived agents (they appear at the end of the list)
        all_agents.extend(self._revived_agents)

        # Filter out dismissed agents
        all_agents = [a for a in all_agents if a.identity not in self._dismissed_agents]

        # Categorize agents: always-visible (dismissable OR running) vs hideable
        always_visible = [a for a in all_agents if _is_always_visible(a)]
        hideable = [a for a in all_agents if not _is_always_visible(a)]

        self._has_always_visible = len(always_visible) > 0
        self._hidden_count = 0

        # Filter if we have always-visible agents and hiding is enabled
        if self._has_always_visible and self.hide_non_run_agents and hideable:
            self._agents = always_visible
            self._hidden_count = len(hideable)
        else:
            self._agents = all_agents

        # Apply fold-state filtering for workflow children
        from ...models import filter_agents_by_fold_state

        self._agents, self._fold_counts = filter_agents_by_fold_state(
            self._agents, self._fold_manager
        )

        # Calculate the new index
        # Use current_idx when on agents tab, otherwise use saved _agents_last_idx
        saved_idx = self.current_idx if on_agents_tab else self._agents_last_idx

        if selected_identity is not None:
            # Try to restore selection by identity
            for idx, agent in enumerate(self._agents):
                if agent.identity == selected_identity:
                    saved_idx = idx
                    break
            # If agent not found, saved_idx remains at the original position

        # Clamp to valid bounds
        if self._agents:
            new_idx = min(saved_idx, len(self._agents) - 1)
        else:
            new_idx = 0

        # Only modify current_idx if we're on the agents tab
        # Otherwise, update the saved position for when user switches to agents tab
        if on_agents_tab:
            self.current_idx = new_idx
        else:
            self._agents_last_idx = new_idx

        # Only refresh display if on agents tab
        if on_agents_tab:
            self._refresh_agents_display()

    def _refresh_agents_display(self) -> None:
        """Refresh the agents tab display."""
        from ...widgets import AgentDetail, AgentList, KeybindingFooter

        agent_list = self.query_one("#agent-list-panel", AgentList)  # type: ignore[attr-defined]
        agent_detail = self.query_one("#agent-detail-panel", AgentDetail)  # type: ignore[attr-defined]
        footer_widget = self.query_one("#keybinding-footer", KeybindingFooter)  # type: ignore[attr-defined]

        agent_list.update_list(
            self._agents, self.current_idx, fold_counts=self._fold_counts
        )

        current_agent = None
        if self._agents and 0 <= self.current_idx < len(self._agents):
            current_agent = self._agents[self.current_idx]
            agent_detail.update_display(
                current_agent, stale_threshold_seconds=self.refresh_interval
            )
        else:
            agent_detail.show_empty()

        # Query file visibility for footer (must be done after update_display)
        file_visible = agent_detail.is_file_visible()

        # Determine if any foldable workflows exist (for fold keybindings)
        has_foldable = any(
            key for key, (non_hidden, _) in self._fold_counts.items() if non_hidden > 0
        )

        footer_widget.update_agent_bindings(
            current_agent,
            file_visible=file_visible,
            has_always_visible=self._has_always_visible,
            hidden_count=self._hidden_count,
            hide_non_run=self.hide_non_run_agents,
            has_foldable=has_foldable,
        )

        self._update_agents_info_panel()

    def _toggle_hide_non_run_agents(self) -> None:
        """Toggle visibility of non-run agents and refresh the display."""
        self.hide_non_run_agents = not self.hide_non_run_agents
        self._load_agents()

    def _update_agents_info_panel(self) -> None:
        """Update the agents info panel with current position and countdown."""
        from ...widgets import AgentInfoPanel

        agent_info_panel = self.query_one("#agent-info-panel", AgentInfoPanel)  # type: ignore[attr-defined]
        # Position is 1-based for display (current_idx is 0-based)
        position = self.current_idx + 1 if self._agents else 0
        agent_info_panel.update_position(position, len(self._agents))
        agent_info_panel.update_countdown(
            self._countdown_remaining, self.refresh_interval
        )
