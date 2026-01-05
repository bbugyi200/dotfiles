"""Tests for gemini_wrapper module."""

import os
import subprocess
import sys
import tempfile
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from gemini_wrapper import process_xfile_references
from gemini_wrapper.file_references import process_file_references

if TYPE_CHECKING:
    from pytest import CaptureFixture


def test_process_xfile_references_no_pattern() -> None:
    """Test that prompts without x:: pattern are returned unchanged."""
    prompt = "This is a regular prompt without any xfile references."
    result = process_xfile_references(prompt)
    assert result == prompt


def test_process_xfile_references_with_pattern() -> None:
    """Test that prompts with x:: pattern are processed through xfile."""
    prompt = "Here are some files: x::myfiles"
    expected_output = (
        "Here are some files: ### Context Files\n+ @file1.txt\n+ @file2.txt"
    )

    # Mock subprocess.Popen
    mock_process = MagicMock()
    mock_process.communicate.return_value = (expected_output, "")
    mock_process.returncode = 0

    with patch(
        "gemini_wrapper.file_references.subprocess.Popen", return_value=mock_process
    ):
        result = process_xfile_references(prompt)

    assert result == expected_output
    mock_process.communicate.assert_called_once_with(input=prompt)


def test_process_xfile_references_xfile_error() -> None:
    """Test that errors from xfile command cause sys.exit(1)."""
    prompt = "Here are some files: x::myfiles"

    # Mock subprocess.Popen to simulate xfile failure
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("", "xfile error message")
    mock_process.returncode = 1

    with patch(
        "gemini_wrapper.file_references.subprocess.Popen", return_value=mock_process
    ):
        with patch(
            "gemini_wrapper.file_references.print_status"
        ):  # Suppress error message
            with pytest.raises(SystemExit) as exc_info:
                process_xfile_references(prompt)
            assert exc_info.value.code == 1


def test_process_xfile_references_xfile_error_prints_stderr(
    capsys: "CaptureFixture[str]",
) -> None:
    """Test that xfile stderr is printed to stderr."""
    prompt = "Here are some files: x::myfiles"
    error_message = "detailed xfile error output"

    # Mock subprocess.Popen to simulate xfile failure
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("", error_message)
    mock_process.returncode = 1

    with patch(
        "gemini_wrapper.file_references.subprocess.Popen", return_value=mock_process
    ):
        with patch(
            "gemini_wrapper.file_references.print_status"
        ):  # Suppress status message
            with pytest.raises(SystemExit):
                process_xfile_references(prompt)

    # Verify stderr was printed
    captured = capsys.readouterr()
    assert error_message in captured.err


def test_process_xfile_references_xfile_error_empty_stderr(
    capsys: "CaptureFixture[str]",
) -> None:
    """Test that xfile error with empty stderr doesn't print extra newlines."""
    prompt = "Here are some files: x::myfiles"

    # Mock subprocess.Popen to simulate xfile failure with empty stderr
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("", "")
    mock_process.returncode = 1

    with patch(
        "gemini_wrapper.file_references.subprocess.Popen", return_value=mock_process
    ):
        with patch(
            "gemini_wrapper.file_references.print_status"
        ):  # Suppress status message
            with pytest.raises(SystemExit):
                process_xfile_references(prompt)

    # Verify no extra output was printed to stderr
    captured = capsys.readouterr()
    assert captured.err == ""


def test_process_xfile_references_xfile_not_found() -> None:
    """Test that FileNotFoundError causes sys.exit(1)."""
    prompt = "Here are some files: x::myfiles"

    # Mock subprocess.Popen to raise FileNotFoundError
    with patch(
        "gemini_wrapper.file_references.subprocess.Popen",
        side_effect=FileNotFoundError("xfile not found"),
    ):
        with patch(
            "gemini_wrapper.file_references.print_status"
        ):  # Suppress error message
            with pytest.raises(SystemExit) as exc_info:
                process_xfile_references(prompt)
            assert exc_info.value.code == 1


