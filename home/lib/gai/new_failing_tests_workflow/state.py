"""State management for the new-failing-tests workflow."""

from typing import TypedDict

from langchain_core.messages import AIMessage, HumanMessage


class NewFailingTestState(TypedDict):
    """State for the new-failing-tests workflow."""

    # Input parameters
    project_name: str
    design_docs_dir: str
    changespec_text: str  # The ChangeSpec read from STDIN
    research_file: (
        str | None
    )  # Optional path to research file (from work-project workflow)

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
    test_targets: str | None  # Space-separated test targets extracted from test coder

    # Test command to run tests
    test_cmd: str | None

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
