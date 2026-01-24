"""Tests for ace/tui/widgets/suffix_formatting.py - suffix display utilities."""

from unittest.mock import MagicMock, patch

from ace.tui.widgets.suffix_formatting import (
    SUFFIX_STYLES,
    _build_suffix_content,
    _strip_tmp_file_for_display,
    append_suffix_to_text,
    should_show_suffix,
)
from rich.text import Text


# Tests for _build_suffix_content
def test_build_suffix_content_suffix_only() -> None:
    """Test _build_suffix_content with only suffix."""
    assert _build_suffix_content("error msg", None) == "error msg"


def test_build_suffix_content_summary_only() -> None:
    """Test _build_suffix_content with only summary."""
    assert _build_suffix_content(None, "summary text") == "summary text"
    assert _build_suffix_content("", "summary text") == "summary text"


def test_build_suffix_content_both() -> None:
    """Test _build_suffix_content with both suffix and summary."""
    result = _build_suffix_content("error", "summary")
    assert result == "error | summary"


def test_build_suffix_content_neither() -> None:
    """Test _build_suffix_content with neither suffix nor summary."""
    assert _build_suffix_content(None, None) == ""
    assert _build_suffix_content("", None) == ""
    assert _build_suffix_content("", "") == ""


# Tests for _strip_tmp_file_for_display
def test_strip_tmp_file_for_display_with_path() -> None:
    """Test _strip_tmp_file_for_display strips tmp file path suffix."""
    content = "3 Tests Failed | http://test/OCL:123 | /tmp/tap_failed_hooks_abc123.txt"
    result = _strip_tmp_file_for_display(content)
    assert result == "3 Tests Failed | http://test/OCL:123"


def test_strip_tmp_file_for_display_without_path() -> None:
    """Test _strip_tmp_file_for_display leaves content without tmp path unchanged."""
    content = "3 Tests Failed | http://test/OCL:123"
    result = _strip_tmp_file_for_display(content)
    assert result == content


def test_strip_tmp_file_for_display_empty() -> None:
    """Test _strip_tmp_file_for_display handles empty string."""
    assert _strip_tmp_file_for_display("") == ""


# Tests for should_show_suffix
def test_should_show_suffix_none() -> None:
    """Test should_show_suffix returns False for None suffix."""
    assert should_show_suffix(None, None) is False
    assert should_show_suffix(None, "error") is False
    assert should_show_suffix(None, "running_agent") is False


def test_should_show_suffix_empty_string_no_type() -> None:
    """Test should_show_suffix returns False for empty string with no special type."""
    assert should_show_suffix("", None) is False
    assert should_show_suffix("", "error") is False
    assert should_show_suffix("", "killed_process") is False


def test_should_show_suffix_empty_string_running_agent() -> None:
    """Test should_show_suffix returns True for empty string with running_agent type."""
    assert should_show_suffix("", "running_agent") is True


def test_should_show_suffix_empty_string_running_process() -> None:
    """Test should_show_suffix returns True for empty string with running_process type."""
    assert should_show_suffix("", "running_process") is True


def test_should_show_suffix_non_empty() -> None:
    """Test should_show_suffix returns True for non-empty suffix."""
    assert should_show_suffix("some content", None) is True
    assert should_show_suffix("some content", "error") is True
    assert should_show_suffix("some content", "running_agent") is True


# Tests for append_suffix_to_text
def test_append_suffix_to_text_error() -> None:
    """Test append_suffix_to_text with error suffix type."""
    text = Text("base")
    append_suffix_to_text(text, "error", "error message")
    assert "(!: error message)" in text.plain
    # Verify styling was applied (the styled span exists)
    assert len(text._spans) > 0


def test_append_suffix_to_text_running_agent_with_content() -> None:
    """Test append_suffix_to_text with running_agent type and content."""
    text = Text("base")
    append_suffix_to_text(text, "running_agent", "agent running")
    assert "(@: agent running)" in text.plain


def test_append_suffix_to_text_running_agent_empty() -> None:
    """Test append_suffix_to_text with running_agent type but no content."""
    text = Text("base")
    append_suffix_to_text(text, "running_agent", "")
    assert "(@)" in text.plain


def test_append_suffix_to_text_running_process() -> None:
    """Test append_suffix_to_text with running_process type."""
    text = Text("base")
    append_suffix_to_text(text, "running_process", "process info")
    assert "($: process info)" in text.plain


def test_append_suffix_to_text_pending_dead_process() -> None:
    """Test append_suffix_to_text with pending_dead_process type."""
    text = Text("base")
    append_suffix_to_text(text, "pending_dead_process", "pending")
    assert "(?$: pending)" in text.plain


