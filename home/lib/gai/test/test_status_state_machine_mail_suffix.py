"""Tests for READY TO MAIL suffix operations."""

import tempfile
from pathlib import Path

from status_state_machine import (
    add_ready_to_mail_suffix,
    remove_ready_to_mail_suffix,
    remove_workspace_suffix,
)


def _create_test_project_file(status: str = "Drafted") -> str:
    """Create a temporary project file with a test ChangeSpec."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(f"""# Test Project

## ChangeSpec

NAME: Test Feature
DESCRIPTION:
  A test feature for unit testing
PARENT: None
CL: None
STATUS: {status}
TEST TARGETS: None

---
""")
        return f.name


def test_remove_workspace_suffix_strips_ready_to_mail() -> None:
    """Test remove_workspace_suffix also strips READY TO MAIL suffix."""
    assert remove_workspace_suffix("Drafted - (!: READY TO MAIL)") == "Drafted"
    assert remove_workspace_suffix("Drafted") == "Drafted"


def test_add_ready_to_mail_suffix() -> None:
    """Test add_ready_to_mail_suffix adds the suffix."""
    project_file = _create_test_project_file("Drafted")

    try:
        result = add_ready_to_mail_suffix(project_file, "Test Feature")
        assert result is True

        with open(project_file, encoding="utf-8") as f:
            content = f.read()
            assert "STATUS: Drafted - (!: READY TO MAIL)" in content

    finally:
        Path(project_file).unlink()


def test_add_ready_to_mail_suffix_already_present() -> None:
    """Test add_ready_to_mail_suffix returns False if already present."""
    project_file = _create_test_project_file("Drafted - (!: READY TO MAIL)")

    try:
        result = add_ready_to_mail_suffix(project_file, "Test Feature")
        assert result is False

    finally:
        Path(project_file).unlink()


def test_remove_ready_to_mail_suffix() -> None:
    """Test remove_ready_to_mail_suffix removes the suffix."""
    project_file = _create_test_project_file("Drafted - (!: READY TO MAIL)")

    try:
        result = remove_ready_to_mail_suffix(project_file, "Test Feature")
        assert result is True

        with open(project_file, encoding="utf-8") as f:
            content = f.read()
            assert "STATUS: Drafted\n" in content
            assert "READY TO MAIL" not in content

    finally:
        Path(project_file).unlink()


def test_remove_ready_to_mail_suffix_not_present() -> None:
    """Test remove_ready_to_mail_suffix returns False if not present."""
    project_file = _create_test_project_file("Drafted")

    try:
        result = remove_ready_to_mail_suffix(project_file, "Test Feature")
        assert result is False

    finally:
        Path(project_file).unlink()
