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
    assert "<=30 words" in prompt
    assert "hook failure message" in prompt
    assert "IMPORTANT" in prompt


def test_build_summarize_prompt_with_home_path() -> None:
    """Test prompt construction with home directory path."""
    prompt = _build_summarize_prompt("~/file.txt", "a COMMITS entry header")
    assert "@~/file.txt" in prompt
    assert "COMMITS entry header" in prompt


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
    workflow = SummarizeWorkflow("/path/to/file.txt", "a COMMITS entry header")
    assert workflow.name == "summarize"


def test_workflow_description() -> None:
    """Test workflow description property."""
    workflow = SummarizeWorkflow("/path/to/file.txt", "a COMMITS entry header")
    assert "30 words" in workflow.description.lower()


def test_workflow_initial_summary_is_none() -> None:
    """Test that summary is None before run()."""
    workflow = SummarizeWorkflow("/path/to/file.txt", "a COMMITS entry header")
    assert workflow.summary is None


def test_workflow_suppress_output_default_false() -> None:
    """Test that suppress_output defaults to False."""
    workflow = SummarizeWorkflow("/path/to/file.txt", "a COMMITS entry header")
    assert workflow.suppress_output is False


def test_workflow_suppress_output_true() -> None:
    """Test that suppress_output can be set to True."""
    workflow = SummarizeWorkflow(
        "/path/to/file.txt", "a COMMITS entry header", suppress_output=True
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
            artifacts_dir=None,
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


def test_get_file_summary_passes_artifacts_dir() -> None:
    """Test that get_file_summary passes artifacts_dir to SummarizeWorkflow."""
    with patch("summarize_utils.SummarizeWorkflow") as mock_workflow_class:
        mock_workflow = MagicMock()
        mock_workflow.run.return_value = True
        mock_workflow.summary = "Test summary"
        mock_workflow_class.return_value = mock_workflow

        get_file_summary(
            target_file="/path/to/file.txt",
            usage="a test",
            artifacts_dir="/path/to/artifacts",
        )

        mock_workflow_class.assert_called_once_with(
            target_file="/path/to/file.txt",
            usage="a test",
            suppress_output=True,
            artifacts_dir="/path/to/artifacts",
        )


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


# Tests for SummarizeWorkflow.run() method
@patch("summarize_workflow.invoke_agent")
def test_workflow_run_success(mock_invoke: MagicMock) -> None:
    """Test successful workflow run."""
    mock_response = MagicMock()
    mock_response.content = "Fixed typo in config"
    mock_invoke.return_value = mock_response

    workflow = SummarizeWorkflow("/path/to/file.txt", "a COMMITS entry header")
    result = workflow.run()

    assert result is True
    assert workflow.summary == "Fixed typo in config"
    mock_invoke.assert_called_once()


@patch("summarize_workflow.invoke_agent")
def test_workflow_run_empty_response(mock_invoke: MagicMock) -> None:
    """Test workflow run with empty response."""
    mock_response = MagicMock()
    mock_response.content = ""
    mock_invoke.return_value = mock_response

    workflow = SummarizeWorkflow("/path/to/file.txt", "a COMMITS entry header")
    result = workflow.run()

    assert result is False
    assert workflow.summary == ""


@patch("summarize_workflow.invoke_agent")
def test_workflow_run_with_artifacts_dir(mock_invoke: MagicMock) -> None:
    """Test workflow run passes artifacts_dir to invoke_agent."""
    mock_response = MagicMock()
    mock_response.content = "Fixed typo"
    mock_invoke.return_value = mock_response

    workflow = SummarizeWorkflow(
        "/path/to/file.txt", "a test", artifacts_dir="/artifacts"
    )
    workflow.run()

    mock_invoke.assert_called_once()
    call_kwargs = mock_invoke.call_args.kwargs
    assert call_kwargs.get("artifacts_dir") == "/artifacts"


@patch("summarize_workflow.invoke_agent")
def test_workflow_run_strips_preamble(mock_invoke: MagicMock) -> None:
    """Test workflow run strips preamble from response."""
    mock_response = MagicMock()
    mock_response.content = "Here is the summary: Fixed typo"
    mock_invoke.return_value = mock_response

    workflow = SummarizeWorkflow("/path/to/file.txt", "a test")
    result = workflow.run()

    assert result is True
    assert workflow.summary == "Fixed typo"


# Tests for main() function
@patch("summarize_workflow.SummarizeWorkflow")
@patch("sys.argv", ["summarize_workflow.py", "/path/to/file.txt", "a COMMITS header"])
def test_main_success(mock_workflow_class: MagicMock) -> None:
    """Test main() with successful workflow."""
    mock_workflow = MagicMock()
    mock_workflow.run.return_value = True
    mock_workflow.summary = "Fixed typo"
    mock_workflow_class.return_value = mock_workflow

    import pytest
    from summarize_workflow import main

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0


@patch("summarize_workflow.SummarizeWorkflow")
@patch("sys.argv", ["summarize_workflow.py", "/path/to/file.txt", "a test"])
def test_main_failure(mock_workflow_class: MagicMock) -> None:
    """Test main() with failed workflow."""
    mock_workflow = MagicMock()
    mock_workflow.run.return_value = False
    mock_workflow.summary = None
    mock_workflow_class.return_value = mock_workflow

    import pytest
    from summarize_workflow import main

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1


@patch("sys.argv", ["summarize_workflow.py"])
def test_main_missing_args() -> None:
    """Test main() with missing arguments."""
    import pytest
    from summarize_workflow import main

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1


@patch("sys.argv", ["summarize_workflow.py", "/path/to/file.txt"])
def test_main_missing_usage_arg() -> None:
    """Test main() with missing usage argument."""
    import pytest
    from summarize_workflow import main

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