def test_append_suffix_to_text_killed_process() -> None:
    """Test append_suffix_to_text with killed_process type."""
    text = Text("base")
    append_suffix_to_text(text, "killed_process", "killed")
    assert "(~$: killed)" in text.plain


def test_append_suffix_to_text_killed_agent() -> None:
    """Test append_suffix_to_text with killed_agent type."""
    text = Text("base")
    append_suffix_to_text(text, "killed_agent", "terminated")
    assert "(~@: terminated)" in text.plain


def test_append_suffix_to_text_rejected_proposal() -> None:
    """Test append_suffix_to_text with rejected_proposal type."""
    text = Text("base")
    append_suffix_to_text(text, "rejected_proposal", "rejected reason")
    assert "(~!: rejected reason)" in text.plain


def test_append_suffix_to_text_summarize_complete_with_content() -> None:
    """Test append_suffix_to_text with summarize_complete type and content."""
    text = Text("base")
    append_suffix_to_text(text, "summarize_complete", "summary done")
    assert "(%: summary done)" in text.plain


def test_append_suffix_to_text_summarize_complete_empty() -> None:
    """Test append_suffix_to_text with summarize_complete type but no content."""
    text = Text("base")
    append_suffix_to_text(text, "summarize_complete", "")
    assert "(%)" in text.plain


def test_append_suffix_to_text_fallback_no_type() -> None:
    """Test append_suffix_to_text with no type falls back to plain suffix."""
    text = Text("base")
    append_suffix_to_text(text, None, "plain suffix")
    assert "(plain suffix)" in text.plain


def test_append_suffix_to_text_unknown_type() -> None:
    """Test append_suffix_to_text with unknown type falls back to plain suffix."""
    text = Text("base")
    append_suffix_to_text(text, "unknown_type", "content")
    assert "(content)" in text.plain


@patch("ace.tui.widgets.suffix_formatting.is_suffix_timestamp")
def test_append_suffix_to_text_timestamp_suffix(mock_is_timestamp: MagicMock) -> None:
    """Test append_suffix_to_text detects timestamp suffix for running_agent style."""
    mock_is_timestamp.return_value = True
    text = Text("base")
    # When suffix looks like timestamp and no explicit type, use running_agent style
    append_suffix_to_text(text, None, "241225_120000")
    assert "(@: 241225_120000)" in text.plain


@patch("ace.tui.widgets.suffix_formatting.is_entry_ref_suffix")
def test_append_suffix_to_text_entry_ref_with_check(
    mock_is_entry_ref: MagicMock,
) -> None:
    """Test append_suffix_to_text with entry_ref check enabled."""
    mock_is_entry_ref.return_value = True
    text = Text("base")
    append_suffix_to_text(text, None, "2a", check_entry_ref=True)
    assert "(2a)" in text.plain


@patch("ace.tui.widgets.suffix_formatting.is_entry_ref_suffix")
def test_append_suffix_to_text_entry_ref_check_disabled(
    mock_is_entry_ref: MagicMock,
) -> None:
    """Test append_suffix_to_text without entry_ref check."""
    mock_is_entry_ref.return_value = True
    text = Text("base")
    # Even if it looks like entry_ref, don't apply special style without check_entry_ref
    append_suffix_to_text(text, None, "2a", check_entry_ref=False)
    # is_entry_ref_suffix should not even be called when check_entry_ref is False
    # The suffix should still appear but without entry_ref style
    assert "(2a)" in text.plain


def test_append_suffix_to_text_with_summary() -> None:
    """Test append_suffix_to_text combines suffix and summary."""
    text = Text("base")
    append_suffix_to_text(text, "error", "error msg", summary="additional info")
    assert "(!: error msg | additional info)" in text.plain


def test_append_suffix_to_text_summary_only() -> None:
    """Test append_suffix_to_text with only summary."""
    text = Text("base")
    append_suffix_to_text(text, "running_process", None, summary="process summary")
    assert "($: process summary)" in text.plain


# Test SUFFIX_STYLES dict is properly defined
def test_suffix_styles_contains_expected_keys() -> None:
    """Test SUFFIX_STYLES contains all expected suffix types."""
    expected_keys = {
        "error",
        "rejected_proposal",
        "running_agent",
        "running_process",
        "pending_dead_process",
        "killed_process",
        "killed_agent",
        "summarize_complete",
        "metahook_complete",
        "entry_ref",
    }
    assert set(SUFFIX_STYLES.keys()) == expected_keys


def test_suffix_styles_values_are_strings() -> None:
    """Test SUFFIX_STYLES values are all style strings."""
    for key, value in SUFFIX_STYLES.items():
        assert isinstance(value, str), f"Style for {key} should be a string"
        assert value, f"Style for {key} should not be empty"
