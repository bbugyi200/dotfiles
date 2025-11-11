"""Tests for gai.rich_utils module."""

import time

import rich_utils
from rich.progress import Progress


def test_print_workflow_header() -> None:
    """Test that workflow header is printed without errors."""
    # This test just verifies the function runs without exceptions
    rich_utils.print_workflow_header("fix-tests", "ABC")


def test_print_workflow_success() -> None:
    """Test that workflow success message is printed without errors."""
    rich_utils.print_workflow_success("fix-tests", "All tests passed")


def test_print_workflow_failure() -> None:
    """Test that workflow failure message is printed without errors."""
    rich_utils.print_workflow_failure("fix-tests", "Tests failed", "Error details")


def test_print_workflow_failure_without_details() -> None:
    """Test that workflow failure message works without details."""
    rich_utils.print_workflow_failure("fix-tests", "Tests failed")


def test_print_status_info() -> None:
    """Test that status messages are printed without errors."""
    rich_utils.print_status("Processing...", "info")


def test_print_status_success() -> None:
    """Test that success status is printed."""
    rich_utils.print_status("Operation successful", "success")


def test_print_status_warning() -> None:
    """Test that warning status is printed."""
    rich_utils.print_status("Be careful", "warning")


def test_print_status_error() -> None:
    """Test that error status is printed."""
    rich_utils.print_status("Something went wrong", "error")


def test_print_status_progress() -> None:
    """Test that progress status is printed."""
    rich_utils.print_status("Working on it...", "progress")


def test_print_command_execution_success() -> None:
    """Test that successful command execution is printed."""
    rich_utils.print_command_execution("make test", True, "All tests passed")


def test_print_command_execution_failure() -> None:
    """Test that failed command execution is printed."""
    rich_utils.print_command_execution("make test", False, "Tests failed")


def test_print_command_execution_without_output() -> None:
    """Test that command execution works without output."""
    rich_utils.print_command_execution("make test", True)


def test_create_progress_tracker() -> None:
    """Test that progress tracker is created."""
    tracker = rich_utils.create_progress_tracker("Processing", 100)
    assert isinstance(tracker, Progress)


def test_create_progress_tracker_without_total() -> None:
    """Test that progress tracker works without total."""
    tracker = rich_utils.create_progress_tracker("Processing")
    assert isinstance(tracker, Progress)


def test_print_artifact_created() -> None:
    """Test that artifact creation is printed."""
    rich_utils.print_artifact_created("/path/to/artifact.txt")


def test_print_file_operation_success() -> None:
    """Test that successful file operation is printed."""
    rich_utils.print_file_operation("Created", "/path/to/file.txt", True)


def test_print_file_operation_failure() -> None:
    """Test that failed file operation is printed."""
    rich_utils.print_file_operation("Failed to create", "/path/to/file.txt", False)


def test_print_iteration_header() -> None:
    """Test that iteration header is printed."""
    rich_utils.print_iteration_header(1, "fix-tests")


def test_print_prompt_and_response() -> None:
    """Test that prompt and response are printed."""
    rich_utils.print_prompt_and_response(
        "What should I do?",
        "Do this thing",
        "planner",
        1,
        show_prompt=True,
        show_response=True,
    )


def test_print_prompt_and_response_only_response() -> None:
    """Test printing only response."""
    rich_utils.print_prompt_and_response(
        "What should I do?",
        "Do this thing",
        "editor",
        show_prompt=False,
        show_response=True,
    )


def test_print_decision_counts() -> None:
    """Test that decision counts are printed."""
    decision_counts = {
        "new_editor": 5,
        "next_editor": 3,
        "research": 2,
    }
    rich_utils.print_decision_counts(decision_counts)


def test_print_decision_counts_empty() -> None:
    """Test that empty decision counts are handled."""
    rich_utils.print_decision_counts({})


def test_gemini_timer() -> None:
    """Test that gemini_timer context manager works."""
    start = time.time()
    with rich_utils.gemini_timer("Testing timer"):
        time.sleep(0.1)  # Sleep for 100ms
    elapsed = time.time() - start
    # Should have slept at least 100ms (we add a small tolerance for overhead)
    assert elapsed >= 0.1
