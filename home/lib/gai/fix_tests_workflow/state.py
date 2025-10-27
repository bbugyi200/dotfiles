import os
from typing import List, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage


class FixTestsState(TypedDict):
    test_cmd: str
    test_output_file: str
    user_instructions_file: Optional[str]
    artifacts_dir: str
    current_iteration: int
    max_iterations: int
    current_judge_iteration: int
    max_judges: int
    test_passed: bool
    failure_reason: Optional[str]
    requirements_exists: bool
    research_exists: bool
    todos_created: bool
    research_updated: bool
    context_agent_retries: int
    max_context_retries: int
    judge_applied_changes: int
    no_human_approval: bool
    comment_out_lines: bool
    verification_retries: int
    max_verification_retries: int
    verification_passed: bool
    needs_editor_retry: bool
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


def collect_all_agent_diff_files(artifacts_dir: str, current_iteration: int) -> str:
    """Collect all available agent diff files for the context agent to review."""
    diff_files_info = ""

    # Collect diff files from all iterations (1 to current_iteration-1)
    diff_files = []

    for iter_num in range(1, current_iteration):
        diff_file = os.path.join(artifacts_dir, f"editor_iter_{iter_num}_changes.diff")
        if os.path.exists(diff_file):
            diff_files.append(
                f"@{diff_file} - Code changes made by editor agent in iteration {iter_num}"
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
                f"@{research_response_file} - Research agent analysis and findings for iteration {iter_num}"
            )

        # Editor agent response file
        response_file = os.path.join(
            artifacts_dir, f"editor_iter_{iter_num}_response.txt"
        )
        if os.path.exists(response_file):
            iteration_artifacts.append(
                f"@{response_file} - Editor agent analysis and approach for iteration {iter_num}"
            )

        # Editor agent code changes diff
        changes_file = os.path.join(
            artifacts_dir, f"editor_iter_{iter_num}_changes.diff"
        )
        if os.path.exists(changes_file):
            iteration_artifacts.append(
                f"@{changes_file} - Code changes made by editor agent in iteration {iter_num}"
            )

        # Test execution results after editor changes
        test_output_file = os.path.join(
            artifacts_dir, f"editor_iter_{iter_num}_test_output.txt"
        )
        if os.path.exists(test_output_file):
            iteration_artifacts.append(
                f"@{test_output_file} - Test execution results after iteration {iter_num} changes"
            )

        # Editor todo list (if exists)
        editor_todos_file = os.path.join(
            artifacts_dir, f"editor_iter_{iter_num}_todos.txt"
        )
        if os.path.exists(editor_todos_file):
            iteration_artifacts.append(
                f"@{editor_todos_file} - Editor agent todo list from iteration {iter_num}"
            )

        # Note: User instructions are no longer versioned - they remain at the original file path

        # Add iteration section if we found any artifacts
        if iteration_artifacts:
            all_artifacts_info += f"\nITERATION {iter_num} ARTIFACTS:\n"
            for artifact_info in iteration_artifacts:
                all_artifacts_info += f"{artifact_info}\n"

    return all_artifacts_info


def collect_last_agent_artifacts(artifacts_dir: str, current_iteration: int) -> str:
    """Collect artifacts from only the most recent iteration for editor agents."""
    if current_iteration <= 1:
        return ""

    last_iteration = current_iteration - 1
    artifacts_info = ""
    last_artifacts = []

    # Editor response from last iteration
    response_file = os.path.join(
        artifacts_dir, f"editor_iter_{last_iteration}_response.txt"
    )
    if os.path.exists(response_file):
        last_artifacts.append(
            f"@{response_file} - Previous editor agent response (iteration {last_iteration})"
        )

    # Changes diff from last iteration
    changes_file = os.path.join(
        artifacts_dir, f"editor_iter_{last_iteration}_changes.diff"
    )
    if os.path.exists(changes_file):
        last_artifacts.append(
            f"@{changes_file} - Code changes made in iteration {last_iteration}"
        )

    # Test results from last iteration
    test_output_file = os.path.join(
        artifacts_dir, f"editor_iter_{last_iteration}_test_output.txt"
    )
    if os.path.exists(test_output_file):
        last_artifacts.append(
            f"@{test_output_file} - Test results from iteration {last_iteration}"
        )

    # Todo list from last iteration
    todos_file = os.path.join(artifacts_dir, f"editor_iter_{last_iteration}_todos.txt")
    if os.path.exists(todos_file):
        last_artifacts.append(
            f"@{todos_file} - Todo list from iteration {last_iteration}"
        )

    # Research log (if exists)
    research_file = os.path.join(artifacts_dir, "research.md")
    if os.path.exists(research_file):
        last_artifacts.append(
            f"@{research_file} - Research log with findings from all iterations"
        )

    if last_artifacts:
        artifacts_info += f"\n# PREVIOUS ITERATION ({last_iteration}) ARTIFACTS:\n"
        for artifact in last_artifacts:
            artifacts_info += f"{artifact}\n"

    return artifacts_info


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
