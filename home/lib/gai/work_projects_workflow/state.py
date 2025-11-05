"""State management for the work-projects workflow."""

from typing import TypedDict

from langchain_core.messages import AIMessage, HumanMessage


class WorkProjectState(TypedDict):
    """State for the work-projects workflow."""

    # Input parameters
    project_file: str  # Path to the ProjectSpec file (e.g., ~/.gai/projects/yserve.md)
    design_docs_dir: str  # Directory containing design documents
    dry_run: bool  # If True, only print the ChangeSpec without invoking create-cl

    # Parsed data
    bug_id: str  # Bug ID from ProjectSpec file
    project_name: str  # Project name extracted from filename
    changespecs: list[dict[str, str]]  # List of parsed ChangeSpecs
    selected_changespec: dict[str, str] | None  # The ChangeSpec to work on

    # ChangeSpec fields extracted from selected_changespec
    cl_name: str  # NAME field from ChangeSpec
    cl_description: str  # DESCRIPTION field from ChangeSpec

    # Workflow artifacts
    artifacts_dir: str  # Directory for workflow artifacts
    workflow_tag: str  # Unique tag for this workflow run
    clsurf_output_file: str | None  # Output from clsurf command

    # Test CL creation results
    cl_id: str | None  # CL ID created by create-test-cl workflow

    # Messages for agents
    messages: list[HumanMessage | AIMessage]

    # Status tracking for cleanup
    status_updated_to_in_progress: bool  # Track if we updated STATUS to "In Progress"
    status_updated_to_tdd_cl_created: (
        bool  # Track if we updated STATUS to "TDD CL Created"
    )
    status_updated_to_fixing_tests: bool  # Track if we updated STATUS to "Fixing Tests"

    # Success/failure tracking
    success: bool
    failure_reason: str | None

    # Multi-ChangeSpec tracking
    attempted_changespecs: list[str]  # List of ChangeSpec NAMEs already attempted
    attempted_changespec_statuses: dict[
        str, str
    ]  # Map of ChangeSpec NAME -> STATUS when last attempted (for loop detection)
    max_changespecs: int | None  # Max number to process (None = infinity)
    changespecs_processed: int  # Number of ChangeSpecs processed so far
    should_continue: bool  # Whether to continue processing more ChangeSpecs

    # Workflow instance (for callbacks)
    workflow_instance: object
