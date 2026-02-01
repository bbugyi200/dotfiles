"""Agent revival and persistence methods for the ace TUI app."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...modals import ChatFileItem
    from ...models import Agent

# Import ChangeSpec unconditionally since it's used as a type annotation
# in attribute declarations (not just in function signatures)
from ....changespec import ChangeSpec


class AgentRevivalMixin:
    """Mixin providing agent revival and persistence methods.

    Type hints below declare attributes that are defined at runtime by AceApp.
    """

    # ChangeSpec state
    changespecs: list[ChangeSpec]
    current_idx: int

    # Agent state
    _revived_agents: list[Agent]

    def action_revive_agent(self) -> None:
        """Open the chat select modal to revive a chat as an agent."""
        # Only available on agents tab
        if self.current_tab != "agents":  # type: ignore[attr-defined]
            return

        from ...modals import ChatFileItem, ChatSelectModal

        def on_dismiss(result: ChatFileItem | None) -> None:
            if result is not None:
                self._create_revived_agent(result)

        self.push_screen(ChatSelectModal(), on_dismiss)  # type: ignore[attr-defined]

    def _create_revived_agent(self, chat_item: ChatFileItem) -> None:
        """Create a revived agent from a chat file selection.

        Args:
            chat_item: The selected chat file item.
        """
        from datetime import datetime

        from ...models.agent import Agent, AgentType

        # Map workflow to agent type
        workflow_to_type: dict[str | None, AgentType] = {
            "run": AgentType.RUNNING,
            "rerun": AgentType.RUNNING,
            "crs": AgentType.CRS,
            "mentor": AgentType.MENTOR,
            "fix_hook": AgentType.FIX_HOOK,
            "summarize_hook": AgentType.SUMMARIZE,
        }
        agent_type = workflow_to_type.get(chat_item.workflow, AgentType.RUNNING)

        # Parse timestamp for start_time
        start_time: datetime | None = None
        if chat_item.timestamp_str:
            try:
                start_time = datetime.strptime(chat_item.timestamp_str, "%y%m%d_%H%M%S")
            except ValueError:
                pass

        # Try to find a matching project file
        project_file = self._find_project_for_cl(chat_item.branch_or_workspace or "")

        agent = Agent(
            agent_type=agent_type,
            cl_name=chat_item.branch_or_workspace or chat_item.basename[:20],
            project_file=project_file,
            status="REVIVED",
            start_time=start_time,
            workflow=chat_item.workflow,
            response_path=chat_item.full_path,
            raw_suffix=chat_item.timestamp_str,
        )

        self._revived_agents.append(agent)
        self._save_revived_agents()
        self.notify(f"Revived chat as agent: {agent.cl_name}")  # type: ignore[attr-defined]
        self._load_agents()  # type: ignore[attr-defined]

    def _find_project_for_cl(self, cl_name: str) -> str:
        """Try to find a project file that contains the given CL name.

        Args:
            cl_name: The CL/branch name to search for.

        Returns:
            Path to the project file if found, empty string otherwise.
        """
        from pathlib import Path

        from ....changespec import find_all_changespecs

        if not cl_name:
            return ""

        # Search through all changespecs for a match
        all_cs = find_all_changespecs()
        for cs in all_cs:
            if cs.name == cl_name:
                return cs.file_path

        # Fallback: look for a project with a matching directory name
        projects_dir = Path.home() / ".gai" / "projects"
        if projects_dir.exists():
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir():
                    gp_file = project_dir / f"{project_dir.name}.gp"
                    if gp_file.exists():
                        # Return first found project as a fallback
                        return str(gp_file)

        return ""

    def _load_revived_agents(self) -> None:
        """Load revived agents from the persistence file."""
        import json
        from datetime import datetime
        from pathlib import Path

        from ...models.agent import Agent, AgentType

        revived_file = Path.home() / ".gai" / "tui" / "revived_agents.json"
        if not revived_file.exists():
            self._revived_agents = []
            return

        try:
            with open(revived_file, encoding="utf-8") as f:
                data = json.load(f)

            agents: list[Agent] = []
            for entry in data:
                # Map agent_type string to AgentType enum
                type_str = entry.get("agent_type", "run")
                agent_type = AgentType.RUNNING
                for at in AgentType:
                    if at.value == type_str:
                        agent_type = at
                        break

                # Parse timestamp
                start_time: datetime | None = None
                timestamp_str = entry.get("timestamp")
                if timestamp_str:
                    try:
                        start_time = datetime.strptime(timestamp_str, "%y%m%d_%H%M%S")
                    except ValueError:
                        pass

                agents.append(
                    Agent(
                        agent_type=agent_type,
                        cl_name=entry.get("cl_name", "unknown"),
                        project_file=entry.get("project_file", ""),
                        status="REVIVED",
                        start_time=start_time,
                        workflow=entry.get("workflow"),
                        response_path=entry.get("chat_path"),
                        raw_suffix=timestamp_str,
                    )
                )

            self._revived_agents = agents
        except Exception:
            self._revived_agents = []

    def _save_revived_agents(self) -> None:
        """Save revived agents to the persistence file."""
        import json
        from pathlib import Path

        tui_dir = Path.home() / ".gai" / "tui"
        tui_dir.mkdir(parents=True, exist_ok=True)

        revived_file = tui_dir / "revived_agents.json"

        data: list[dict[str, str | None]] = []
        for agent in self._revived_agents:
            data.append(
                {
                    "chat_path": agent.response_path,
                    "agent_type": agent.agent_type.value,
                    "cl_name": agent.cl_name,
                    "project_file": agent.project_file,
                    "workflow": agent.workflow,
                    "timestamp": agent.raw_suffix,
                }
            )

        try:
            with open(revived_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
