"""Tests for gemini_wrapper module."""

import os
import tempfile
from unittest.mock import MagicMock, patch

from gemini_wrapper import _process_file_references, process_xfile_references


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


def test_process_file_references_tilde_expansion() -> None:
    """Test that tilde paths are expanded to home directory."""
    # Create a temp file to reference
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        temp_path = f.name
        f.write(b"test content")

    try:
        # Create a tilde path by replacing the home directory with ~
        home_dir = os.path.expanduser("~")
        if temp_path.startswith(home_dir):
            tilde_path = "~" + temp_path[len(home_dir) :]
        else:
            # Skip test if temp file is not under home directory
            return

        prompt = f"Check this file: @{tilde_path}"

        # Change to a temp directory to avoid issues with bb/gai/ in the actual dir
        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            try:
                with patch("gemini_wrapper.print_status"):
                    with patch("gemini_wrapper.print_file_operation"):
                        result = _process_file_references(prompt)

                # The tilde path should be replaced with a relative path to bb/gai/
                assert f"@{tilde_path}" not in result
                assert "@bb/gai/" in result

                # Check that the file was copied
                copied_file = os.path.join("bb/gai", os.path.basename(temp_path))
                assert os.path.exists(copied_file)

                # Verify content was copied correctly
                with open(copied_file) as f:
                    assert f.read() == "test content"
            finally:
                os.chdir(original_cwd)
    finally:
        os.unlink(temp_path)


def test_process_file_references_tilde_missing_file() -> None:
    """Test that missing tilde paths are reported correctly."""
    import pytest

    prompt = "Check this file: @~/nonexistent/path/to/file.txt"

    with patch("gemini_wrapper.print_status"):
        with patch("gemini_wrapper.print_file_operation"):
            # Should exit with error for missing file
            with pytest.raises(SystemExit) as exc_info:
                _process_file_references(prompt)
            assert exc_info.value.code == 1


def test_process_file_references_no_tilde() -> None:
    """Test that prompts without @ references are returned unchanged."""
    prompt = "This is a regular prompt without any file references."
    result = _process_file_references(prompt)
    assert result == prompt


def test_process_file_references_relative_path_unchanged() -> None:
    """Test that relative paths are not treated as absolute paths."""
    # Create a temp directory and file
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            # Create a relative file
            os.makedirs("test_dir", exist_ok=True)
            test_file = "test_dir/test.txt"
            with open(test_file, "w") as f:
                f.write("content")

            prompt = f"Check: @{test_file}"

            with patch("gemini_wrapper.print_status"):
                with patch("gemini_wrapper.print_file_operation"):
                    result = _process_file_references(prompt)

            # Relative path should remain unchanged (not copied to bb/gai/)
            assert f"@{test_file}" in result
            assert "bb/gai" not in result
        finally:
            os.chdir(original_cwd)
