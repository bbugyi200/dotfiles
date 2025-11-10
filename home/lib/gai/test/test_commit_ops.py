"""Tests for work workflow commit operations."""

import tempfile
from pathlib import Path

from work.commit_ops import _parse_bug_id_from_project_file, _update_cl_field


def test_parse_bug_id_from_project_file_plain_id() -> None:
    """Test parsing plain bug ID from project file."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write("BUG: 12345\n\n\nNAME: test\n")
        project_file = f.name

    try:
        bug_id = _parse_bug_id_from_project_file(project_file)
        assert bug_id == "12345"
    finally:
        Path(project_file).unlink()


def test_parse_bug_id_from_project_file_url_http() -> None:
    """Test parsing bug ID from HTTP URL format."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write("BUG: http://b/450606779\n\n\nNAME: test\n")
        project_file = f.name

    try:
        bug_id = _parse_bug_id_from_project_file(project_file)
        assert bug_id == "450606779"
    finally:
        Path(project_file).unlink()


def test_parse_bug_id_from_project_file_url_https() -> None:
    """Test parsing bug ID from HTTPS URL format."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write("BUG: https://b/987654321\n\n\nNAME: test\n")
        project_file = f.name

    try:
        bug_id = _parse_bug_id_from_project_file(project_file)
        assert bug_id == "987654321"
    finally:
        Path(project_file).unlink()


def test_parse_bug_id_from_project_file_not_found() -> None:
    """Test parsing when BUG field is not present."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write("NAME: test\nDESCRIPTION: test\n")
        project_file = f.name

    try:
        bug_id = _parse_bug_id_from_project_file(project_file)
        assert bug_id is None
    finally:
        Path(project_file).unlink()


def test_update_cl_field_success() -> None:
    """Test successfully updating CL field in a ChangeSpec."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(
            """BUG: 12345


NAME: test_feature
DESCRIPTION:
  A test feature
PARENT: None
CL: None
STATUS: Unstarted (EZ)
"""
        )
        project_file = f.name

    try:
        success, error = _update_cl_field(project_file, "test_feature", "54321")
        assert success is True
        assert error is None

        # Verify the file was updated
        with open(project_file) as f:
            content = f.read()
        assert "CL: 54321" in content
        assert "CL: None" not in content
    finally:
        Path(project_file).unlink()


def test_update_cl_field_changespec_not_found() -> None:
    """Test updating CL field when ChangeSpec doesn't exist."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(
            """BUG: 12345


NAME: test_feature
DESCRIPTION:
  A test feature
PARENT: None
CL: None
STATUS: Unstarted (EZ)
"""
        )
        project_file = f.name

    try:
        success, error = _update_cl_field(project_file, "nonexistent_feature", "54321")
        assert success is False
        assert error is not None
        assert "Could not find ChangeSpec" in error
    finally:
        Path(project_file).unlink()


def test_update_cl_field_multiple_changespecs() -> None:
    """Test updating CL field in the correct ChangeSpec when multiple exist."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(
            """BUG: 12345


NAME: feature_a
DESCRIPTION:
  First feature
PARENT: None
CL: None
STATUS: Unstarted (EZ)


NAME: feature_b
DESCRIPTION:
  Second feature
PARENT: None
CL: None
STATUS: Unstarted (TDD)
"""
        )
        project_file = f.name

    try:
        success, error = _update_cl_field(project_file, "feature_b", "99999")
        assert success is True
        assert error is None

        # Verify only feature_b was updated
        with open(project_file) as f:
            lines = f.readlines()

        # Find lines with CL fields
        cl_lines = [line for line in lines if line.startswith("CL:")]
        assert len(cl_lines) == 2
        assert "CL: None\n" in cl_lines  # feature_a unchanged
        assert "CL: 99999\n" in cl_lines  # feature_b updated
    finally:
        Path(project_file).unlink()
