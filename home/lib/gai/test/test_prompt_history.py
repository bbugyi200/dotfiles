"""Tests for prompt history functionality."""

from pathlib import Path
from unittest.mock import patch

from prompt_history import (
    _format_prompt_for_display,
    _load_prompt_history,
    _PromptEntry,
    _save_prompt_history,
    add_or_update_prompt,
    get_prompts_for_fzf,
)


def test_load_empty_when_no_file(tmp_path: Path) -> None:
    """Test loading returns empty list when no file exists."""
    with patch("prompt_history._PROMPT_HISTORY_FILE", tmp_path / "nonexistent.json"):
        result = _load_prompt_history()
        assert result == []


def test_save_and_load_prompt(tmp_path: Path) -> None:
    """Test saving and loading a prompt."""
    test_file = tmp_path / "prompt_history.json"
    with patch("prompt_history._PROMPT_HISTORY_FILE", test_file):
        entry = _PromptEntry(
            text="test prompt",
            branch_or_workspace="main",
            timestamp="251231_143052",
            last_used="251231_143052",
        )
        assert _save_prompt_history([entry])
        result = _load_prompt_history()
        assert len(result) == 1
        assert result[0].text == "test prompt"
        assert result[0].branch_or_workspace == "main"


def test_save_multiple_prompts(tmp_path: Path) -> None:
    """Test saving multiple prompts."""
    test_file = tmp_path / "prompt_history.json"
    with patch("prompt_history._PROMPT_HISTORY_FILE", test_file):
        entries = [
            _PromptEntry(
                text="prompt 1",
                branch_or_workspace="main",
                timestamp="251231_143052",
                last_used="251231_143052",
            ),
            _PromptEntry(
                text="prompt 2",
                branch_or_workspace="feature",
                timestamp="251231_143053",
                last_used="251231_143053",
            ),
        ]
        assert _save_prompt_history(entries)
        result = _load_prompt_history()
        assert len(result) == 2
        assert result[0].text == "prompt 1"
        assert result[1].text == "prompt 2"


def test_add_new_prompt(tmp_path: Path) -> None:
    """Test adding a new prompt to history."""
    test_file = tmp_path / "prompt_history.json"
    with (
        patch("prompt_history._PROMPT_HISTORY_FILE", test_file),
        patch("prompt_history._get_current_branch_or_workspace", return_value="main"),
        patch("prompt_history._get_workspace_name", return_value="myproject"),
        patch("prompt_history.generate_timestamp", return_value="251231_143052"),
    ):
        add_or_update_prompt("test prompt")
        result = _load_prompt_history()
        assert len(result) == 1
        assert result[0].text == "test prompt"
        assert result[0].branch_or_workspace == "main"
        assert result[0].timestamp == "251231_143052"
        assert result[0].last_used == "251231_143052"
        assert result[0].workspace == "myproject"


def test_add_duplicate_updates_timestamp(tmp_path: Path) -> None:
    """Test that adding a duplicate prompt updates its last_used timestamp."""
    test_file = tmp_path / "prompt_history.json"
    with patch("prompt_history._PROMPT_HISTORY_FILE", test_file):
        # Add initial prompt
        initial_entry = _PromptEntry(
            text="test prompt",
            branch_or_workspace="main",
            timestamp="251231_100000",
            last_used="251231_100000",
        )
        _save_prompt_history([initial_entry])

        # Add the same prompt again
        with (
            patch(
                "prompt_history._get_current_branch_or_workspace", return_value="main"
            ),
            patch("prompt_history._get_workspace_name", return_value="myproject"),
            patch("prompt_history.generate_timestamp", return_value="251231_200000"),
        ):
            add_or_update_prompt("test prompt")

        result = _load_prompt_history()
        # Should still be only 1 prompt (deduplicated)
        assert len(result) == 1
        assert result[0].text == "test prompt"
        # Original timestamp should be preserved
        assert result[0].timestamp == "251231_100000"
        # last_used should be updated
        assert result[0].last_used == "251231_200000"