def test_process_xfile_references_exception() -> None:
    """Test that general exceptions cause sys.exit(1)."""
    prompt = "Here are some files: x::myfiles"

    # Mock subprocess.Popen to raise a general exception
    with patch(
        "gemini_wrapper.file_references.subprocess.Popen",
        side_effect=Exception("Unexpected error"),
    ):
        with patch(
            "gemini_wrapper.file_references.print_status"
        ):  # Suppress error message
            with pytest.raises(SystemExit) as exc_info:
                process_xfile_references(prompt)
            assert exc_info.value.code == 1


def testprocess_file_references_tilde_expansion() -> None:
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

        # Change to a temp directory to avoid issues with bb/gai/context/ in the actual dir
        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            try:
                with patch("gemini_wrapper.file_references.print_status"):
                    with patch("gemini_wrapper.file_references.print_file_operation"):
                        result = process_file_references(prompt)

                # The tilde path should be replaced with a relative path to bb/gai/context/
                assert f"@{tilde_path}" not in result
                assert "@bb/gai/context/" in result

                # Check that the file was copied
                copied_file = os.path.join(
                    "bb/gai/context", os.path.basename(temp_path)
                )
                assert os.path.exists(copied_file)

                # Verify content was copied correctly
                with open(copied_file) as f:
                    assert f.read() == "test content"
            finally:
                os.chdir(original_cwd)
    finally:
        os.unlink(temp_path)


def testprocess_file_references_tilde_missing_file() -> None:
    """Test that missing tilde paths are reported correctly."""
    prompt = "Check this file: @~/nonexistent/path/to/file.txt"

    with patch("gemini_wrapper.file_references.print_status"):
        with patch("gemini_wrapper.file_references.print_file_operation"):
            # Should exit with error for missing file
            with pytest.raises(SystemExit) as exc_info:
                process_file_references(prompt)
            assert exc_info.value.code == 1


def testprocess_file_references_no_tilde() -> None:
    """Test that prompts without @ references are returned unchanged."""
    prompt = "This is a regular prompt without any file references."
    result = process_file_references(prompt)
    assert result == prompt


def testprocess_file_references_relative_path_unchanged() -> None:
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

            with patch("gemini_wrapper.file_references.print_status"):
                with patch("gemini_wrapper.file_references.print_file_operation"):
                    result = process_file_references(prompt)

            # Relative path should remain unchanged (not copied to bb/gai/context/)
            assert f"@{test_file}" in result
            assert "bb/gai/context" not in result
        finally:
            os.chdir(original_cwd)


def testprocess_file_references_context_dir_blocked() -> None:
    """Test that referencing bb/gai/context/ directory is blocked."""
    prompt = "Check this file: @bb/gai/context/test.txt"

    with patch("gemini_wrapper.file_references.print_status"):
        with patch("gemini_wrapper.file_references.print_file_operation"):
            # Should exit with error for reserved directory
            with pytest.raises(SystemExit) as exc_info:
                process_file_references(prompt)
            assert exc_info.value.code == 1


def testprocess_file_references_context_dir_with_prefix_blocked() -> None:
    """Test that referencing ./bb/gai/context/ directory is blocked."""
    prompt = "Check this file: @./bb/gai/context/test.txt"

    with patch("gemini_wrapper.file_references.print_status"):
        with patch("gemini_wrapper.file_references.print_file_operation"):
            # Should exit with error for reserved directory
            with pytest.raises(SystemExit) as exc_info:
                process_file_references(prompt)
            assert exc_info.value.code == 1


def testprocess_file_references_at_only_after_space_or_newline() -> None:
    """Test that @ is only recognized at start of line or after whitespace."""
    # Create a temp directory and file
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            # Create a test file
            test_file = "test.txt"
            with open(test_file, "w") as f:
                f.write("content")

            # @ after space should be recognized
            prompt_space = f"Check this file: @{test_file}"
            with patch("gemini_wrapper.file_references.print_status"):
                with patch("gemini_wrapper.file_references.print_file_operation"):
                    result = process_file_references(prompt_space)
            assert f"@{test_file}" in result

            # @ at start of string should be recognized
            prompt_start = f"@{test_file} is the file"
            with patch("gemini_wrapper.file_references.print_status"):
                with patch("gemini_wrapper.file_references.print_file_operation"):
                    result = process_file_references(prompt_start)
            assert f"@{test_file}" in result

            # @ at start of newline should be recognized
            prompt_newline = f"Here is the file:\n@{test_file}"
            with patch("gemini_wrapper.file_references.print_status"):
                with patch("gemini_wrapper.file_references.print_file_operation"):
                    result = process_file_references(prompt_newline)
            assert f"@{test_file}" in result

        finally:
            os.chdir(original_cwd)


