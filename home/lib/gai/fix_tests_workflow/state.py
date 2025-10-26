import os
from typing import List, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage


class FixTestsState(TypedDict):
    test_cmd: str
    test_output_file: str
    blackboard_file: Optional[str]
    artifacts_dir: str
    current_iteration: int
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


def create_test_output_diff(
    artifacts_dir: str, iteration: int, test_output_content: str
) -> str:
    """Create a diff between the current test output and the original test_output.txt."""
    from shared_utils import run_shell_command

    original_test_output_path = os.path.join(artifacts_dir, "test_output.txt")

    try:
        # Read the original test output
        with open(original_test_output_path, "r") as f:
            original_content = f.read()

        # Create temporary files for diff
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as original_tmp:
            original_tmp.write(original_content)
            original_tmp_path = original_tmp.name

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as current_tmp:
            current_tmp.write(test_output_content)
            current_tmp_path = current_tmp.name

        # Create diff using shell command
        diff_cmd = f"diff -u '{original_tmp_path}' '{current_tmp_path}' || true"
        diff_result = run_shell_command(diff_cmd)

        # Clean up temporary files
        os.unlink(original_tmp_path)
        os.unlink(current_tmp_path)

        # Save the diff to the iteration-specific file
        diff_file_path = os.path.join(
            artifacts_dir, f"editor_iter_{iteration}_test_output_diff.txt"
        )
        with open(diff_file_path, "w") as f:
            if diff_result.stdout.strip():
                f.write(diff_result.stdout)
            else:
                f.write(
                    "No differences found between original and current test output.\n"
                )

        return diff_file_path

    except Exception as e:
        # Fallback: save error message
        diff_file_path = os.path.join(
            artifacts_dir, f"editor_iter_{iteration}_test_output_diff.txt"
        )
        with open(diff_file_path, "w") as f:
            f.write(f"Error creating test output diff: {str(e)}\n")
        return diff_file_path


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

        # Check for test output file
        test_output_file = os.path.join(
            artifacts_dir, f"editor_iter_{iter_num}_test_output.txt"
        )
        if os.path.exists(test_output_file):
            iteration_files.append(
                f"@{test_output_file} - Test execution results from iteration {iter_num}"
            )

        # Check for test output diff file
        test_diff_file = os.path.join(
            artifacts_dir, f"editor_iter_{iter_num}_test_output_diff.txt"
        )
        if os.path.exists(test_diff_file):
            iteration_files.append(
                f"@{test_diff_file} - Diff between iteration {iter_num} test output and original test output"
            )

        # Add iteration section if we found any files
        if iteration_files:
            historical_files_info += f"\n# ITERATION {iter_num} FILES:\n"
            for file_info in iteration_files:
                historical_files_info += f"{file_info}\n"

    return historical_files_info
