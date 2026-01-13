"""Tests for the chat_history module."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from chat_history import (
    _generate_chat_filename,
    _get_branch_or_workspace_name,
    _get_chat_file_path,
    _increment_markdown_headings,
    list_chat_histories,
    load_chat_history,
    save_chat_history,
)
from gai_utils import ensure_gai_directory, generate_timestamp, get_gai_directory


def test_get_chats_directory() -> None:
    """Test that get_gai_directory('chats') returns the correct path."""
    result = get_gai_directory("chats")
    assert result == os.path.expanduser("~/.gai/chats")


def test_generate_timestamp() -> None:
    """Test that timestamp is in correct format."""
    timestamp = generate_timestamp()
    # Should be 13 characters: YYmmdd_HHMMSS
    assert len(timestamp) == 13
    # Should have underscore at position 6
    assert timestamp[6] == "_"
    # Date and time parts should be digits
    assert timestamp[:6].isdigit()
    assert timestamp[7:].isdigit()


def test_get_branch_or_workspace_name_success() -> None:
    """Test _get_branch_or_workspace_name with successful command."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "my-branch\n"

    with patch("chat_history.run_shell_command", return_value=mock_result):
        result = _get_branch_or_workspace_name()
        assert result == "my-branch"


def test_get_branch_or_workspace_name_failure() -> None:
    """Test _get_branch_or_workspace_name with failed command."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "command not found"

    with patch("chat_history.run_shell_command", return_value=mock_result):
        with pytest.raises(
            RuntimeError, match="Failed to get branch_or_workspace_name"
        ):
            _get_branch_or_workspace_name()


def test_generate_chat_filename_basic() -> None:
    """Test _generate_chat_filename with basic inputs."""
    with (
        patch("chat_history._get_branch_or_workspace_name", return_value="my-branch"),
        patch("chat_history.generate_timestamp", return_value="251128120000"),
    ):
        result = _generate_chat_filename("run")
        assert result == "my-branch-run-251128120000"


def test_generate_chat_filename_with_agent() -> None:
    """Test _generate_chat_filename with agent name."""
    with (
        patch("chat_history._get_branch_or_workspace_name", return_value="my-branch"),
        patch("chat_history.generate_timestamp", return_value="251128_120000"),
    ):
        # Workflow dashes are normalized to underscores in filename
        result = _generate_chat_filename("crs", agent="planner")
        assert result == "my-branch-crs-planner-251128_120000"


def test_generate_chat_filename_with_explicit_values() -> None:
    """Test _generate_chat_filename with explicit branch and timestamp."""
    result = _generate_chat_filename(
        "rerun",
        branch_or_workspace="feature-branch",
        timestamp="251128130000",
    )
    assert result == "feature-branch-rerun-251128130000"


def test_get_chat_file_path_basename() -> None:
    """Test _get_chat_file_path with basename only."""
    result = _get_chat_file_path("my-branch-run-251128120000")
    assert result == os.path.expanduser("~/.gai/chats/my-branch-run-251128120000.md")


def test_get_chat_file_path_with_extension() -> None:
    """Test _get_chat_file_path when extension is already present."""
    result = _get_chat_file_path("my-branch-run-251128120000.md")
    assert result == os.path.expanduser("~/.gai/chats/my-branch-run-251128120000.md")


def test_ensure_chats_directory() -> None:
    """Test ensure_gai_directory creates the directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_chats_dir = os.path.join(tmpdir, ".gai", "chats")
        with patch("gai_utils.get_gai_directory", return_value=test_chats_dir):
            ensure_gai_directory("chats")
            assert os.path.isdir(test_chats_dir)


def test_save_chat_history_basic() -> None:
    """Test save_chat_history creates a file with correct content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_chats_dir = os.path.join(tmpdir, "chats")
        os.makedirs(test_chats_dir)

        with patch("chat_history.get_gai_directory", return_value=test_chats_dir):
            with patch(
                "chat_history._get_branch_or_workspace_name", return_value="test-branch"
            ):
                with patch(
                    "chat_history.generate_timestamp", return_value="251128120000"
                ):
                    result = save_chat_history(
                        prompt="Hello, how are you?",
                        response="I am fine, thank you!",
                        workflow="run",
                    )

                    assert os.path.exists(result)
                    with open(result) as f:
                        content = f.read()
                    assert "Hello, how are you?" in content
                    assert "I am fine, thank you!" in content
                    assert "# Chat History - run" in content


def test_save_chat_history_with_previous_history() -> None:
    """Test save_chat_history with previous history prepended."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_chats_dir = os.path.join(tmpdir, "chats")
        os.makedirs(test_chats_dir)

        with patch("chat_history.get_gai_directory", return_value=test_chats_dir):
            with patch(
                "chat_history._get_branch_or_workspace_name", return_value="test-branch"
            ):
                with patch(
                    "chat_history.generate_timestamp", return_value="251128120000"
                ):
                    result = save_chat_history(
                        prompt="Follow up question",
                        response="Follow up answer",
                        workflow="rerun",
                        previous_history="Previous conversation content",
                    )

                    with open(result) as f:
                        content = f.read()
                    assert "Previous Conversation" in content
                    assert "Previous conversation content" in content
                    assert "Follow up question" in content


