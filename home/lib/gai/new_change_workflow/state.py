"""State definition for the new-change workflow."""

from typing import TypedDict


class NewChangeState(TypedDict, total=False):
    """State for the new-change workflow."""

    # Input parameters
    project_name: str
    design_docs_dir: str
    changespec_text: str
    research_file: str | None

    # Workflow state
    artifacts_dir: str
    workflow_tag: str
    cl_name: str
    cl_description: str

    # Agent outputs
    editor_response: str

    # Success/failure tracking
    success: bool
    failure_reason: str
