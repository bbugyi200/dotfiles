import os
from typing import List, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage


class FixTestsState(TypedDict):
    test_cmd: str
    test_output_file: str
    blackboard_file: Optional[str]
    artifacts_dir: str
    current_iteration: int
    max_iterations: int
    test_passed: bool
    failure_reason: Optional[str]
    lessons_exists: bool
    research_exists: bool
    context_agent_retries: int
    max_context_retries: int
    messages: List[HumanMessage | AIMessage]


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
                f"@{test_output_file} - Full test execution results from iteration {iter_num}"
            )

    if test_files:
        test_output_files_info += "\n# ALL TEST OUTPUT FILES:\n"
        for file_info in test_files:
            test_output_files_info += f"{file_info}\n"

    return test_output_files_info


def collect_historical_iteration_files(
    artifacts_dir: str, current_iteration: int
) -> str:
    """Collect all historical iteration files for the context agent to review."""
    historical_files_info = ""

    # Collect files from all previous iterations (1 to current_iteration-1)
    for iter_num in range(1, current_iteration):
        iteration_files = []

        # Check for editor response file
        response_file = os.path.join(
            artifacts_dir, f"editor_iter_{iter_num}_response.txt"
        )
        if os.path.exists(response_file):
            iteration_files.append(
                f"@{response_file} - Editor agent response from iteration {iter_num}"
            )

        # Check for changes diff file
        changes_file = os.path.join(
            artifacts_dir, f"editor_iter_{iter_num}_changes.diff"
        )
        if os.path.exists(changes_file):
            iteration_files.append(
                f"@{changes_file} - Code changes made by editor in iteration {iter_num}"
            )

        # Check for full test output file
        test_output_file = os.path.join(
            artifacts_dir, f"editor_iter_{iter_num}_test_output.txt"
        )
        if os.path.exists(test_output_file):
            iteration_files.append(
                f"@{test_output_file} - Full test execution results from iteration {iter_num}"
            )

        # Add iteration section if we found any files
        if iteration_files:
            historical_files_info += f"\n# ITERATION {iter_num} FILES:\n"
            for file_info in iteration_files:
                historical_files_info += f"{file_info}\n"

    return historical_files_info