def testprocess_file_references_at_not_in_middle_of_word() -> None:
    """Test that @ in the middle of a word is NOT treated as a file reference."""
    # These should NOT be treated as file references and should not cause errors
    # even if the "file" doesn't exist
    prompt_email = "Contact user@example.com for help"
    result = process_file_references(prompt_email)
    assert result == prompt_email  # Unchanged

    prompt_embedded = "The foo@bar value is important"
    result = process_file_references(prompt_embedded)
    assert result == prompt_embedded  # Unchanged

    prompt_no_space = "Check this:@something"
    result = process_file_references(prompt_no_space)
    assert result == prompt_no_space  # Unchanged (@ not after space)


def test_log_prompt_and_response_basic() -> None:
    """Test basic logging of prompt and response."""
    from gemini_wrapper.wrapper import _log_prompt_and_response

    with tempfile.TemporaryDirectory() as tmpdir:
        _log_prompt_and_response(
            prompt="Test prompt",
            response="Test response",
            artifacts_dir=tmpdir,
            agent_type="test_agent",
        )

        # Check that the log file was created
        log_file = os.path.join(tmpdir, "gai.md")
        assert os.path.exists(log_file)

        # Check contents
        with open(log_file) as f:
            content = f.read()
        assert "Test prompt" in content
        assert "Test response" in content
        assert "test_agent" in content


def test_log_prompt_and_response_with_iteration() -> None:
    """Test logging with iteration number."""
    from gemini_wrapper.wrapper import _log_prompt_and_response

    with tempfile.TemporaryDirectory() as tmpdir:
        _log_prompt_and_response(
            prompt="Test prompt",
            response="Test response",
            artifacts_dir=tmpdir,
            agent_type="editor",
            iteration=5,
        )

        log_file = os.path.join(tmpdir, "gai.md")
        with open(log_file) as f:
            content = f.read()
        assert "iteration 5" in content


def test_log_prompt_and_response_with_workflow_tag() -> None:
    """Test logging with workflow tag."""
    from gemini_wrapper.wrapper import _log_prompt_and_response

    with tempfile.TemporaryDirectory() as tmpdir:
        _log_prompt_and_response(
            prompt="Test prompt",
            response="Test response",
            artifacts_dir=tmpdir,
            agent_type="planner",
            workflow_tag="fix-tests",
        )

        log_file = os.path.join(tmpdir, "gai.md")
        with open(log_file) as f:
            content = f.read()
        assert "tag fix-tests" in content


def test_log_prompt_and_response_appends() -> None:
    """Test that multiple logs are appended to the same file."""
    from gemini_wrapper.wrapper import _log_prompt_and_response

    with tempfile.TemporaryDirectory() as tmpdir:
        _log_prompt_and_response(
            prompt="First prompt",
            response="First response",
            artifacts_dir=tmpdir,
        )
        _log_prompt_and_response(
            prompt="Second prompt",
            response="Second response",
            artifacts_dir=tmpdir,
        )

        log_file = os.path.join(tmpdir, "gai.md")
        with open(log_file) as f:
            content = f.read()
        assert "First prompt" in content
        assert "Second prompt" in content
        assert "First response" in content
        assert "Second response" in content


def test_log_prompt_and_response_handles_error(
    capsys: "CaptureFixture[str]",
) -> None:
    """Test that logging errors are handled gracefully."""
    from gemini_wrapper.wrapper import _log_prompt_and_response

    # Try to log to a non-existent directory that can't be created
    _log_prompt_and_response(
        prompt="Test prompt",
        response="Test response",
        artifacts_dir="/nonexistent/path/that/cannot/exist",
    )

    # Should print a warning but not raise
    captured = capsys.readouterr()
    assert "Warning" in captured.out


