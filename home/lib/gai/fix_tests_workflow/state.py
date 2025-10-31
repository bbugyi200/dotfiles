import os
from typing import Any, List, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage


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
    todos_created: bool
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













def collect_all_research_md_files(artifacts_dir: str, current_iteration: int) -> str:
    """Collect all research.md files from previous iterations for planner agents to review."""
    research_files_info = ""

    # Collect research.md files from all previous iterations (1 to current_iteration-1)
    research_files = []

    for iter_num in range(1, current_iteration):
        research_file = os.path.join(artifacts_dir, f"research_iter_{iter_num}.md")
        if os.path.exists(research_file):
            research_files.append(
                f"{research_file} - Research findings from iteration {iter_num} (different test failure state)"
            )

    if research_files:
        research_files_info += "\n# ALL RESEARCH FILES:\n"
        for file_info in research_files:
            research_files_info += f"{file_info}\n"

    return research_files_info


def collect_distinct_test_outputs_info(distinct_test_outputs: List[str]) -> str:
    """Collect information about all distinct test output files for comparison."""
    if not distinct_test_outputs:
        return "No previous distinct test output files found."

    info = f"Found {len(distinct_test_outputs)} distinct test output files from previous iterations:\n"
    for i, test_output_path in enumerate(distinct_test_outputs, 1):
        info += f"{i}. {test_output_path} - Previously determined to be distinct\n"

    return info
