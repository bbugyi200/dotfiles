"""State definition for new-tdd-feature workflow."""

from typing import Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage


class NewTddFeatureState(TypedDict):
    """State for the new-tdd-feature workflow."""

    test_output_file: str  # Path to test output file from new-failing-tests workflow
    test_command: str | None  # Test command discovered from test output file
    user_instructions_file: str | None  # Optional user instructions
    context_file_directory: (
        str | None
    )  # Optional directory containing markdown files to add to agent prompt
    artifacts_dir: str  # Directory for workflow artifacts
    current_iteration: int  # Current iteration number
    max_iterations: int  # Maximum number of iterations
    test_passed: bool  # Whether tests are passing
    failure_reason: str | None  # Failure reason if workflow fails
    messages: list[HumanMessage | AIMessage]  # Message history
    workflow_instance: Any | None  # Reference to workflow instance
    workflow_tag: str  # Unique 3-digit alphanumeric tag for this workflow run
    artifact_files: dict[str, str]  # Map of artifact names to file paths
