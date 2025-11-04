"""State management for the pre-mail-cl workflow."""

from typing import TypedDict

from langchain_core.messages import AIMessage, HumanMessage


class PreMailCLState(TypedDict):
    """State for the pre-mail-cl workflow."""

    # Input parameters
    project_name: str
    design_docs_dir: str
    changespec_text: str  # The ChangeSpec read from STDIN
    cl_number: str  # The CL number created by create-test-cl
    test_output_file: str  # Path to file containing trimmed test output

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
    test_output_content: str  # Content of the test output file

    # Research results
    research_results: dict[str, dict[str, str]] | None

    # Feature coder agent results
    feature_coder_response: str | None
    feature_coder_success: bool

    # Test verification results
    tests_passed: bool

    # Messages for agents
    messages: list[HumanMessage | AIMessage]

    # Success/failure tracking
    success: bool
    failure_reason: str | None

    # Workflow instance (for callbacks)
    workflow_instance: object
