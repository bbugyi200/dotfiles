"""Tests for commit_utils.modifiers module."""

import tempfile
from pathlib import Path

from commit_utils import reject_proposals_and_set_status_atomic


def _create_test_project_file(content: str) -> Path:
    """Create a temporary project file with the given content."""
    fd, path = tempfile.mkstemp(suffix=".gp")
    with open(path, "w") as f:
        f.write(content)
    return Path(path)


def test_reject_proposals_and_set_status_atomic_set_mailed() -> None:
    """Test setting status to Mailed while rejecting proposals."""
    content = """NAME: test-cl
STATUS: Drafted
COMMITS:
  (1) First commit
  (2a) Proposal A - (!: NEW PROPOSAL)
  (2b) Proposal B - (!: NEW PROPOSAL)
"""
    project_file = _create_test_project_file(content)
    try:
        result = reject_proposals_and_set_status_atomic(
            str(project_file), "test-cl", "Mailed"
        )
        assert result is True

        # Read back and verify
        with open(project_file) as f:
            new_content = f.read()

        assert "STATUS: Mailed" in new_content
        assert "(~!: NEW PROPOSAL)" in new_content
        assert "(!: NEW PROPOSAL)" not in new_content
    finally:
        project_file.unlink()


def test_reject_proposals_and_set_status_atomic_add_ready_to_mail() -> None:
    """Test adding READY TO MAIL suffix while rejecting proposals."""
    content = """NAME: test-cl
STATUS: Drafted
COMMITS:
  (1) First commit
  (2a) Proposal A - (!: NEW PROPOSAL)
"""
    project_file = _create_test_project_file(content)
    try:
        result = reject_proposals_and_set_status_atomic(
            str(project_file), "test-cl", ""
        )
        assert result is True

        # Read back and verify
        with open(project_file) as f:
            new_content = f.read()

        assert "STATUS: Drafted - (!: READY TO MAIL)" in new_content
        assert "(~!: NEW PROPOSAL)" in new_content
    finally:
        project_file.unlink()


def test_reject_proposals_and_set_status_atomic_no_proposals() -> None:
    """Test when there are no proposals to reject."""
    content = """NAME: test-cl
STATUS: Drafted
COMMITS:
  (1) First commit
  (2) Second commit
"""
    project_file = _create_test_project_file(content)
    try:
        result = reject_proposals_and_set_status_atomic(
            str(project_file), "test-cl", "Mailed"
        )
        assert result is True

        # Read back and verify - status should still be updated
        with open(project_file) as f:
            new_content = f.read()

        assert "STATUS: Mailed" in new_content
    finally:
        project_file.unlink()


def test_reject_proposals_and_set_status_atomic_wrong_cl() -> None:
    """Test when the CL name doesn't match."""
    content = """NAME: other-cl
STATUS: Drafted
COMMITS:
  (1) First commit
"""
    project_file = _create_test_project_file(content)
    try:
        result = reject_proposals_and_set_status_atomic(
            str(project_file), "test-cl", "Mailed"
        )
        # Should fail because the CL name doesn't match
        assert result is False
    finally:
        project_file.unlink()


def test_reject_proposals_and_set_status_atomic_already_has_suffix() -> None:
    """Test when status already has READY TO MAIL suffix."""
    content = """NAME: test-cl
STATUS: Drafted - (!: READY TO MAIL)
COMMITS:
  (1) First commit
"""
    project_file = _create_test_project_file(content)
    try:
        result = reject_proposals_and_set_status_atomic(
            str(project_file), "test-cl", ""
        )
        assert result is True

        # Read back and verify - should keep the existing suffix
        with open(project_file) as f:
            new_content = f.read()

        # Should not double the suffix
        assert new_content.count("(!: READY TO MAIL)") == 1
    finally:
        project_file.unlink()


def test_reject_proposals_and_set_status_atomic_multiple_changespecs() -> None:
    """Test with multiple changespecs in the file."""
    content = """NAME: first-cl
STATUS: Drafted
COMMITS:
  (1) First commit

NAME: test-cl
STATUS: Drafted
COMMITS:
  (1) First commit
  (2a) Proposal A - (!: NEW PROPOSAL)

NAME: third-cl
STATUS: Drafted
COMMITS:
  (1) Third commit
"""
    project_file = _create_test_project_file(content)
    try:
        result = reject_proposals_and_set_status_atomic(
            str(project_file), "test-cl", "Mailed"
        )
        assert result is True

        # Read back and verify
        with open(project_file) as f:
            new_content = f.read()

        # Only the target CL should be modified
        lines = new_content.split("\n")

        # Find the STATUS lines
        first_cl_status = None
        test_cl_status = None
        third_cl_status = None
        current_cl = None

        for line in lines:
            if line.startswith("NAME: "):
                current_cl = line[6:].strip()
            elif line.startswith("STATUS: "):
                if current_cl == "first-cl":
                    first_cl_status = line
                elif current_cl == "test-cl":
                    test_cl_status = line
                elif current_cl == "third-cl":
                    third_cl_status = line

        assert first_cl_status == "STATUS: Drafted"
        assert test_cl_status == "STATUS: Mailed"
        assert third_cl_status == "STATUS: Drafted"

        # Only test-cl proposals should be rejected
        assert "(~!: NEW PROPOSAL)" in new_content
    finally:
        project_file.unlink()


def test_reject_proposals_and_set_status_atomic_with_mentors_section() -> None:
    """Test that MENTORS section is handled correctly (stops in_commits)."""
    content = """NAME: test-cl
STATUS: Drafted
COMMITS:
  (1) First commit
  (2a) Proposal A - (!: NEW PROPOSAL)
MENTORS:
  mentor1@example.com
"""
    project_file = _create_test_project_file(content)
    try:
        result = reject_proposals_and_set_status_atomic(
            str(project_file), "test-cl", "Mailed"
        )
        assert result is True

        with open(project_file) as f:
            new_content = f.read()

        assert "STATUS: Mailed" in new_content
        assert "(~!: NEW PROPOSAL)" in new_content
        assert "MENTORS:" in new_content
    finally:
        project_file.unlink()
