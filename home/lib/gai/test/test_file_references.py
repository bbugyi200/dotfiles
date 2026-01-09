"""Tests for the file_references module."""

import os
import tempfile

import pytest
from gemini_wrapper.file_references import (
    _parse_file_refs,
    validate_file_references,
)

# Tests for _parse_file_refs


def test_parse_file_refs_empty_prompt() -> None:
    """Test parsing prompt with no file references."""
    result = _parse_file_refs("No file references here")
    assert result.absolute_paths == []
    assert result.parent_dir_paths == []
    assert result.missing_files == []
    assert result.seen_paths == {}


def test_parse_file_refs_relative_path_exists() -> None:
    """Test parsing relative path that exists."""
    # Use a file we know exists
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        temp_path = f.name
    try:
        # Get just the filename for relative path test
        cwd = os.getcwd()
        os.chdir(os.path.dirname(temp_path))
        try:
            basename = os.path.basename(temp_path)
            result = _parse_file_refs(f"Check @{basename}")
            # Should be tracked but not in missing_files
            assert basename in result.seen_paths
            assert result.missing_files == []
        finally:
            os.chdir(cwd)
    finally:
        os.unlink(temp_path)


def test_parse_file_refs_relative_path_missing() -> None:
    """Test parsing relative path that doesn't exist."""
    result = _parse_file_refs("Check @nonexistent_file_12345.txt")
    assert "nonexistent_file_12345.txt" in result.missing_files


def test_parse_file_refs_absolute_path_exists() -> None:
    """Test parsing absolute path that exists."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        temp_path = f.name
    try:
        result = _parse_file_refs(f"Check @{temp_path}")
        assert len(result.absolute_paths) == 1
        assert result.absolute_paths[0][0] == temp_path
        assert result.missing_files == []
    finally:
        os.unlink(temp_path)


def test_parse_file_refs_absolute_path_missing() -> None:
    """Test parsing absolute path that doesn't exist."""
    result = _parse_file_refs("Check @/nonexistent/path/to/file.txt")
    assert "/nonexistent/path/to/file.txt" in result.missing_files


def test_parse_file_refs_parent_dir_path() -> None:
    """Test parsing path with .. prefix."""
    result = _parse_file_refs("Check @../some/file.txt")
    assert "../some/file.txt" in result.parent_dir_paths


def test_parse_file_refs_context_dir_path() -> None:
    """Test parsing path in reserved context directory."""
    result = _parse_file_refs("Check @bb/gai/context/file.txt")
    assert "bb/gai/context/file.txt" in result.context_dir_paths


def test_parse_file_refs_duplicate_paths() -> None:
    """Test detecting duplicate file references."""
    result = _parse_file_refs("Check @file.txt and again @file.txt")
    assert result.seen_paths.get("file.txt", 0) == 2
    assert "file.txt" in result.duplicate_paths


def test_parse_file_refs_skips_urls() -> None:
    """Test that URL-like patterns are skipped."""
    result = _parse_file_refs("Visit @http://example.com")
    assert result.seen_paths == {}


def test_parse_file_refs_skips_domain_names() -> None:
    """Test that domain-like patterns are skipped."""
    result = _parse_file_refs("Email @google.com @github.io")
    assert result.seen_paths == {}


def test_parse_file_refs_at_in_middle_of_word() -> None:
    """Test that @ in middle of word is not treated as file reference."""
    result = _parse_file_refs("email@example.com")
    # The pattern requires @ to be at start or after whitespace
    assert result.seen_paths == {}


def test_parse_file_refs_tilde_expansion() -> None:
    """Test that ~ is expanded to home directory."""
    home = os.path.expanduser("~")
    # Use a file that should exist in home directory
    result = _parse_file_refs("Check @~/.bashrc")
    if os.path.exists(os.path.join(home, ".bashrc")):
        # If .bashrc exists, it should be in absolute_paths
        assert len(result.absolute_paths) == 1
    else:
        # If .bashrc doesn't exist, it should be in missing_files
        assert "~/.bashrc" in result.missing_files


# Tests for validate_file_references


def test_validate_file_references_no_refs_passes() -> None:
    """Test that prompt without file refs passes validation."""
    # Should not raise
    validate_file_references("No file references here")


def test_validate_file_references_existing_file_passes() -> None:
    """Test that existing file reference passes validation."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        temp_path = f.name
    try:
        validate_file_references(f"Check @{temp_path}")
    finally:
        os.unlink(temp_path)


def test_validate_file_references_missing_file_exits() -> None:
    """Test that missing file reference causes exit."""
    with pytest.raises(SystemExit) as exc_info:
        validate_file_references("Check @/nonexistent/path/file.txt")
    assert exc_info.value.code == 1


def test_validate_file_references_parent_dir_exits() -> None:
    """Test that parent dir path causes exit."""
    with pytest.raises(SystemExit) as exc_info:
        validate_file_references("Check @../some/file.txt")
    assert exc_info.value.code == 1


def test_validate_file_references_duplicate_exits() -> None:
    """Test that duplicate file refs cause exit."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        temp_path = f.name
    try:
        with pytest.raises(SystemExit) as exc_info:
            validate_file_references(f"Check @{temp_path} and @{temp_path}")
        assert exc_info.value.code == 1
    finally:
        os.unlink(temp_path)


def test_validate_file_references_context_dir_allowed() -> None:
    """Test that context dir refs are allowed by validate (not checked)."""
    # validate_file_references should NOT check context_dir paths
    # (only process_file_references does)
    # This should pass since context_dir check is disabled
    validate_file_references("Check @bb/gai/context/file.txt")
    # No exception = pass
