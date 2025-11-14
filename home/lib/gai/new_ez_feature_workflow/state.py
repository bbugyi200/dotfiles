"""State definition for new-ez-feature workflow."""

from typing import Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage


class NewEzFeatureState(TypedDict):
    """State for the new-ez-feature workflow."""

    project_name: str  # Name of the project
    design_docs_dir: str  # Directory containing design documents
    changespec_text: str  # The ChangeSpec text
    context_file_directory: (
        str | None
    )  # Optional directory containing markdown files to add to agent prompt
    guidance: str | None  # Optional guidance text to append to agent prompt
    artifacts_dir: str  # Directory for workflow artifacts
    workflow_tag: str  # Unique 3-digit alphanumeric tag for this workflow run
    cl_name: str  # Extracted CL name from ChangeSpec
    cl_description: str  # Extracted CL description from ChangeSpec
    editor_response: str | None  # Response from editor agent
    failure_reason: str | None  # Failure reason if workflow fails
    success: bool  # Whether workflow succeeded
    messages: list[HumanMessage | AIMessage]  # Message history
    workflow_instance: Any | None  # Reference to workflow instance
