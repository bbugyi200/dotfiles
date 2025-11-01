from typing import Any, List, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage


def get_latest_planner_response(state: "FixTestsState") -> str:
    """Get the latest planner agent response from the state messages."""
    messages = state.get("messages", [])

    # Look for the most recent planner response
    for message in reversed(messages):
        if hasattr(message, "content") and message.content:
            # This is a simplified approach - in practice, you might want to
            # track which message came from which agent more explicitly
            if (
                "# Analysis and Planning" in message.content
                or "# File Modifications" in message.content
            ):
                return message.content

    return ""


def extract_file_modifications_from_response(response: str) -> str:
    """Extract the File Modifications section from a planner response."""
    if not response:
        return ""

    lines = response.split("\n")
    in_file_modifications = False
    modifications_lines = []

    for line in lines:
        if line.strip() == "# File Modifications":
            in_file_modifications = True
            continue
        elif line.startswith("# ") and in_file_modifications:
            # Start of a new section, stop collecting
            break
        elif in_file_modifications:
            modifications_lines.append(line)

    if modifications_lines:
        return "\n".join(modifications_lines).strip()
    else:
        return ""


class FixTestsState(TypedDict):
    test_cmd: str
    test_output_file: str
    user_instructions_file: Optional[str]
    clquery: Optional[str]  # Optional query for CL analysis
    clsurf_output_file: Optional[str]  # Path to clsurf output file
    artifacts_dir: str
    current_iteration: int
    max_iterations: int
    test_passed: bool
    failure_reason: Optional[str]
    requirements_exists: bool
    research_exists: bool
    structured_modifications_received: (
        bool  # Track if planner provided structured file modifications
    )
    research_updated: bool
    context_agent_retries: int
    max_context_retries: int
    verification_retries: int
    max_verification_retries: int
    verification_passed: bool
    needs_editor_retry: bool
    first_verification_success: bool
    messages: List[HumanMessage | AIMessage]
    workflow_instance: Optional[Any]  # Use Any to avoid circular import
    last_amend_successful: bool  # Track if the last amend operation was successful
    safe_to_unamend: bool  # Track if it's safe to run unamend (i.e., we've had at least one successful amend)
    research_results: Optional[dict]  # Results from research agents
    research_md_created: bool  # Track if research.md was created
    workflow_tag: str  # Unique 3-digit alphanumeric tag for this workflow run
    commit_iteration: int  # Counter for successful commits (starts at 1)
    meaningful_test_failure_change: bool  # Track if test failure meaningfully changed
    comparison_completed: bool  # Track if test failure comparison was completed
    distinct_test_outputs: List[
        str
    ]  # List of file paths to test outputs determined to be distinct/unique
    verifier_notes: List[str]  # Accumulated notes from verifier agents
    postmortem_completed: bool  # Track if postmortem analysis was completed
    postmortem_content: Optional[str]  # Content from postmortem agent
    initial_test_output: Optional[
        str
    ]  # Initial test output for first iteration log entry


def collect_distinct_test_outputs_info(distinct_test_outputs: List[str]) -> str:
    """Collect information about all distinct test output files for comparison."""
    if not distinct_test_outputs:
        return "No previous distinct test output files found."

    info = f"Found {len(distinct_test_outputs)} distinct test output files from previous iterations:\n"
    for i, test_output_path in enumerate(distinct_test_outputs, 1):
        info += f"{i}. {test_output_path} - Previously determined to be distinct\n"

    return info
