"""Agent data model for the Agents tab."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


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
