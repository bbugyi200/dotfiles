"""State management for the create-project workflow."""

from typing import Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage


class CreateProjectState(TypedDict):
    """State for the create-project workflow."""

    bug_id: str  # Bug ID to track this project
    clquery: str  # Critique query for clsurf
    design_docs_dir: str  # Directory containing markdown design docs
    filename: str  # Filename (basename without .md) for project file
    dry_run: bool  # If True, print to STDOUT instead of writing to file
    project_name: (
        str  # Project name (same as filename, used as NAME field in ChangeSpecs)
    )
    artifacts_dir: str  # Artifacts directory for workflow outputs
    workflow_tag: str  # Unique workflow tag
    clsurf_output_file: str | None  # Path to clsurf output file
    projects_file: str  # Path to the generated project file (~/.gai/projects/<filename>/<filename>.gp)
    success: bool  # Whether the workflow completed successfully
    failure_reason: str | None  # Reason for failure if unsuccessful
    messages: list[HumanMessage | AIMessage]  # Message history
    workflow_instance: Any | None  # Reference to the workflow instance
