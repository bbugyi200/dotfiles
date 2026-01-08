"""Tests for commit_workflow.changespec_operations module."""

import os
import tempfile
from unittest.mock import patch

from commit_workflow.changespec_operations import add_changespec_to_project_file


def test_add_changespec_with_initial_hooks() -> None:
    """Test that initial_hooks are included in the ChangeSpec block."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("BUG: b/12345\n")
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="test_project",
                cl_name="test_project_foo",
                description="Test description",
                parent=None,
                cl_url="http://cl/12345",
                initial_hooks=["!$bb_hg_presubmit", "bb_hg_lint"],
            )

        assert result is True

        with open(project_file, encoding="utf-8") as f:
            content = f.read()

        # Verify hooks are present
        assert "HOOKS:" in content
        assert "  !$bb_hg_presubmit" in content
        assert "  bb_hg_lint" in content
    finally:
        os.unlink(project_file)


def test_add_changespec_without_initial_hooks() -> None:
    """Test that ChangeSpec works without initial_hooks (backward compatible)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("BUG: b/12345\n")
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="test_project",
                cl_name="test_project_foo",
                description="Test description",
                parent=None,
                cl_url="http://cl/12345",
                # No initial_hooks parameter - backward compatible
            )

        assert result is True

        with open(project_file, encoding="utf-8") as f:
            content = f.read()

        # Verify HOOKS is NOT present when not provided
        assert "HOOKS:" not in content
    finally:
        os.unlink(project_file)


def test_add_changespec_hooks_in_correct_order() -> None:
    """Test that hooks appear in the correct order in the ChangeSpec."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("BUG: b/12345\n")
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="test_project",
                cl_name="test_project_foo",
                description="Test description",
                parent=None,
                cl_url="http://cl/12345",
                initial_hooks=[
                    "!$bb_hg_presubmit",
                    "bb_hg_lint",
                    "bb_rabbit_test //foo:test1",
                ],
            )

        assert result is True

        with open(project_file, encoding="utf-8") as f:
            content = f.read()

        # Verify order (presubmit before lint before test target)
        presubmit_idx = content.index("!$bb_hg_presubmit")
        lint_idx = content.index("bb_hg_lint")
        test_idx = content.index("bb_rabbit_test")
        assert presubmit_idx < lint_idx < test_idx
    finally:
        os.unlink(project_file)


def test_add_changespec_with_empty_hooks_list() -> None:
    """Test that empty initial_hooks list doesn't add HOOKS field."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("BUG: b/12345\n")
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="test_project",
                cl_name="test_project_foo",
                description="Test description",
                parent=None,
                cl_url="http://cl/12345",
                initial_hooks=[],  # Empty list
            )

        assert result is True

        with open(project_file, encoding="utf-8") as f:
            content = f.read()

        # Verify HOOKS is NOT present when list is empty
        assert "HOOKS:" not in content
    finally:
        os.unlink(project_file)
