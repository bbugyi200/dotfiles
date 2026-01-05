"""Tests for the mentors module - MENTORS field operations."""

import tempfile
from pathlib import Path

from ace.changespec import MentorEntry, MentorStatusLine
from ace.mentors import (
    _apply_mentors_update,
    _format_mentors_field,
    add_mentor_entry,
    set_mentor_status,
)


def test_format_mentors_field_empty() -> None:
    """Test formatting empty mentors list."""
    lines = _format_mentors_field([])
    assert lines == []


def test_format_mentors_field_single_entry_no_status() -> None:
    """Test formatting single entry without status lines."""
    entry = MentorEntry(
        entry_id="1",
        profiles=["feature", "tests"],
        status_lines=None,
    )
    lines = _format_mentors_field([entry])
    assert lines == [
        "MENTORS:\n",
        "  (1) feature tests\n",
    ]


def test_format_mentors_field_with_status_lines() -> None:
    """Test formatting entry with status lines."""
    entry = MentorEntry(
        entry_id="2",
        profiles=["feature"],
        status_lines=[
            MentorStatusLine(
                profile_name="feature",
                mentor_name="complete",
                status="PASSED",
                duration="1h2m3s",
            ),
            MentorStatusLine(
                profile_name="feature",
                mentor_name="soundness",
                status="RUNNING",
                suffix="mentor_soundness-123-240601_1530",
                suffix_type="running_agent",
            ),
        ],
    )
    lines = _format_mentors_field([entry])
    assert "MENTORS:\n" in lines
    assert "  (2) feature\n" in lines
    # Check status lines are present
    assert any("PASSED" in line for line in lines)
    assert any("RUNNING" in line for line in lines)


def test_format_mentors_field_with_error_suffix() -> None:
    """Test formatting with error suffix."""
    entry = MentorEntry(
        entry_id="1",
        profiles=["test"],
        status_lines=[
            MentorStatusLine(
                profile_name="test",
                mentor_name="complete",
                status="FAILED",
                suffix="Connection error",
                suffix_type="error",
            ),
        ],
    )
    lines = _format_mentors_field([entry])
    # Should contain error marker
    assert any("!:" in line for line in lines)


def test_apply_mentors_update_new_field() -> None:
    """Test applying mentors to a file without existing MENTORS field."""
    lines = [
        "NAME: test-cl\n",
        "STATUS: Drafted\n",
        "DESCRIPTION:\n",
        "  Test description\n",
    ]
    entry = MentorEntry(entry_id="1", profiles=["test"], status_lines=None)
    updated = _apply_mentors_update(lines, "test-cl", [entry])
    # Should contain MENTORS field at the end
    content = "".join(updated)
    assert "MENTORS:" in content
    assert "(1) test" in content


def test_apply_mentors_update_replace_existing() -> None:
    """Test replacing existing MENTORS field."""
    lines = [
        "NAME: test-cl\n",
        "STATUS: Drafted\n",
        "MENTORS:\n",
        "  (1) old_profile\n",
    ]
    entry = MentorEntry(entry_id="2", profiles=["new_profile"], status_lines=None)
    updated = _apply_mentors_update(lines, "test-cl", [entry])
    content = "".join(updated)
    assert "(2) new_profile" in content
    assert "old_profile" not in content


def test_add_mentor_entry_new() -> None:
    """Test adding a new mentor entry to a file."""
    content = """NAME: test-cl
STATUS: Drafted
DESCRIPTION:
  Test description
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    result = add_mentor_entry(file_path, "test-cl", "1", ["feature"])

    assert result is True

    # Read and verify
    with open(file_path) as f:
        updated_content = f.read()

    assert "MENTORS:" in updated_content
    assert "(1) feature" in updated_content

    Path(file_path).unlink()


def test_add_mentor_entry_merge_profiles() -> None:
    """Test adding profiles to existing mentor entry."""
    content = """NAME: test-cl
STATUS: Drafted
MENTORS:
  (1) feature
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    result = add_mentor_entry(file_path, "test-cl", "1", ["tests"])

    assert result is True

    # Read and verify profiles are merged
    with open(file_path) as f:
        updated_content = f.read()

    # Should have both profiles
    assert "feature" in updated_content
    assert "tests" in updated_content

    Path(file_path).unlink()


def test_set_mentor_status_new() -> None:
    """Test setting mentor status for new mentor."""
    content = """NAME: test-cl
STATUS: Drafted
MENTORS:
  (1) feature
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    result = set_mentor_status(
        file_path,
        "test-cl",
        "1",
        "feature",
        "complete",
        status="RUNNING",
        suffix="mentor_complete-123",
        suffix_type="running_agent",
    )

    assert result is True

    with open(file_path) as f:
        updated_content = f.read()

    assert "feature:complete" in updated_content
    assert "RUNNING" in updated_content

    Path(file_path).unlink()


def test_set_mentor_status_update_existing() -> None:
    """Test updating existing mentor status."""
    content = """NAME: test-cl
STATUS: Drafted
MENTORS:
  (1) feature
      | feature:complete - RUNNING - (@: mentor_complete-123)
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    result = set_mentor_status(
        file_path,
        "test-cl",
        "1",
        "feature",
        "complete",
        status="PASSED",
        duration="1h2m3s",
    )

    assert result is True

    with open(file_path) as f:
        updated_content = f.read()

    assert "PASSED" in updated_content
    assert "1h2m3s" in updated_content

    Path(file_path).unlink()


def test_format_mentors_field_multiple_entries() -> None:
    """Test formatting multiple mentor entries."""
    entries = [
        MentorEntry(entry_id="1", profiles=["feature"], status_lines=None),
        MentorEntry(entry_id="2", profiles=["tests", "perf"], status_lines=None),
    ]
    lines = _format_mentors_field(entries)
    content = "".join(lines)
    assert "(1) feature" in content
    assert "(2) tests perf" in content


def test_format_mentors_field_with_plain_suffix() -> None:
    """Test formatting with plain suffix (no type)."""
    entry = MentorEntry(
        entry_id="1",
        profiles=["test"],
        status_lines=[
            MentorStatusLine(
                profile_name="test",
                mentor_name="complete",
                status="PASSED",
                suffix="some_suffix",
                suffix_type=None,  # Plain suffix
            ),
        ],
    )
    lines = _format_mentors_field([entry])
    content = "".join(lines)
    assert "some_suffix" in content


def test_apply_mentors_update_wrong_changespec() -> None:
    """Test that update doesn't affect other changespecs."""
    lines = [
        "NAME: other-cl\n",
        "STATUS: Drafted\n",
        "---\n",
        "NAME: test-cl\n",
        "STATUS: Mailed\n",
    ]
    entry = MentorEntry(entry_id="1", profiles=["feature"], status_lines=None)
    updated = _apply_mentors_update(lines, "test-cl", [entry])
    content = "".join(updated)
    # MENTORS should be added to test-cl, not other-cl
    assert content.count("MENTORS:") == 1


def test_set_mentor_status_creates_entry_if_missing() -> None:
    """Test that set_mentor_status creates entry if it doesn't exist."""
    content = """NAME: test-cl
STATUS: Drafted
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    result = set_mentor_status(
        file_path,
        "test-cl",
        "1",
        "feature",
        "complete",
        status="RUNNING",
    )

    assert result is True

    with open(file_path) as f:
        updated_content = f.read()

    assert "MENTORS:" in updated_content
    assert "feature:complete" in updated_content
    assert "RUNNING" in updated_content

    Path(file_path).unlink()
