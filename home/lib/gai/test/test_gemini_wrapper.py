"""Tests for gemini_wrapper module."""

from unittest.mock import MagicMock, patch

from gemini_wrapper import process_xfile_references


def testprocess_xfile_references_no_pattern() -> None:
    """Test that prompts without x:: pattern are returned unchanged."""
    prompt = "This is a regular prompt without any xfile references."
    result = process_xfile_references(prompt)
    assert result == prompt


def testprocess_xfile_references_with_pattern() -> None:
    """Test that prompts with x:: pattern are processed through xfile."""
    prompt = "Here are some files: x::myfiles"
    expected_output = (
        "Here are some files: ### Context Files\n+ @file1.txt\n+ @file2.txt"
    )

    # Mock subprocess.Popen
    mock_process = MagicMock()
    mock_process.communicate.return_value = (expected_output, "")
    mock_process.returncode = 0

    with patch("gemini_wrapper.subprocess.Popen", return_value=mock_process):
        result = process_xfile_references(prompt)

    assert result == expected_output
    mock_process.communicate.assert_called_once_with(input=prompt)


def testprocess_xfile_references_xfile_error() -> None:
    """Test that errors from xfile command return original prompt."""
    prompt = "Here are some files: x::myfiles"

    # Mock subprocess.Popen to simulate xfile failure
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("", "xfile error")
    mock_process.returncode = 1

    with patch("gemini_wrapper.subprocess.Popen", return_value=mock_process):
        with patch("gemini_wrapper.print_status"):  # Suppress error message
            result = process_xfile_references(prompt)

    assert result == prompt  # Should return original prompt on error


def testprocess_xfile_references_xfile_not_found() -> None:
    """Test that FileNotFoundError returns original prompt."""
    prompt = "Here are some files: x::myfiles"

    # Mock subprocess.Popen to raise FileNotFoundError
    with patch(
        "gemini_wrapper.subprocess.Popen",
        side_effect=FileNotFoundError("xfile not found"),
    ):
        with patch("gemini_wrapper.print_status"):  # Suppress error message
            result = process_xfile_references(prompt)

    assert result == prompt  # Should return original prompt when xfile not found


def testprocess_xfile_references_exception() -> None:
    """Test that general exceptions return original prompt."""
    prompt = "Here are some files: x::myfiles"

    # Mock subprocess.Popen to raise a general exception
    with patch(
        "gemini_wrapper.subprocess.Popen", side_effect=Exception("Unexpected error")
    ):
        with patch("gemini_wrapper.print_status"):  # Suppress error message
            result = process_xfile_references(prompt)

    assert result == prompt  # Should return original prompt on exception