def test_load_chat_history_by_basename() -> None:
    """Test load_chat_history with basename."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_chats_dir = os.path.join(tmpdir, "chats")
        os.makedirs(test_chats_dir)

        # Create a test file
        test_file = os.path.join(test_chats_dir, "test-run-251128120000.md")
        with open(test_file, "w") as f:
            f.write("Test content")

        with patch("chat_history.get_gai_directory", return_value=test_chats_dir):
            result = load_chat_history("test-run-251128120000")
            assert result == "Test content"


def test_load_chat_history_by_full_path() -> None:
    """Test load_chat_history with full path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.md")
        with open(test_file, "w") as f:
            f.write("Full path content")

        result = load_chat_history(test_file)
        assert result == "Full path content"


def test_load_chat_history_not_found() -> None:
    """Test load_chat_history with non-existent file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_chats_dir = os.path.join(tmpdir, "chats")
        os.makedirs(test_chats_dir)

        with patch("chat_history.get_gai_directory", return_value=test_chats_dir):
            with pytest.raises(FileNotFoundError):
                load_chat_history("nonexistent-run-251128120000")


def test_list_chat_histories_empty() -> None:
    """Test list_chat_histories with no files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_chats_dir = os.path.join(tmpdir, "chats")
        os.makedirs(test_chats_dir)

        with patch("chat_history.get_gai_directory", return_value=test_chats_dir):
            result = list_chat_histories()
            assert result == []


def test_list_chat_histories_nonexistent_dir() -> None:
    """Test list_chat_histories when directory doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        nonexistent_dir = os.path.join(tmpdir, "nonexistent")

        with patch("chat_history.get_gai_directory", return_value=nonexistent_dir):
            result = list_chat_histories()
            assert result == []


def test_list_chat_histories_with_files() -> None:
    """Test list_chat_histories with multiple files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_chats_dir = os.path.join(tmpdir, "chats")
        os.makedirs(test_chats_dir)

        # Create test files
        files = ["test-run-251128120000.md", "test-run-251128130000.md"]
        for filename in files:
            filepath = os.path.join(test_chats_dir, filename)
            with open(filepath, "w") as f:
                f.write("content")

        with patch("chat_history.get_gai_directory", return_value=test_chats_dir):
            result = list_chat_histories()
            assert len(result) == 2
            assert "test-run-251128120000" in result
            assert "test-run-251128130000" in result


def test_increment_markdown_headings() -> None:
    """Test _increment_markdown_headings increments all heading levels."""
    content = "# H1\n## H2\n### H3\n#### H4\nNormal text"
    result = _increment_markdown_headings(content)
    assert result == "## H1\n### H2\n#### H3\n##### H4\nNormal text"


def test_increment_markdown_headings_no_headings() -> None:
    """Test _increment_markdown_headings with no headings."""
    content = "Just normal text\nNo headings here"
    result = _increment_markdown_headings(content)
    assert result == content


def test_load_chat_history_with_increment_headings() -> None:
    """Test load_chat_history with increment_headings=True."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.md")
        content = """# Main Title

## Section 1

Some content here.

### Subsection

More content.

#### Deep section

Even more."""
        with open(test_file, "w") as f:
            f.write(content)

        result = load_chat_history(test_file, increment_headings=True)

        # All headings should be incremented by one level
        assert "## Main Title" in result
        assert "### Section 1" in result
        assert "#### Subsection" in result
        assert "##### Deep section" in result
        # Original headings should not be present
        assert "\n# Main Title" not in result


def test_load_chat_history_without_increment_headings() -> None:
    """Test load_chat_history with increment_headings=False (default)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.md")
        content = "# Main Title\n\n## Section 1"
        with open(test_file, "w") as f:
            f.write(content)

        result = load_chat_history(test_file, increment_headings=False)

        # Headings should remain unchanged
        assert "# Main Title" in result
        assert "## Section 1" in result
