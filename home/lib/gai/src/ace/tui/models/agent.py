"""Agent data model for the Agents tab."""

import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path


class AgentType(Enum):
    """Types of agents that can be tracked."""

    RUNNING = "run"  # Manual gai run commands (RUNNING field)
    FIX_HOOK = "fix-hook"  # Fix-hook agents (HOOKS suffix_type=running_agent)
    SUMMARIZE = "summarize"  # Summarize-hook agents (HOOKS)
    MENTOR = "mentor"  # Mentor agents (MENTORS)
    CRS = "crs"  # Comment Resolution System (COMMENTS)


@dataclass
class Agent:
    """Represents a single running agent."""

    agent_type: AgentType
    cl_name: str  # ChangeSpec name
    project_file: str  # Path to .gp file
    status: str  # "RUNNING", etc.
    start_time: datetime | None  # Parsed from timestamp suffix

    # Type-specific fields
    workspace_num: int | None = None  # For RUNNING type
    workflow: str | None = None  # For RUNNING type (e.g., "fix-tests")
    hook_command: str | None = None  # For FIX_HOOK/SUMMARIZE types
    commit_entry_id: str | None = None  # For hook-based agents
    mentor_profile: str | None = None  # For MENTOR type
    mentor_name: str | None = None  # For MENTOR type
    reviewer: str | None = None  # For CRS type (e.g., "critique")

    # PID for process management
    pid: int | None = None

    # For agent suffix parsing
    raw_suffix: str | None = None

    # Response file path for DONE agents
    response_path: str | None = None

    @property
    def display_type(self) -> str:
        """Human-readable agent type for display."""
        return self.agent_type.value

    @property
    def display_label(self) -> str:
        """Combined label for list display: Type + CL name."""
        return f"[{self.display_type}] {self.cl_name}"

    @property
    def start_time_display(self) -> str:
        """Formatted start time for display."""
        if self.start_time is None:
            return "Unknown"
        return self.start_time.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def start_time_short(self) -> str:
        """Short formatted start time (HH:MM) for list display."""
        if self.start_time is None:
            return "?"
        return self.start_time.strftime("%H:%M")

    @property
    def duration_display(self) -> str:
        """Display how long the agent has been running."""
        if self.start_time is None:
            return "?"
        delta = datetime.now() - self.start_time
        total_seconds = int(delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h{minutes}m"
        elif minutes > 0:
            return f"{minutes}m{seconds}s"
        else:
            return f"{seconds}s"

    def get_artifacts_dir(self) -> str | None:
        """Get the artifacts directory path for this agent.

        Returns:
            Path to the artifacts directory, or None if it cannot be determined.
        """
        # Extract project name from project_file
        # Format: ~/.gai/projects/<project>/<project>.gp
        project_path = Path(self.project_file)
        project_name = project_path.parent.name

        # Determine workflow name based on agent type
        if self.agent_type == AgentType.RUNNING:
            workflow = self.workflow or "run"
            # Extract base workflow: "ace(run)-timestamp" -> "ace-run"
            if workflow.startswith("ace(run)"):
                workflow_name = "ace-run"
            else:
                workflow_name = workflow
        elif self.agent_type == AgentType.FIX_HOOK:
            workflow_name = "fix-hook"
        elif self.agent_type == AgentType.SUMMARIZE:
            workflow_name = "summarize-hook"
        elif self.agent_type == AgentType.MENTOR:
            if self.mentor_name:
                workflow_name = f"mentor-{self.mentor_name}"
            else:
                workflow_name = "mentor"
        elif self.agent_type == AgentType.CRS:
            workflow_name = "crs"
        else:
            return None

        # Extract and convert timestamp from raw_suffix
        # raw_suffix format: <agent>-<PID>-YYmmdd_HHMMSS or similar
        # artifacts_dir expects: YYYYmmddHHMMSS
        if self.raw_suffix is None:
            return None

        timestamp = self._extract_artifacts_timestamp()
        if timestamp is None:
            return None

        # Construct path
        artifacts_dir = os.path.expanduser(
            f"~/.gai/projects/{project_name}/artifacts/{workflow_name}/{timestamp}"
        )

        if os.path.isdir(artifacts_dir):
            return artifacts_dir

        return None

    def _extract_artifacts_timestamp(self) -> str | None:
        """Extract and convert timestamp from raw_suffix to artifacts format.

        For RUNNING agents: raw_suffix is already YYYYmmddHHMMSS (14 chars)
        For other agents: raw_suffix uses YYmmdd_HHMMSS format (13 chars with underscore)
        artifacts_dir expects: YYYYmmddHHMMSS format (14 chars, no underscore)

        Returns:
            Converted timestamp string, or None if parsing fails.
        """
        if self.raw_suffix is None:
            return None

        # For RUNNING agents, raw_suffix is the timestamp directly (14 chars)
        if len(self.raw_suffix) == 14 and self.raw_suffix.isdigit():
            return self.raw_suffix

        # Extract timestamp part from suffix
        ts: str | None = None

        if "-" in self.raw_suffix:
            parts = self.raw_suffix.split("-")
            if len(parts) >= 2:
                ts = parts[-1]
        else:
            ts = self.raw_suffix

        # Validate and convert format: YYmmdd_HHMMSS -> YYYYmmddHHMMSS
        if ts and len(ts) == 13 and ts[6] == "_":
            # Add century prefix and remove underscore
            return f"20{ts[:6]}{ts[7:]}"

        return None

    def get_response_content(self) -> str | None:
        """Get the response content for DONE agents.

        Returns:
            Response content string, or None if not available.
        """
        if self.response_path is None:
            return None
        try:
            with open(self.response_path, encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None
