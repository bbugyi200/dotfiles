"""State management for the work-project workflow."""

from typing import TypedDict

from langchain_core.messages import AIMessage, HumanMessage


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

    # ChangeSpec fields extracted from selected_changespec
    cl_name: str  # NAME field from ChangeSpec
    cl_description: str  # DESCRIPTION field from ChangeSpec

    # Research and artifacts
    artifacts_dir: str  # Directory for workflow artifacts
    workflow_tag: str  # Unique tag for this workflow run
    clsurf_output_file: str | None  # Output from clsurf command
    research_results: dict[str, dict[str, str]] | None  # Results from research agents
    research_file: str | None  # File containing aggregated research results
    context_dir: str | None  # Directory containing context markdown files for fix-tests

    # Test CL creation results
    cl_id: str | None  # CL ID created by create-test-cl workflow

    # Messages for agents
    messages: list[HumanMessage | AIMessage]

    # Status tracking for cleanup
    status_updated_to_in_progress: bool  # Track if we updated STATUS to "In Progress"

    # Success/failure tracking
    success: bool
    failure_reason: str | None

    # Workflow instance (for callbacks)
    workflow_instance: object
