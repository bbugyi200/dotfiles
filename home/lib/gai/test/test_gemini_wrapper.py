"""Tests for gemini_wrapper module."""

import os
import tempfile
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from gemini_wrapper.file_references import process_file_references

if TYPE_CHECKING:
    from pytest import CaptureFixture


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


def test_gemini_command_wrapper_model_tier_override() -> None:
    """Test that model tier can be overridden by environment variable."""
    from gemini_wrapper import GeminiCommandWrapper

    # Test default
    wrapper = GeminiCommandWrapper(model_tier="little")
    assert wrapper.model_tier == "little"
    # Backward-compat alias
    assert wrapper.model_size == "little"

    # Test override via new env var
    os.environ["GAI_MODEL_TIER_OVERRIDE"] = "big"
    try:
        wrapper = GeminiCommandWrapper(model_tier="little")
        assert wrapper.model_tier == "big"
    finally:
        del os.environ["GAI_MODEL_TIER_OVERRIDE"]

    # Test override via legacy env var
    os.environ["GAI_MODEL_SIZE_OVERRIDE"] = "big"
    try:
        wrapper = GeminiCommandWrapper(model_tier="little")
        assert wrapper.model_tier == "big"
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

    # With no counts set, should do nothing
    wrapper._display_decision_counts()
    capsys.readouterr()  # Clear any output
    # No output expected when counts is None

    # With counts set, should call print_decision_counts
    wrapper.set_decision_counts({"yes": 5, "no": 3})
    with patch("gemini_wrapper.wrapper.print_decision_counts") as mock_print:
        wrapper._display_decision_counts()
        mock_print.assert_called_once_with({"yes": 5, "no": 3})


def test_gemini_command_wrapper_big_model_tier() -> None:
    """Test creating wrapper with big model tier."""
    from gemini_wrapper import GeminiCommandWrapper

    wrapper = GeminiCommandWrapper(model_tier="big")
    assert wrapper.model_tier == "big"
    assert wrapper.agent_type == "agent"
    assert wrapper.iteration is None
    assert wrapper.workflow_tag is None
    assert wrapper.artifacts_dir is None
    assert wrapper.suppress_output is False
