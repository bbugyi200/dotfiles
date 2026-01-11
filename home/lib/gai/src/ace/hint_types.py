"""Data types for hint-based file selection."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ViewFilesResult:
    """Result from ViewFilesModal."""

    files: list[str]  # Expanded file paths
    open_in_editor: bool  # True if @ suffix was used
    copy_to_clipboard: bool  # True if % suffix was used
    user_input: str  # Raw input for nvim positioning logic
    changespec_name: str  # For editor positioning


@dataclass
class EditHooksResult:
    """Result from EditHooksModal."""

    action_type: Literal["rerun_delete", "test_targets", "custom_hook"]
    # For rerun_delete:
    hints_to_rerun: list[int] = field(default_factory=list)
    hints_to_delete: list[int] = field(default_factory=list)
    # For test_targets:
    test_targets: list[str] = field(default_factory=list)
    # For custom_hook:
    hook_command: str | None = None
