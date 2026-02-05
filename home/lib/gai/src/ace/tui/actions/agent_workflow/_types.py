"""Type definitions for agent workflow mixin."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Type alias for tab names
TabName = Literal["changespecs", "agents", "axe"]


@dataclass
class PromptContext:
    """Context for in-progress agent prompt input."""

    project_name: str
    cl_name: str | None
    new_cl_name: str | None
    parent_cl_name: str | None
    project_file: str
    workspace_dir: str
    workspace_num: int
    workflow_name: str
    timestamp: str
    history_sort_key: str
    display_name: str
    update_target: str
    bug: str | None = None
    fixed_bug: str | None = None
    is_home_mode: bool = False
