"""Tests for commit_workflow/cl_formatting.py - CL description formatting."""

import tempfile
from pathlib import Path

from commit_workflow.cl_formatting import format_cl_description


def test_format_cl_description_basic() -> None:
    """Test format_cl_description with basic input."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Initial description")
        temp_path = f.name

    try:
        format_cl_description(temp_path, "myproject", "b/12345")

        content = Path(temp_path).read_text()
        lines = content.split("\n")

        # First line should be [project] description
        assert lines[0] == "[myproject] Initial description"
        # Second line should be empty
        assert lines[1] == ""
        # Metadata fields
        assert "AUTOSUBMIT_BEHAVIOR=SYNC_SUBMIT" in content
        assert "BUG=b/12345" in content
        assert "MARKDOWN=true" in content
        assert "R=startblock" in content
        assert "STARTBLOCK_AUTOSUBMIT=yes" in content
        assert "WANT_LGTM=all" in content
    finally:
        Path(temp_path).unlink()


def test_format_cl_description_multiline_content() -> None:
    """Test format_cl_description preserves multiline content."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Line 1\nLine 2\nLine 3")
        temp_path = f.name

    try:
        format_cl_description(temp_path, "project", "b/99999")

        content = Path(temp_path).read_text()
        # Original content should be preserved with project prefix
        assert content.startswith("[project] Line 1\nLine 2\nLine 3")
    finally:
        Path(temp_path).unlink()


def test_format_cl_description_special_characters_in_project() -> None:
    """Test format_cl_description handles special characters in project name."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Description")
        temp_path = f.name

    try:
        format_cl_description(temp_path, "my-project_v2", "b/1")

        content = Path(temp_path).read_text()
        assert "[my-project_v2] Description" in content
    finally:
        Path(temp_path).unlink()


def test_format_cl_description_empty_content() -> None:
    """Test format_cl_description handles empty file content."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("")
        temp_path = f.name

    try:
        format_cl_description(temp_path, "proj", "b/0")

        content = Path(temp_path).read_text()
        # Should have [proj] followed by empty content and metadata
        assert content.startswith("[proj] \n")
        assert "BUG=b/0" in content
    finally:
        Path(temp_path).unlink()


def test_format_cl_description_metadata_order() -> None:
    """Test format_cl_description writes metadata in expected order."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Test")
        temp_path = f.name

    try:
        format_cl_description(temp_path, "test", "b/123")

        content = Path(temp_path).read_text()
        lines = content.split("\n")

        # Find indices of metadata lines
        autosubmit_idx = next(
            i for i, line in enumerate(lines) if "AUTOSUBMIT_BEHAVIOR" in line
        )
        bug_idx = next(i for i, line in enumerate(lines) if line.startswith("BUG="))
        markdown_idx = next(i for i, line in enumerate(lines) if "MARKDOWN" in line)

        # Verify order: AUTOSUBMIT_BEHAVIOR, BUG, MARKDOWN
        assert autosubmit_idx < bug_idx < markdown_idx
    finally:
        Path(temp_path).unlink()
