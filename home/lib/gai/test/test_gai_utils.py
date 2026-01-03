"""Tests for gai_utils module."""

import os
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from gai_utils import (
    ensure_gai_directory,
    generate_timestamp,
    get_gai_directory,
    get_workspace_directory_for_changespec,
    make_safe_filename,
    shorten_path,
    strip_reverted_suffix,
)


def test_generate_timestamp_format() -> None:
    """Test that generate_timestamp returns correct format."""
    timestamp = generate_timestamp()
    # Should be YYmmdd_HHMMSS format (13 chars with underscore at position 6)
    assert len(timestamp) == 13
    assert timestamp[6] == "_"
    # First 6 chars should be digits (date)
    assert timestamp[:6].isdigit()
    # Last 6 chars should be digits (time)
    assert timestamp[7:].isdigit()


def test_generate_timestamp_regex_pattern() -> None:
    """Test that generate_timestamp matches expected pattern."""
    timestamp = generate_timestamp()
    pattern = r"^\d{6}_\d{6}$"
    assert re.match(pattern, timestamp) is not None


def test_get_gai_directory_returns_correct_path() -> None:
    """Test that get_gai_directory returns correct path."""
    result = get_gai_directory("hooks")
    expected = os.path.expanduser("~/.gai/hooks")
    assert result == expected


def test_get_gai_directory_with_different_subdirs() -> None:
    """Test get_gai_directory with various subdirectories."""
    subdirs = ["diffs", "chats", "comments", "workflows", "splits"]
    for subdir in subdirs:
        result = get_gai_directory(subdir)
        expected = os.path.expanduser(f"~/.gai/{subdir}")
        assert result == expected


def test_ensure_gai_directory_creates_directory() -> None:
    """Test that ensure_gai_directory creates the directory."""
    # Use a unique test directory to avoid conflicts
    test_subdir = f"test_dir_{os.getpid()}"
    expected_path = os.path.expanduser(f"~/.gai/{test_subdir}")

    try:
        # Ensure directory doesn't exist yet
        if os.path.exists(expected_path):
            os.rmdir(expected_path)

        result = ensure_gai_directory(test_subdir)
        assert result == expected_path
        assert os.path.isdir(expected_path)
    finally:
        # Clean up
        if os.path.exists(expected_path):
            os.rmdir(expected_path)


def test_ensure_gai_directory_returns_path() -> None:
    """Test that ensure_gai_directory returns the correct path."""
    test_subdir = f"test_dir_return_{os.getpid()}"
    expected_path = os.path.expanduser(f"~/.gai/{test_subdir}")

    try:
        result = ensure_gai_directory(test_subdir)
        assert result == expected_path
    finally:
        if os.path.exists(expected_path):
            os.rmdir(expected_path)


def test_make_safe_filename_basic() -> None:
    """Test make_safe_filename with basic inputs."""
    assert make_safe_filename("hello_world") == "hello_world"
    assert make_safe_filename("hello") == "hello"
    assert make_safe_filename("test123") == "test123"


def test_make_safe_filename_replaces_special_chars() -> None:
    """Test make_safe_filename replaces non-alphanumeric chars."""
    assert make_safe_filename("hello-world") == "hello_world"
    assert make_safe_filename("hello.world") == "hello_world"
    assert make_safe_filename("hello/world") == "hello_world"
    assert make_safe_filename("hello world") == "hello_world"
    assert make_safe_filename("hello@world#test") == "hello_world_test"


def test_make_safe_filename_preserves_underscores() -> None:
    """Test make_safe_filename preserves existing underscores."""
    assert make_safe_filename("hello_world_test") == "hello_world_test"


def test_strip_reverted_suffix_with_suffix() -> None:
    """Test strip_reverted_suffix removes __<N> suffix."""
    assert strip_reverted_suffix("foobar__1") == "foobar"
    assert strip_reverted_suffix("foobar__2") == "foobar"
    assert strip_reverted_suffix("my_feature__10") == "my_feature"
    assert strip_reverted_suffix("test__123") == "test"


def test_strip_reverted_suffix_without_suffix() -> None:
    """Test strip_reverted_suffix returns original when no suffix."""
    assert strip_reverted_suffix("foobar") == "foobar"
    assert strip_reverted_suffix("my_feature") == "my_feature"
    assert strip_reverted_suffix("test") == "test"


def test_strip_reverted_suffix_partial_match() -> None:
    """Test strip_reverted_suffix doesn't match incomplete patterns."""
    # These should NOT be stripped
    assert strip_reverted_suffix("foobar_1") == "foobar_1"  # single underscore
    assert strip_reverted_suffix("foobar__") == "foobar__"  # no number
    assert strip_reverted_suffix("foobar__a") == "foobar__a"  # letter not number


def test_shorten_path_with_home() -> None:
    """Test shorten_path replaces home directory with ~."""
    home = str(Path.home())
    path = f"{home}/some/path/file.txt"
    result = shorten_path(path)
    assert result == "~/some/path/file.txt"


def test_shorten_path_without_home() -> None:
    """Test shorten_path returns unchanged if no home directory."""
    path = "/tmp/some/path/file.txt"
    result = shorten_path(path)
    assert result == path


def test_shorten_path_partial_home_match() -> None:
    """Test shorten_path with path that doesn't start with home."""
    home = str(Path.home())
    # Path that contains home directory but not at start
    path = f"/prefix{home}/file.txt"
    result = shorten_path(path)
    # Should still replace the home part
    assert result == "/prefix~/file.txt"


def test_get_workspace_directory_for_changespec_success() -> None:
    """Test get_workspace_directory_for_changespec with successful lookup."""
    mock_changespec = MagicMock()
    mock_changespec.file_path = "/path/to/project/test_project.gp"
    mock_changespec.project_basename = "test_project"

    with patch("running_field.get_workspace_directory") as mock_get_ws:
        mock_get_ws.return_value = "/workspace/test_project"
        result = get_workspace_directory_for_changespec(mock_changespec)
        assert result == "/workspace/test_project"
        mock_get_ws.assert_called_once_with("test_project")


def test_get_workspace_directory_for_changespec_runtime_error() -> None:
    """Test get_workspace_directory_for_changespec returns None on RuntimeError."""
    mock_changespec = MagicMock()
    mock_changespec.file_path = "/path/to/project/test_project.gp"
    mock_changespec.project_basename = "test_project"

    with patch("running_field.get_workspace_directory") as mock_get_ws:
        mock_get_ws.side_effect = RuntimeError("Workspace not found")
        result = get_workspace_directory_for_changespec(mock_changespec)
        assert result is None


def test_get_workspace_directory_for_changespec_extracts_basename() -> None:
    """Test that get_workspace_directory_for_changespec extracts project basename."""
    mock_changespec = MagicMock()
    mock_changespec.file_path = "/some/path/my_project.gp"
    mock_changespec.project_basename = "my_project"

    with patch("running_field.get_workspace_directory") as mock_get_ws:
        mock_get_ws.return_value = "/workspace/my_project"
        get_workspace_directory_for_changespec(mock_changespec)
        # Should extract "my_project" from "my_project.gp"
        mock_get_ws.assert_called_once_with("my_project")
