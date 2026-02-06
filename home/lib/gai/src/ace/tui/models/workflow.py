"""Workflow entry model for the Agents tab."""

from dataclasses import dataclass
from datetime import datetime

from xprompt import StepState, StepStatus


@dataclass
class WorkflowEntry:
    """Represents a running or completed workflow in the TUI.

    Attributes:
        workflow_name: Name of the workflow being executed.
        cl_name: Associated ChangeSpec name.
        project_file: Path to the project .gp file.
        status: Overall workflow status ("RUNNING", "WAITING INPUT", "DONE", "FAILED").
        current_step: Index of the currently executing step.
        total_steps: Total number of steps in the workflow.
        steps: List of step states with their individual status.
        start_time: When the workflow started.
        artifacts_dir: Directory containing workflow artifacts.
    """

    workflow_name: str
    cl_name: str
    project_file: str
    status: str
    current_step: int
    total_steps: int
    steps: list[StepState]
    start_time: datetime | None
    artifacts_dir: str
    pid: int | None = None
    appears_as_agent: bool = False

    @property
    def display_type(self) -> str:
        """Human-readable type for display."""
        return f"workflow:{self.workflow_name}"

    @property
    def display_label(self) -> str:
        """Combined label for list display."""
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
        """Display how long the workflow has been running."""
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

    @property
    def progress_display(self) -> str:
        """Display workflow progress as step count."""
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        return f"{completed}/{self.total_steps}"

    @property
    def current_step_name(self) -> str | None:
        """Get the name of the current step."""
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step].name
        return None

    @property
    def is_waiting_hitl(self) -> bool:
        """Check if workflow is waiting for HITL input."""
        return self.status == "WAITING INPUT"

    @property
    def identity(self) -> tuple[str, str, str]:
        """Unique identifier for this workflow instance."""
        return ("workflow", self.cl_name, self.artifacts_dir)
