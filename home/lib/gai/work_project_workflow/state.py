"""State management for the work-project workflow."""

from typing import TypedDict


class WorkProjectState(TypedDict):
    """State for the work-project workflow."""

    # Input parameters
    project_file: str  # Path to the ProjectSpec file (e.g., ~/.gai/projects/yserve.md)
    design_docs_dir: str  # Directory containing design documents
    dry_run: bool  # If True, only print the ChangeSpec without invoking create-cl

    # Parsed data
    project_name: str  # Project name extracted from filename
    changespecs: list[dict[str, str]]  # List of parsed ChangeSpecs
    selected_changespec: dict[str, str] | None  # The ChangeSpec to work on

    # Success/failure tracking
    success: bool
    failure_reason: str | None

    # Workflow instance (for callbacks)
    workflow_instance: object
