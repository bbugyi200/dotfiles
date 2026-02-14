"""ProjectSpec and WorkspaceClaim data models."""

from dataclasses import dataclass

from .models import ChangeSpec


@dataclass
class WorkspaceClaim:
    """Workspace claim in the RUNNING field."""

    workspace_num: int
    pid: int
    workflow: str
    cl_name: str | None = None
    artifacts_timestamp: str | None = None


@dataclass
class ProjectSpec:
    """Complete project specification file wrapper."""

    file_path: str
    bug: str | None = None
    running: list[WorkspaceClaim] | None = None
    changespecs: list[ChangeSpec] | None = None