def test_format_prompt_for_display_current_branch() -> None:
    """Test formatting a prompt from the current branch shows asterisk."""
    entry = _PromptEntry(
        text="test prompt",
        branch_or_workspace="main",
        timestamp="251231_143052",
        last_used="251231_143052",
        workspace="myproject",
    )
    result = _format_prompt_for_display(entry, "main", "myproject", 10)
    assert result.startswith("*")
    assert "main" in result
    assert "test prompt" in result


def test_format_prompt_for_display_same_workspace() -> None:
    """Test formatting a prompt from same workspace but different branch shows tilde."""
    entry = _PromptEntry(
        text="test prompt",
        branch_or_workspace="feature",
        timestamp="251231_143052",
        last_used="251231_143052",
        workspace="myproject",
    )
    result = _format_prompt_for_display(entry, "main", "myproject", 10)
    assert result.startswith("~")
    assert "feature" in result
    assert "test prompt" in result


def test_format_prompt_for_display_other_workspace() -> None:
    """Test formatting a prompt from another workspace shows space."""
    entry = _PromptEntry(
        text="test prompt",
        branch_or_workspace="feature",
        timestamp="251231_143052",
        last_used="251231_143052",
        workspace="otherproject",
    )
    result = _format_prompt_for_display(entry, "main", "myproject", 10)
    assert result.startswith(" ")
    assert "feature" in result


def test_format_prompt_truncates_long_prompts() -> None:
    """Test that long prompts are truncated with ellipsis."""
    entry = _PromptEntry(
        text="a" * 100,
        branch_or_workspace="main",
        timestamp="251231_143052",
        last_used="251231_143052",
        workspace="myproject",
    )
    result = _format_prompt_for_display(entry, "main", "myproject", 10)
    assert "..." in result
    # Should not contain the full prompt
    assert "a" * 100 not in result


def test_format_prompt_replaces_newlines() -> None:
    """Test that newlines in prompts are replaced with spaces."""
    entry = _PromptEntry(
        text="line1\nline2\rline3",
        branch_or_workspace="main",
        timestamp="251231_143052",
        last_used="251231_143052",
        workspace="myproject",
    )
    result = _format_prompt_for_display(entry, "main", "myproject", 10)
    assert "\n" not in result
    assert "\r" not in result
    assert "line1 line2 line3" in result


def test_get_prompts_for_fzf_empty(tmp_path: Path) -> None:
    """Test get_prompts_for_fzf returns empty list when no history."""
    test_file = tmp_path / "prompt_history.json"
    with patch("prompt_history._PROMPT_HISTORY_FILE", test_file):
        result = get_prompts_for_fzf("main", "myproject")
        assert result == []


def test_get_prompts_for_fzf_sorts_current_branch_first(tmp_path: Path) -> None:
    """Test that prompts from current branch are sorted first."""
    test_file = tmp_path / "prompt_history.json"
    with patch("prompt_history._PROMPT_HISTORY_FILE", test_file):
        entries = [
            _PromptEntry(
                text="other branch prompt",
                branch_or_workspace="feature",
                timestamp="251231_143052",
                last_used="251231_200000",  # More recent
                workspace="myproject",
            ),
            _PromptEntry(
                text="current branch prompt",
                branch_or_workspace="main",
                timestamp="251231_143052",
                last_used="251231_100000",  # Less recent
                workspace="myproject",
            ),
        ]
        _save_prompt_history(entries)

        result = get_prompts_for_fzf("main", "myproject")
        assert len(result) == 2
        # Current branch should be first despite being less recent
        assert result[0][1].text == "current branch prompt"
        assert result[1][1].text == "other branch prompt"