def test_stream_process_output_basic() -> None:
    """Test basic streaming of process output."""
    from gemini_wrapper.wrapper import _stream_process_output

    # Create a simple process that outputs to stdout
    process = subprocess.Popen(
        ["echo", "hello world"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stdout, stderr, return_code = _stream_process_output(process, suppress_output=True)

    assert "hello world" in stdout
    assert stderr == ""
    assert return_code == 0


def test_stream_process_output_stderr() -> None:
    """Test streaming of process stderr."""
    from gemini_wrapper.wrapper import _stream_process_output

    # Create a process that outputs to stderr
    process = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stderr.write('error message\\n')"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stdout, stderr, return_code = _stream_process_output(process, suppress_output=True)

    assert stdout == ""
    assert "error message" in stderr
    assert return_code == 0


def test_stream_process_output_nonzero_exit() -> None:
    """Test streaming when process exits with non-zero code."""
    from gemini_wrapper.wrapper import _stream_process_output

    # Create a process that exits with error
    process = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.exit(42)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stdout, stderr, return_code = _stream_process_output(process, suppress_output=True)

    assert return_code == 42


def test_gemini_command_wrapper_set_decision_counts() -> None:
    """Test setting decision counts on the wrapper."""
    from gemini_wrapper import GeminiCommandWrapper

    wrapper = GeminiCommandWrapper()
    assert wrapper.decision_counts is None

    counts = {"yes": 5, "no": 3}
    wrapper.set_decision_counts(counts)
    assert wrapper.decision_counts == counts


def test_gemini_command_wrapper_set_logging_context() -> None:
    """Test setting logging context on the wrapper."""
    from gemini_wrapper import GeminiCommandWrapper

    wrapper = GeminiCommandWrapper()
    wrapper.set_logging_context(
        agent_type="test_agent",
        iteration=3,
        workflow_tag="test-workflow",
        artifacts_dir="/tmp/test",
        suppress_output=True,
        workflow="my-workflow",
    )

    assert wrapper.agent_type == "test_agent"
    assert wrapper.iteration == 3
    assert wrapper.workflow_tag == "test-workflow"
    assert wrapper.artifacts_dir == "/tmp/test"
    assert wrapper.suppress_output is True
    assert wrapper.workflow == "my-workflow"


def test_gemini_command_wrapper_model_size_override() -> None:
    """Test that model size can be overridden by environment variable."""
    from gemini_wrapper import GeminiCommandWrapper

    # Test default
    wrapper = GeminiCommandWrapper(model_size="little")
    assert wrapper.model_size == "little"

    # Test override
    os.environ["GAI_MODEL_SIZE_OVERRIDE"] = "big"
    try:
        wrapper = GeminiCommandWrapper(model_size="little")
        assert wrapper.model_size == "big"
    finally:
        del os.environ["GAI_MODEL_SIZE_OVERRIDE"]


def test_gemini_command_wrapper_invoke_no_query() -> None:
    """Test invoke returns error message when no HumanMessage found."""
    from gemini_wrapper import GeminiCommandWrapper
    from langchain_core.messages import AIMessage

    wrapper = GeminiCommandWrapper()
    # Pass only AIMessage, no HumanMessage
    result = wrapper.invoke([AIMessage(content="Some AI response")])
    assert "No query found in messages" in result.content


def test_gemini_command_wrapper_display_decision_counts(
    capsys: "CaptureFixture[str]",
) -> None:
    """Test that decision counts are displayed when set."""
    from gemini_wrapper import GeminiCommandWrapper

    wrapper = GeminiCommandWrapper()
    wrapper.suppress_output = False

    # With no counts set, should do nothing
    wrapper._display_decision_counts()
    capsys.readouterr()  # Clear any output
    # No output expected when counts is None

    # With counts set, should call print_decision_counts
    wrapper.set_decision_counts({"yes": 5, "no": 3})
    with patch("gemini_wrapper.wrapper.print_decision_counts") as mock_print:
        wrapper._display_decision_counts()
        mock_print.assert_called_once_with({"yes": 5, "no": 3})


def test_gemini_command_wrapper_big_model_size() -> None:
    """Test creating wrapper with big model size."""
    from gemini_wrapper import GeminiCommandWrapper

    wrapper = GeminiCommandWrapper(model_size="big")
    assert wrapper.model_size == "big"
    assert wrapper.agent_type == "agent"
    assert wrapper.iteration is None
    assert wrapper.workflow_tag is None
    assert wrapper.artifacts_dir is None
    assert wrapper.suppress_output is False
