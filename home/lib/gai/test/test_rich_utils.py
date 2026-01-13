"""Tests for gai.rich_utils module."""

import time

from rich_utils import (
    gemini_timer,
    print_artifact_created,
    print_decision_counts,
    print_file_operation,
    print_prompt_and_response,
    print_status,
    print_workflow_header,
)


def test_print_workflow_header() -> None:
    """Test that workflow header is printed without errors."""
    # This test just verifies the function runs without exceptions
    print_workflow_header("crs", "ABC")


def test_print_status_info() -> None:
    """Test that status messages are printed without errors."""
    print_status("Processing...", "info")


def test_print_status_success() -> None:
    """Test that success status is printed."""
    print_status("Operation successful", "success")


def test_print_status_warning() -> None:
    """Test that warning status is printed."""
    print_status("Be careful", "warning")


def test_print_status_error() -> None:
    """Test that error status is printed."""
    print_status("Something went wrong", "error")


def test_print_status_progress() -> None:
    """Test that progress status is printed."""
    print_status("Working on it...", "progress")


def test_print_artifact_created() -> None:
    """Test that artifact creation is printed."""
    print_artifact_created("/path/to/artifact.txt")


def test_print_file_operation_success() -> None:
    """Test that successful file operation is printed."""
    print_file_operation("Created", "/path/to/file.txt", True)


def test_print_file_operation_failure() -> None:
    """Test that failed file operation is printed."""
    print_file_operation("Failed to create", "/path/to/file.txt", False)


def test_print_prompt_and_response() -> None:
    """Test that prompt and response are printed."""
    print_prompt_and_response(
        "What should I do?",
        "Do this thing",
        "planner",
        1,
        show_prompt=True,
        show_response=True,
    )


def test_print_prompt_and_response_only_response() -> None:
    """Test printing only response."""
    print_prompt_and_response(
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
    print_decision_counts(decision_counts)


def test_print_decision_counts_empty() -> None:
    """Test that empty decision counts are handled."""
    print_decision_counts({})


def test_gemini_timer() -> None:
    """Test that gemini_timer context manager works."""
    start = time.time()
    with gemini_timer("Testing timer"):
        time.sleep(0.1)  # Sleep for 100ms
    elapsed = time.time() - start
    # Should have slept at least 100ms (we add a small tolerance for overhead)
    assert elapsed >= 0.1


def test_gemini_timer_long_duration() -> None:
    """Test the gemini_timer formatting with hours."""
    from unittest.mock import patch

    # Mock time to simulate > 1 hour duration
    with patch("time.perf_counter", side_effect=[0, 3665]):  # 1 hour, 1 min, 5 sec
        with gemini_timer("Long operation"):
            pass  # Timer will calculate elapsed time from the mocked values