def test_get_prompts_for_fzf_sorts_workspace_second(tmp_path: Path) -> None:
    """Test that prompts from same workspace but different branch are sorted second."""
    test_file = tmp_path / "prompt_history.json"
    with patch("prompt_history._PROMPT_HISTORY_FILE", test_file):
        entries = [
            _PromptEntry(
                text="other workspace prompt",
                branch_or_workspace="feature",
                timestamp="251231_143052",
                last_used="251231_300000",  # Most recent
                workspace="otherproject",
            ),
            _PromptEntry(
                text="same workspace prompt",
                branch_or_workspace="feature2",
                timestamp="251231_143052",
                last_used="251231_200000",  # Middle
                workspace="myproject",
            ),
            _PromptEntry(
                text="current branch prompt",
                branch_or_workspace="main",
                timestamp="251231_143052",
                last_used="251231_100000",  # Least recent
                workspace="myproject",
            ),
        ]
        _save_prompt_history(entries)

        result = get_prompts_for_fzf("main", "myproject")
        assert len(result) == 3
        # Current branch first, then same workspace, then other
        assert result[0][1].text == "current branch prompt"
        assert result[1][1].text == "same workspace prompt"
        assert result[2][1].text == "other workspace prompt"


def test_get_prompts_for_fzf_sorts_by_recency_within_branch(tmp_path: Path) -> None:
    """Test that prompts within same branch are sorted by recency."""
    test_file = tmp_path / "prompt_history.json"
    with patch("prompt_history._PROMPT_HISTORY_FILE", test_file):
        entries = [
            _PromptEntry(
                text="older prompt",
                branch_or_workspace="main",
                timestamp="251231_143052",
                last_used="251231_100000",
                workspace="myproject",
            ),
            _PromptEntry(
                text="newer prompt",
                branch_or_workspace="main",
                timestamp="251231_143052",
                last_used="251231_200000",
                workspace="myproject",
            ),
        ]
        _save_prompt_history(entries)

        result = get_prompts_for_fzf("main", "myproject")
        assert len(result) == 2
        # Newer prompt should be first
        assert result[0][1].text == "newer prompt"
        assert result[1][1].text == "older prompt"


def test_handles_corrupt_json(tmp_path: Path) -> None:
    """Test that corrupt JSON files are handled gracefully."""
    test_file = tmp_path / "prompt_history.json"
    test_file.write_text("not valid json {")
    with patch("prompt_history._PROMPT_HISTORY_FILE", test_file):
        result = _load_prompt_history()
        assert result == []


def test_handles_missing_fields_in_json(tmp_path: Path) -> None:
    """Test that JSON entries with missing fields are filtered out."""
    test_file = tmp_path / "prompt_history.json"
    test_file.write_text(
        '{"prompts": [{"text": "valid", "branch_or_workspace": "main", '
        '"timestamp": "251231_143052", "last_used": "251231_143052"}, '
        '{"text": "missing_fields"}]}'
    )
    with patch("prompt_history._PROMPT_HISTORY_FILE", test_file):
        result = _load_prompt_history()
        assert len(result) == 1
        assert result[0].text == "valid"


def test_load_handles_missing_workspace_field(tmp_path: Path) -> None:
    """Test that old entries without workspace field default to empty string."""
    test_file = tmp_path / "prompt_history.json"
    # Old format without workspace field
    test_file.write_text(
        '{"prompts": [{"text": "old prompt", "branch_or_workspace": "main", '
        '"timestamp": "251231_143052", "last_used": "251231_143052"}]}'
    )
    with patch("prompt_history._PROMPT_HISTORY_FILE", test_file):
        result = _load_prompt_history()
        assert len(result) == 1
        assert result[0].text == "old prompt"
        assert result[0].workspace == ""  # Should default to empty string


def test_save_creates_parent_directory(tmp_path: Path) -> None:
    """Test that save_prompt_history creates parent directory if needed."""
    test_file = tmp_path / "subdir" / "prompt_history.json"
    with patch("prompt_history._PROMPT_HISTORY_FILE", test_file):
        entry = _PromptEntry(
            text="test",
            branch_or_workspace="main",
            timestamp="251231_143052",
            last_used="251231_143052",
            workspace="myproject",
        )
        assert _save_prompt_history([entry])
        assert test_file.exists()
