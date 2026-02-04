"""Agent killing/dismissal methods for the ace TUI app."""

from __future__ import annotations

import os
import signal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models import Agent
    from ...models.agent import AgentType

# Import ChangeSpec unconditionally since it's used as a type annotation
# in attribute declarations (not just in function signatures)
from ....changespec import ChangeSpec


def _find_workflow_workspace_from_running_field(
    project_file: str,
    workflow_name: str,
    cl_name: str | None = None,
) -> int | None:
    """Find workspace_num for a workflow from the RUNNING field.

    Args:
        project_file: Path to the project file.
        workflow_name: The workflow name (without "workflow()" wrapper).
        cl_name: Optional CL name for more specific matching.

    Returns:
        The workspace_num if found, None otherwise.
    """
    from running_field import get_claimed_workspaces

    claims = get_claimed_workspaces(project_file)
    expected_workflow = f"workflow({workflow_name})"

    for claim in claims:
        if claim.workflow == expected_workflow:
            if cl_name is not None and claim.cl_name != cl_name:
                continue
            return claim.workspace_num

    return None


class AgentKillingMixin:
    """Mixin providing agent killing/dismissal methods.

    Type hints below declare attributes that are defined at runtime by AceApp.
    """

    # ChangeSpec state
    changespecs: list[ChangeSpec]
    current_idx: int

    # Agent state (needed for _dismiss_done_agent)
    _revived_agents: list[Agent]
    _viewed_agents: set[tuple[AgentType, str, str | None]]
    _dismissed_agents: set[tuple[AgentType, str, str | None]]

    def _do_kill_agent(self, agent: Agent) -> None:
        """Perform the actual agent kill after confirmation."""
        from ...models.agent import AgentType

        # Dispatch based on agent type
        if agent.agent_type == AgentType.RUNNING:
            self._kill_running_agent(agent)
        elif agent.agent_type in (AgentType.FIX_HOOK, AgentType.SUMMARIZE):
            self._kill_hook_agent(agent)
        elif agent.agent_type == AgentType.MENTOR:
            self._kill_mentor_agent(agent)
        elif agent.agent_type == AgentType.CRS:
            self._kill_crs_agent(agent)
        elif agent.agent_type == AgentType.WORKFLOW:
            self._kill_workflow_agent(agent)
        else:
            self.notify(  # type: ignore[attr-defined]
                f"Unknown agent type: {agent.agent_type}", severity="error"
            )
            return

        # Refresh agents list
        self._load_agents()  # type: ignore[attr-defined]

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
        from ....changespec import parse_project_file
        from ....hooks import update_changespec_hooks_field
        from ....hooks.processes import mark_hook_agents_as_killed

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
        from ....changespec import parse_project_file
        from ....hooks.processes import mark_mentor_agents_as_killed
        from ....mentors import update_changespec_mentors_field

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
        from ....changespec import parse_project_file
        from ....comments import update_changespec_comments_field
        from ....comments.operations import mark_comment_agents_as_killed

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

    def _kill_workflow_agent(self, agent: Agent) -> None:
        """Kill a workflow agent.

        Args:
            agent: The workflow agent to kill.
        """
        from pathlib import Path

        from running_field import release_workspace

        # Kill the workflow process if it has a PID
        if agent.pid is not None:
            if not self._kill_process_group(agent.pid):
                return
            self.notify(f"Killed workflow (PID {agent.pid})")  # type: ignore[attr-defined]

        # Determine workflow name (steps use parent_workflow)
        workflow_name = agent.workflow
        if agent.is_workflow_child and agent.parent_workflow:
            workflow_name = agent.parent_workflow

        # Release the workspace claim (workflow claims use "workflow(name)" format)
        if workflow_name is not None:
            # Try agent's workspace_num first, then look it up from RUNNING field
            workspace_num = agent.workspace_num
            if workspace_num is None:
                # For steps, don't use the decorated cl_name for lookup
                # Also treat "unknown" as None since it's a placeholder
                lookup_cl_name = None
                if not agent.is_workflow_child and agent.cl_name != "unknown":
                    lookup_cl_name = agent.cl_name
                workspace_num = _find_workflow_workspace_from_running_field(
                    agent.project_file,
                    workflow_name,
                    lookup_cl_name,
                )

            if workspace_num is not None:
                # Treat "unknown" as None since it's a placeholder
                release_cl_name = None
                if not agent.is_workflow_child and agent.cl_name != "unknown":
                    release_cl_name = agent.cl_name
                release_workspace(
                    agent.project_file,
                    workspace_num,
                    f"workflow({workflow_name})",
                    release_cl_name,
                )

        # Delete the workflow state file
        if agent.raw_suffix is None or agent.workflow is None:
            return

        project_path = Path(agent.project_file)
        project_name = project_path.parent.name

        state_file = (
            Path.home()
            / ".gai"
            / "projects"
            / project_name
            / "artifacts"
            / f"workflow-{agent.workflow}"
            / agent.raw_suffix
            / "workflow_state.json"
        )

        if state_file.exists():
            try:
                state_file.unlink()
            except OSError:
                pass  # Already notified about kill, state file cleanup is secondary

    def _dismiss_done_agent(self, agent: Agent) -> None:
        """Dismiss a DONE, REVIVED, or completed workflow agent.

        For REVIVED agents: removes from _revived_agents list and saves.
        For workflow agents: removes the workflow artifacts directory.
        For other agents: removes the done.json file.

        Args:
            agent: The DONE, REVIVED, or completed agent to dismiss.
        """
        import shutil
        from pathlib import Path

        from ...models.agent import AgentType

        # Handle REVIVED agents differently
        if agent.status == "REVIVED":
            self._revived_agents = [  # type: ignore[attr-defined]
                a
                for a in self._revived_agents
                if a.identity != agent.identity  # type: ignore[attr-defined]
            ]
            self._save_revived_agents()  # type: ignore[attr-defined]
            self.notify(f"Dismissed revived agent for {agent.cl_name}")  # type: ignore[attr-defined]
            self._load_agents()  # type: ignore[attr-defined]
            return

        if agent.raw_suffix is None:
            self.notify("Cannot dismiss agent: no timestamp", severity="error")  # type: ignore[attr-defined]
            return

        # Extract project name from project_file path
        # Path format: ~/.gai/projects/<project>/<project>.gp
        project_path = Path(agent.project_file)
        project_name = project_path.parent.name

        # Handle workflow agents - delete entire workflow artifacts directory
        if agent.agent_type == AgentType.WORKFLOW:
            # Release the workspace claim first (workflow claims use
            # "workflow(name)" format in RUNNING field)
            from running_field import release_workspace

            # Determine workflow name (steps use parent_workflow)
            workflow_name = agent.workflow
            if agent.is_workflow_child and agent.parent_workflow:
                workflow_name = agent.parent_workflow

            if workflow_name is not None:
                # Try agent's workspace_num first, then look it up from RUNNING field
                workspace_num = agent.workspace_num
                if workspace_num is None:
                    # For steps, don't use the decorated cl_name for lookup
                    # Also treat "unknown" as None since it's a placeholder
                    lookup_cl_name = None
                    if not agent.is_workflow_child and agent.cl_name != "unknown":
                        lookup_cl_name = agent.cl_name
                    workspace_num = _find_workflow_workspace_from_running_field(
                        agent.project_file,
                        workflow_name,
                        lookup_cl_name,
                    )

                if workspace_num is not None:
                    # Treat "unknown" as None since it's a placeholder
                    release_cl_name = None
                    if not agent.is_workflow_child and agent.cl_name != "unknown":
                        release_cl_name = agent.cl_name
                    release_workspace(
                        agent.project_file,
                        workspace_num,
                        f"workflow({workflow_name})",
                        release_cl_name,
                    )

            workflow_dir = (
                Path.home()
                / ".gai"
                / "projects"
                / project_name
                / "artifacts"
                / f"workflow-{workflow_name or agent.workflow}"
                / (agent.parent_timestamp or agent.raw_suffix)
            )
            try:
                if workflow_dir.exists():
                    shutil.rmtree(workflow_dir)
                self.notify(f"Dismissed workflow {agent.workflow}")  # type: ignore[attr-defined]
            except Exception as e:
                self.notify(f"Error dismissing workflow: {e}", severity="error")  # type: ignore[attr-defined]
                return

            # Always track dismissal in _dismissed_agents as a fallback.
            # This ensures the workflow is filtered out even if it's loaded
            # from the RUNNING field or other sources.
            from ...dismissed_agents import save_dismissed_agents

            self._dismissed_agents.add(agent.identity)  # type: ignore[attr-defined]
            save_dismissed_agents(self._dismissed_agents)  # type: ignore[attr-defined]

            self._load_agents()  # type: ignore[attr-defined]
            return

        # Handle hook-based agents (FIX_HOOK, SUMMARIZE, MENTOR, CRS)
        # These don't have a done.json file - they're stored as status lines
        # in the project file. We track dismissal in _dismissed_agents.
        if agent.agent_type in (
            AgentType.FIX_HOOK,
            AgentType.SUMMARIZE,
            AgentType.MENTOR,
            AgentType.CRS,
        ):
            from ...dismissed_agents import save_dismissed_agents

            self._dismissed_agents.add(agent.identity)  # type: ignore[attr-defined]
            save_dismissed_agents(self._dismissed_agents)  # type: ignore[attr-defined]

            # Remove from viewed agents set if present and persist
            self._viewed_agents.discard(agent.identity)  # type: ignore[attr-defined]
            from ...viewed_agents import save_viewed_agents

            save_viewed_agents(self._viewed_agents)  # type: ignore[attr-defined]

            self.notify(  # type: ignore[attr-defined]
                f"Dismissed {agent.agent_type.value.lower()} agent for {agent.cl_name}"
            )
            self._load_agents()  # type: ignore[attr-defined]
            return

        # Build path to done.json for ace-run agents
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

        # Remove from viewed agents set if present and persist
        self._viewed_agents.discard(agent.identity)  # type: ignore[attr-defined]
        from ...viewed_agents import save_viewed_agents

        save_viewed_agents(self._viewed_agents)  # type: ignore[attr-defined]

        # Refresh agents list
        self._load_agents()  # type: ignore[attr-defined]
