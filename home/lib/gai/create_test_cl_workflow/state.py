"""State management for the create-test-cl workflow."""

from typing import TypedDict

from langchain_core.messages import AIMessage, HumanMessage


class CreateTestCLState(TypedDict):
    """State for the create-test-cl workflow."""

    # Input parameters
    project_name: str
    design_docs_dir: str
    changespec_text: str  # The ChangeSpec read from STDIN

    # Parsed ChangeSpec fields
    cl_name: str
    cl_description: str
    cl_parent: str | None
    cl_status: str

    # Artifacts and workflow tracking
    artifacts_dir: str
    workflow_tag: str
    clsurf_output_file: str | None
    log_file: str

    # Research results
    research_results: dict[str, dict[str, str]] | None

    # Test coder agent results
    test_coder_response: str | None
    test_coder_success: bool

    # Test verification results
    tests_failed_as_expected: bool

    # CL creation results
    cl_id: str | None  # Changeset ID after successful commit

    # Messages for agents
    messages: list[HumanMessage | AIMessage]

    # Success/failure tracking
    success: bool
    failure_reason: str | None

    # Workflow instance (for callbacks)
    workflow_instance: object
