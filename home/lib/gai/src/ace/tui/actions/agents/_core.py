"""Core agent display and interaction methods for the ace TUI app."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from ._killing import AgentKillingMixin
from ._revival import AgentRevivalMixin

if TYPE_CHECKING:
    from ...models import Agent

# Import ChangeSpec unconditionally since it's used as a type annotation
# in attribute declarations (not just in function signatures)
from ....changespec import ChangeSpec

# Type alias for tab names
TabName = Literal["changespecs", "agents", "axe"]

# Statuses that indicate an agent is dismissable (shows "x dismiss" in footer)
DISMISSABLE_STATUSES = {
    "NO CHANGES",
    "NEW CL",
    "NEW PROPOSAL",
    "REVIVED",
    "COMPLETED",
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

    return agent.agent_type == AgentType.RUNNING or agent.status in DISMISSABLE_STATUSES


class AgentsMixinCore(
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

    def action_kill_agent(self) -> None:
        """Kill or dismiss agent, or clear AXE output depending on tab."""
        if self.current_tab == "axe":
            self.action_clear_axe_output()  # type: ignore[attr-defined]
            return
        if self.current_tab != "agents":
            return

        if not self._agents or not (0 <= self.current_idx < len(self._agents)):
            self.notify("No agent selected", severity="warning")  # type: ignore[attr-defined]
            return

        agent = self._agents[self.current_idx]

        # Handle completed/revived agents with dismiss (no confirmation needed)
        if agent.status in DISMISSABLE_STATUSES:
            self._dismiss_done_agent(agent)
            return

        if agent.pid is None:
            self.notify("Agent has no PID", severity="warning")  # type: ignore[attr-defined]
            return

        # Build description for confirmation dialog
        desc_parts = [f"Type: {agent.agent_type.value}"]
        desc_parts.append(f"CL: {agent.cl_name}")
        if agent.workspace_num is not None:
            desc_parts.append(f"Workspace: #{agent.workspace_num}")
        desc_parts.append(f"PID: {agent.pid}")
        agent_description = "\n".join(desc_parts)

        # Show confirmation modal
        from ...modals import ConfirmKillModal

        def on_dismiss(confirmed: bool | None) -> None:
            if confirmed:
                self._do_kill_agent(agent)

        self.push_screen(ConfirmKillModal(agent_description), on_dismiss)  # type: ignore[attr-defined]

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

        agent_list.update_list(self._agents, self.current_idx)

        current_agent = None
        if self._agents and 0 <= self.current_idx < len(self._agents):
            current_agent = self._agents[self.current_idx]
            agent_detail.update_display(
                current_agent, stale_threshold_seconds=self.refresh_interval
            )
        else:
            agent_detail.show_empty()

        # Query diff visibility for footer (must be done after update_display)
        diff_visible = agent_detail.is_diff_visible()

        footer_widget.update_agent_bindings(
            current_agent,
            diff_visible=diff_visible,
            has_always_visible=self._has_always_visible,
            hidden_count=self._hidden_count,
            hide_non_run=self.hide_non_run_agents,
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

    def action_show_diff(self) -> None:
        """Show diff - behavior depends on current tab."""
        if self.current_tab == "agents":
            self._refresh_agent_diff()
        else:
            # Call parent implementation for ChangeSpecs
            super().action_show_diff()  # type: ignore[misc]

    def _refresh_agent_diff(self) -> None:
        """Refresh the diff for the currently selected agent."""
        from ...widgets import AgentDetail

        if not self._agents or not (0 <= self.current_idx < len(self._agents)):
            self.notify("No agent selected", severity="warning")  # type: ignore[attr-defined]
            return

        agent = self._agents[self.current_idx]
        agent_detail = self.query_one("#agent-detail-panel", AgentDetail)  # type: ignore[attr-defined]
        agent_detail.refresh_current_diff(agent)

    def action_edit_spec(self) -> None:
        """Edit spec/chat - behavior depends on current tab."""
        if self.current_tab == "agents":
            self._open_agent_chat()
        else:
            # Call parent implementation for ChangeSpecs
            super().action_edit_spec()  # type: ignore[misc]

    def _open_agent_chat(self) -> None:
        """Open the agent's chat file in $EDITOR."""
        import os
        import subprocess

        if not self._agents or not (0 <= self.current_idx < len(self._agents)):
            self.notify("No agent selected", severity="warning")  # type: ignore[attr-defined]
            return

        agent = self._agents[self.current_idx]

        # Only available for completed or revived agents
        if agent.status not in ("NO CHANGES", "NEW CL", "NEW PROPOSAL", "REVIVED"):
            self.notify("Agent not finished yet", severity="warning")  # type: ignore[attr-defined]
            return

        if not agent.response_path:
            self.notify("No chat file found", severity="warning")  # type: ignore[attr-defined]
            return

        editor = os.environ.get("EDITOR", "vi")
        file_path = os.path.expanduser(agent.response_path)

        with self.suspend():  # type: ignore[attr-defined]
            subprocess.run([editor, file_path], check=False)

    def action_toggle_layout(self) -> None:
        """Toggle the layout between prompt-priority and diff-priority."""
        if self.current_tab != "agents":
            return

        from ...widgets import AgentDetail

        agent_detail = self.query_one("#agent-detail-panel", AgentDetail)  # type: ignore[attr-defined]

        if not agent_detail.is_diff_visible():
            self.notify("No diff panel to toggle", severity="warning")  # type: ignore[attr-defined]
            return

        agent_detail.toggle_layout()

    def _answer_workflow_hitl(self, agent: Agent) -> None:
        """Answer a workflow HITL prompt.

        Reads the hitl_request.json file, shows a modal with options,
        and writes the response to hitl_response.json.

        Args:
            agent: The workflow agent with WAITING INPUT status.
        """
        import json
        from pathlib import Path

        from ...modals import WorkflowHITLInput, WorkflowHITLModal
        from ...models.agent import AgentType

        if agent.agent_type != AgentType.WORKFLOW:
            self.notify("Not a workflow agent", severity="error")  # type: ignore[attr-defined]
            return

        if agent.raw_suffix is None:
            self.notify("Cannot find workflow artifacts", severity="error")  # type: ignore[attr-defined]
            return

        # Extract project name from project_file
        project_path = Path(agent.project_file)
        project_name = project_path.parent.name

        # Build path to hitl_request.json
        artifacts_dir = (
            Path.home()
            / ".gai"
            / "projects"
            / project_name
            / "artifacts"
            / f"workflow-{agent.workflow}"
            / agent.raw_suffix
        )
        request_path = artifacts_dir / "hitl_request.json"

        if not request_path.exists():
            self.notify("No HITL request found", severity="warning")  # type: ignore[attr-defined]
            return

        # Read the request file
        try:
            with open(request_path, encoding="utf-8") as f:
                request_data = json.load(f)
        except Exception as e:
            self.notify(f"Error reading HITL request: {e}", severity="error")  # type: ignore[attr-defined]
            return

        # Create input data for modal
        input_data = WorkflowHITLInput(
            step_name=request_data.get("step_name", "unknown"),
            step_type=request_data.get("step_type", "agent"),
            output=request_data.get("output", {}),
            workflow_name=agent.workflow or "unknown",
        )

        # Show the HITL modal
        def on_dismiss(result: object) -> None:
            from xprompt import HITLResult

            if result is None:
                return

            # Verify result is HITLResult
            if not isinstance(result, HITLResult):
                return

            # Write response file
            response_path = artifacts_dir / "hitl_response.json"
            response_data = {
                "action": result.action,
                "approved": result.approved,
            }
            if result.edited_output is not None:
                response_data["edited_output"] = result.edited_output
            if result.feedback is not None:
                response_data["feedback"] = result.feedback

            try:
                with open(response_path, "w", encoding="utf-8") as f:
                    json.dump(response_data, f, indent=2, default=str)
                self.notify(f"Sent {result.action} response")  # type: ignore[attr-defined]
            except Exception as e:
                self.notify(f"Error writing response: {e}", severity="error")  # type: ignore[attr-defined]

            # Refresh agents after a short delay to pick up status change
            self.call_later(self._load_agents)  # type: ignore[attr-defined]

        self.push_screen(WorkflowHITLModal(input_data), on_dismiss)  # type: ignore[attr-defined]
