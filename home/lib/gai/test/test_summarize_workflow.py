"""Tests for summarize_workflow module."""

from unittest.mock import MagicMock, patch

from summarize_utils import get_file_summary
from summarize_workflow import (
    SummarizeWorkflow,
    _build_summarize_prompt,
    _extract_summary,
)


# Tests for _build_summarize_prompt
def test_build_summarize_prompt_basic() -> None:
    """Test basic prompt construction."""
    prompt = _build_summarize_prompt("/path/to/file.txt", "a hook failure message")
    assert "@/path/to/file.txt" in prompt
    assert "<=20 words" in prompt
    assert "hook failure message" in prompt
    assert "IMPORTANT" in prompt


def test_build_summarize_prompt_with_home_path() -> None:
    """Test prompt construction with home directory path."""
    prompt = _build_summarize_prompt("~/file.txt", "a HISTORY entry header")
    assert "@~/file.txt" in prompt
    assert "HISTORY entry header" in prompt


# Tests for _extract_summary
def test_extract_summary_clean() -> None:
    """Test extracting a clean summary with no preamble."""
    result = _extract_summary("Fixed typo in config file")
    assert result == "Fixed typo in config file"


def test_extract_summary_with_preamble() -> None:
    """Test extracting summary with 'Here is the summary:' preamble."""
    result = _extract_summary("Here is the summary: Fixed typo in config file")
    assert result == "Fixed typo in config file"


def test_extract_summary_with_summary_prefix() -> None:
    """Test extracting summary with 'Summary:' prefix."""
    result = _extract_summary("Summary: Fixed typo in config file")
    assert result == "Fixed typo in config file"


def test_extract_summary_with_quotes() -> None:
    """Test extracting summary wrapped in double quotes."""
    result = _extract_summary('"Fixed typo in config file"')
    assert result == "Fixed typo in config file"


def test_extract_summary_with_single_quotes() -> None:
    """Test extracting summary wrapped in single quotes."""
    result = _extract_summary("'Fixed typo in config file'")
    assert result == "Fixed typo in config file"


def test_extract_summary_with_whitespace() -> None:
    """Test extracting summary with leading/trailing whitespace."""
    result = _extract_summary("  Fixed typo in config file  \n")
    assert result == "Fixed typo in config file"


def test_extract_summary_case_insensitive_preamble() -> None:
    """Test that preamble removal is case-insensitive."""
    result = _extract_summary("HERE IS THE SUMMARY: Fixed typo")
    assert result == "Fixed typo"


# Tests for SummarizeWorkflow class
def test_workflow_name() -> None:
    """Test workflow name property."""
    workflow = SummarizeWorkflow("/path/to/file.txt", "a HISTORY entry header")
    assert workflow.name == "summarize"


def test_workflow_description() -> None:
    """Test workflow description property."""
    workflow = SummarizeWorkflow("/path/to/file.txt", "a HISTORY entry header")
    assert "20 words" in workflow.description.lower()


def test_workflow_initial_summary_is_none() -> None:
    """Test that summary is None before run()."""
    workflow = SummarizeWorkflow("/path/to/file.txt", "a HISTORY entry header")
    assert workflow.summary is None


def test_workflow_suppress_output_default_false() -> None:
    """Test that suppress_output defaults to False."""
    workflow = SummarizeWorkflow("/path/to/file.txt", "a HISTORY entry header")
    assert workflow.suppress_output is False


def test_workflow_suppress_output_true() -> None:
    """Test that suppress_output can be set to True."""
    workflow = SummarizeWorkflow(
        "/path/to/file.txt", "a HISTORY entry header", suppress_output=True
    )
    assert workflow.suppress_output is True


# Tests for get_file_summary utility function
def test_get_file_summary_fallback_on_exception() -> None:
    """Test that get_file_summary returns fallback when workflow fails."""
    with patch("summarize_utils.SummarizeWorkflow") as mock_workflow_class:
        mock_workflow = MagicMock()
        mock_workflow.run.side_effect = Exception("Test error")
        mock_workflow_class.return_value = mock_workflow

        result = get_file_summary(
            target_file="/nonexistent/file.txt",
            usage="a test",
            fallback="Fallback text",
        )
        assert result == "Fallback text"


def test_get_file_summary_fallback_on_empty_summary() -> None:
    """Test that get_file_summary returns fallback when summary is empty."""
    with patch("summarize_utils.SummarizeWorkflow") as mock_workflow_class:
        mock_workflow = MagicMock()
        mock_workflow.run.return_value = True
        mock_workflow.summary = ""
        mock_workflow_class.return_value = mock_workflow

        result = get_file_summary(
            target_file="/path/to/file.txt",
            usage="a test",
            fallback="Fallback text",
        )
        assert result == "Fallback text"


def test_get_file_summary_returns_summary_on_success() -> None:
    """Test that get_file_summary returns the summary on success."""
    with patch("summarize_utils.SummarizeWorkflow") as mock_workflow_class:
        mock_workflow = MagicMock()
        mock_workflow.run.return_value = True
        mock_workflow.summary = "Fixed config typo"
        mock_workflow_class.return_value = mock_workflow

        result = get_file_summary(
            target_file="/path/to/file.txt",
            usage="a test",
            fallback="Fallback text",
        )
        assert result == "Fixed config typo"


def test_get_file_summary_fallback_on_run_failure() -> None:
    """Test that get_file_summary returns fallback when run() returns False."""
    with patch("summarize_utils.SummarizeWorkflow") as mock_workflow_class:
        mock_workflow = MagicMock()
        mock_workflow.run.return_value = False
        mock_workflow.summary = None
        mock_workflow_class.return_value = mock_workflow

        result = get_file_summary(
            target_file="/path/to/file.txt",
            usage="a test",
            fallback="Fallback text",
        )
        assert result == "Fallback text"


def test_get_file_summary_uses_suppress_output() -> None:
    """Test that get_file_summary passes suppress_output=True."""
    with patch("summarize_utils.SummarizeWorkflow") as mock_workflow_class:
        mock_workflow = MagicMock()
        mock_workflow.run.return_value = True
        mock_workflow.summary = "Test summary"
        mock_workflow_class.return_value = mock_workflow

        get_file_summary(
            target_file="/path/to/file.txt",
            usage="a test",
        )

        mock_workflow_class.assert_called_once_with(
            target_file="/path/to/file.txt",
            usage="a test",
            suppress_output=True,
        )


def test_get_file_summary_default_fallback() -> None:
    """Test that get_file_summary uses default fallback."""
    with patch("summarize_utils.SummarizeWorkflow") as mock_workflow_class:
        mock_workflow = MagicMock()
        mock_workflow.run.return_value = False
        mock_workflow.summary = None
        mock_workflow_class.return_value = mock_workflow

        result = get_file_summary(
            target_file="/path/to/file.txt",
            usage="a test",
        )
        assert result == "Operation completed"


# Additional edge case tests
def test_extract_summary_heres_prefix() -> None:
    """Test extracting summary with 'Here's the summary:' prefix."""
    result = _extract_summary("Here's the summary: Fixed typo")
    assert result == "Fixed typo"


def test_extract_summary_the_summary_is() -> None:
    """Test extracting summary with 'The summary is:' prefix."""
    result = _extract_summary("The summary is: Fixed typo")
    assert result == "Fixed typo"


def test_extract_summary_empty_string() -> None:
    """Test extracting empty summary."""
    result = _extract_summary("")
    assert result == ""


def test_extract_summary_whitespace_only() -> None:
    """Test extracting whitespace-only summary."""
    result = _extract_summary("   \n  ")
    assert result == ""
