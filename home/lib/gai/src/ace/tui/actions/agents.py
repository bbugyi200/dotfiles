"""Agent display mixin for the ace TUI app."""

from __future__ import annotations

import os
import signal
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ...changespec import ChangeSpec
    from ..models import Agent
    from ..models.agent import AgentType

# Type alias for tab names
TabName = Literal["changespecs", "agents", "axe"]


class AgentsMixin:
    """Mixin providing agent loading and display methods."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    current_idx: int
    current_tab: TabName
    refresh_interval: int
    _countdown_remaining: int
    _agents: list[Agent]

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

        # Handle completed agents with dismiss (no confirmation needed)
        if agent.status in ("NO CHANGES", "NEW CL", "NEW PROPOSAL"):
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
        from ..modals import ConfirmKillModal

        def on_dismiss(confirmed: bool | None) -> None:
            if confirmed:
                self._do_kill_agent(agent)

        self.push_screen(ConfirmKillModal(agent_description), on_dismiss)  # type: ignore[attr-defined]

    def _do_kill_agent(self, agent: Agent) -> None:
        """Perform the actual agent kill after confirmation."""
        from ..models.agent import AgentType

        # Dispatch based on agent type
        if agent.agent_type == AgentType.RUNNING:
            self._kill_running_agent(agent)
        elif agent.agent_type in (AgentType.FIX_HOOK, AgentType.SUMMARIZE):
            self._kill_hook_agent(agent)
        elif agent.agent_type == AgentType.MENTOR:
            self._kill_mentor_agent(agent)
        elif agent.agent_type == AgentType.CRS:
            self._kill_crs_agent(agent)
        else:
            self.notify(  # type: ignore[attr-defined]
                f"Unknown agent type: {agent.agent_type}", severity="error"
            )
            return

        # Refresh agents list
        self._load_agents()

    def _kill_process_group(self, pid: int) -> bool:
        """Kill a process group by PID.

        Args:
            pid: Process ID to kill.

        Returns:
            True if kill succeeded or process was already dead, False on error.
        """
        try:
            os.killpg(pid, signal.SIGTERM)
            return True
        except ProcessLookupError:
            # Process already dead - still consider success
            return True
        except PermissionError:
            self.notify(  # type: ignore[attr-defined]
                f"Permission denied killing PID {pid}", severity="error"
            )
            return False

    def _kill_running_agent(self, agent: Agent) -> None:
        """Kill a RUNNING type agent (workspace-based)."""
        from running_field import release_workspace

        if agent.pid is None:
            return

        if not self._kill_process_group(agent.pid):
            return

        self.notify(f"Killed agent (PID {agent.pid})")  # type: ignore[attr-defined]

        # Release the workspace claim
        if agent.workspace_num is not None:
            release_workspace(
                agent.project_file,
                agent.workspace_num,
                agent.workflow,
                agent.cl_name,
            )

    def _kill_hook_agent(self, agent: Agent) -> None:
        """Kill a hook agent (FIX_HOOK or SUMMARIZE)."""
        from ...changespec import parse_project_file
        from ...hooks import update_changespec_hooks_field
        from ...hooks.processes import mark_hook_agents_as_killed

        if agent.pid is None:
            return

        if not self._kill_process_group(agent.pid):
            return

        self.notify(f"Killed hook agent (PID {agent.pid})")  # type: ignore[attr-defined]

        # Update hook status to killed_agent
        changespecs = parse_project_file(agent.project_file)
        for cs in changespecs:
            if cs.name == agent.cl_name and cs.hooks:
                killed_hook_agents = []
                for hook in cs.hooks:
                    if hook.status_lines:
                        for sl in hook.status_lines:
                            if (
                                sl.suffix_type == "running_agent"
                                and sl.suffix == agent.raw_suffix
                            ):
                                killed_hook_agents.append((hook, sl, agent.pid))

                if killed_hook_agents:
                    updated_hooks = mark_hook_agents_as_killed(
                        cs.hooks, killed_hook_agents
                    )
                    update_changespec_hooks_field(
                        agent.project_file, agent.cl_name, updated_hooks
                    )
                break

    def _kill_mentor_agent(self, agent: Agent) -> None:
        """Kill a mentor agent."""
        from ...changespec import parse_project_file
        from ...hooks.processes import mark_mentor_agents_as_killed
        from ...mentors import update_changespec_mentors_field

        if agent.pid is None:
            return

        if not self._kill_process_group(agent.pid):
            return

        self.notify(f"Killed mentor agent (PID {agent.pid})")  # type: ignore[attr-defined]

        # Update mentor status to killed_agent
        changespecs = parse_project_file(agent.project_file)
        for cs in changespecs:
            if cs.name == agent.cl_name and cs.mentors:
                killed_mentor_agents = []
                for entry in cs.mentors:
                    if entry.status_lines:
                        for sl in entry.status_lines:
                            if (
                                sl.suffix_type == "running_agent"
                                and sl.suffix == agent.raw_suffix
                            ):
                                killed_mentor_agents.append((entry, sl, agent.pid))

                if killed_mentor_agents:
                    updated_mentors = mark_mentor_agents_as_killed(
                        cs.mentors, killed_mentor_agents
                    )
                    update_changespec_mentors_field(
                        agent.project_file, agent.cl_name, updated_mentors
                    )
                break

    def _kill_crs_agent(self, agent: Agent) -> None:
        """Kill a CRS (comments) agent."""
        from ...changespec import parse_project_file
        from ...comments import update_changespec_comments_field
        from ...comments.operations import mark_comment_agents_as_killed

        if agent.pid is None:
            return

        if not self._kill_process_group(agent.pid):
            return

        self.notify(f"Killed CRS agent (PID {agent.pid})")  # type: ignore[attr-defined]

        # Update comment status to killed_agent
        changespecs = parse_project_file(agent.project_file)
        for cs in changespecs:
            if cs.name == agent.cl_name and cs.comments:
                killed_comment_agents = []
                for comment in cs.comments:
                    if (
                        comment.suffix_type == "running_agent"
                        and comment.suffix == agent.raw_suffix
                    ):
                        killed_comment_agents.append((comment, agent.pid))

                if killed_comment_agents:
                    updated_comments = mark_comment_agents_as_killed(
                        cs.comments, killed_comment_agents
                    )
                    update_changespec_comments_field(
                        agent.project_file, agent.cl_name, updated_comments
                    )
                break

    def _dismiss_done_agent(self, agent: Agent) -> None:
        """Dismiss a DONE agent by removing its done.json file.

        Args:
            agent: The DONE agent to dismiss.
        """
        from pathlib import Path

        if agent.raw_suffix is None:
            self.notify("Cannot dismiss agent: no timestamp", severity="error")  # type: ignore[attr-defined]
            return

        # Extract project name from project_file path
        # Path format: ~/.gai/projects/<project>/<project>.gp
        project_path = Path(agent.project_file)
        project_name = project_path.parent.name

        # Build path to done.json
        done_path = (
            Path.home()
            / ".gai"
            / "projects"
            / project_name
            / "artifacts"
            / "ace-run"
            / agent.raw_suffix
            / "done.json"
        )

        try:
            if done_path.exists():
                done_path.unlink()
                self.notify(f"Dismissed agent for {agent.cl_name}")  # type: ignore[attr-defined]
            else:
                self.notify("Agent already dismissed", severity="warning")  # type: ignore[attr-defined]
        except Exception as e:
            self.notify(f"Error dismissing agent: {e}", severity="error")  # type: ignore[attr-defined]
            return

        # Refresh agents list
        self._load_agents()

    def _load_agents(self) -> None:
        """Load agents from all sources."""
        from ..models import load_all_agents

        # Capture current selection identity before reload
        selected_identity: tuple[AgentType, str, str | None] | None = None
        if self._agents and 0 <= self.current_idx < len(self._agents):
            selected_identity = self._agents[self.current_idx].identity

        # Load fresh agent list
        self._agents = load_all_agents()

        # Try to restore selection by identity
        if selected_identity is not None:
            for idx, agent in enumerate(self._agents):
                if agent.identity == selected_identity:
                    self.current_idx = idx
                    break
            else:
                # Agent no longer in list - clamp to bounds
                if self._agents:
                    self.current_idx = min(self.current_idx, len(self._agents) - 1)
                else:
                    self.current_idx = 0
        else:
            # No previous selection - clamp to bounds
            if self._agents:
                self.current_idx = min(self.current_idx, len(self._agents) - 1)
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

        # Query diff visibility for footer (must be done after update_display)
        diff_visible = agent_detail.is_diff_visible()

        footer_widget.update_agent_bindings(
            current_agent,
            self.current_idx,
            len(self._agents),
            diff_visible=diff_visible,
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

        # Only available for completed agents
        if agent.status not in ("NO CHANGES", "NEW CL", "NEW PROPOSAL"):
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

        from ..widgets import AgentDetail

        agent_detail = self.query_one("#agent-detail-panel", AgentDetail)  # type: ignore[attr-defined]

        if not agent_detail.is_diff_visible():
            self.notify("No diff panel to toggle", severity="warning")  # type: ignore[attr-defined]
            return

        agent_detail.toggle_layout()
