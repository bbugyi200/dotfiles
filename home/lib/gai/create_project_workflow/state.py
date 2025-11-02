"""State management for the create-project workflow."""

from typing import Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage


class CreateProjectState(TypedDict):
    """State for the create-project workflow."""

    clquery: str  # Critique query for clsurf
    design_docs_dir: str  # Directory containing markdown design docs
    filename: str  # Filename (basename) for the project file in ~/.gai/projects/
    artifacts_dir: str  # Artifacts directory for workflow outputs
    workflow_tag: str  # Unique workflow tag
    clsurf_output_file: str | None  # Path to clsurf output file
    projects_file: (
        str  # Path to the generated project file (~/.gai/projects/<filename>)
    )
    success: bool  # Whether the workflow completed successfully
    failure_reason: str | None  # Reason for failure if unsuccessful
    messages: list[HumanMessage | AIMessage]  # Message history
    workflow_instance: Any | None  # Reference to the workflow instance
