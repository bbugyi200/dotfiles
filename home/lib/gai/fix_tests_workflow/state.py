import os
from typing import Any, List, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage


class FixTestsState(TypedDict):
    test_cmd: str
    test_output_file: str
    user_instructions_file: Optional[str]
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


def file_exists_with_content(file_path: str) -> bool:
    """Check if a file exists and has non-whitespace content."""
    try:
        if not os.path.exists(file_path):
            return False
        with open(file_path, "r") as f:
            content = f.read()
            return bool(content.strip())
    except Exception:
        return False


def collect_all_test_output_files(artifacts_dir: str, current_iteration: int) -> str:
    """Collect all available test output files for the context agent to review."""
    test_output_files_info = ""

    # Collect test output files from all iterations (1 to current_iteration-1)
    test_files = []

    for iter_num in range(1, current_iteration):
        test_output_file = os.path.join(
            artifacts_dir, f"editor_iter_{iter_num}_test_output.txt"
        )
        if os.path.exists(test_output_file):
            test_files.append(
                f"{test_output_file} - Full test execution results from iteration {iter_num}"
            )

    if test_files:
        test_output_files_info += "\n# ALL TEST OUTPUT FILES:\n"
        for file_info in test_files:
            test_output_files_info += f"{file_info}\n"

    return test_output_files_info


def collect_all_agent_diff_files(artifacts_dir: str, current_iteration: int) -> str:
    """Collect all available agent diff files for the context agent to review."""
    diff_files_info = ""

    # Collect diff files from all iterations (1 to current_iteration-1)
    diff_files = []

    for iter_num in range(1, current_iteration):
        diff_file = os.path.join(artifacts_dir, f"editor_iter_{iter_num}_changes.diff")
        if os.path.exists(diff_file):
            diff_files.append(
                f"{diff_file} - Code changes made by editor agent in iteration {iter_num}"
            )

    if diff_files:
        diff_files_info += "\n# ALL AGENT DIFF FILES:\n"
        for file_info in diff_files:
            diff_files_info += f"{file_info}\n"

    return diff_files_info


def collect_all_agent_artifacts(artifacts_dir: str, current_iteration: int) -> str:
    """Collect ALL agent artifacts from all iterations for the context agent to review."""
    all_artifacts_info = ""

    # Collect artifacts from all previous iterations (1 to current_iteration-1)
    for iter_num in range(1, current_iteration):
        iteration_artifacts = []

        # Research agent response file (NEW)
        research_response_file = os.path.join(
            artifacts_dir, f"research_iter_{iter_num}_response.txt"
        )
        if os.path.exists(research_response_file):
            iteration_artifacts.append(
                f"{research_response_file} - Research agent analysis and findings for iteration {iter_num}"
            )

        # Editor agent response file
        response_file = os.path.join(
            artifacts_dir, f"editor_iter_{iter_num}_response.txt"
        )
        if os.path.exists(response_file):
            iteration_artifacts.append(
                f"{response_file} - Editor agent analysis and approach for iteration {iter_num}"
            )

        # Editor agent code changes diff
        changes_file = os.path.join(
            artifacts_dir, f"editor_iter_{iter_num}_changes.diff"
        )
        if os.path.exists(changes_file):
            iteration_artifacts.append(
                f"{changes_file} - Code changes made by editor agent in iteration {iter_num}"
            )

        # Test execution results after editor changes
        test_output_file = os.path.join(
            artifacts_dir, f"editor_iter_{iter_num}_test_output.txt"
        )
        if os.path.exists(test_output_file):
            iteration_artifacts.append(
                f"{test_output_file} - Test execution results after iteration {iter_num} changes"
            )

        # Editor todo list (if exists)
        editor_todos_file = os.path.join(
            artifacts_dir, f"editor_iter_{iter_num}_todos.txt"
        )
        if os.path.exists(editor_todos_file):
            iteration_artifacts.append(
                f"{editor_todos_file} - Editor agent todo list from iteration {iter_num}"
            )

        # Note: User instructions are no longer versioned - they remain at the original file path

        # Add iteration section if we found any artifacts
        if iteration_artifacts:
            all_artifacts_info += f"\nITERATION {iter_num} ARTIFACTS:\n"
            for artifact_info in iteration_artifacts:
                all_artifacts_info += f"{artifact_info}\n"

    return all_artifacts_info


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
