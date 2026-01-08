"""Tests for commit workflow operations."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from commit_workflow.changespec_operations import (
    _find_changespec_end_line,
    add_changespec_to_project_file,
)
from commit_workflow.changespec_queries import changespec_exists, project_file_exists
from commit_workflow.editor_utils import _get_editor
from workflow_utils import get_project_file_path


def testget_project_file_path() -> None:
    """Test that project file path is correctly constructed."""
    path = get_project_file_path("myproject")
    assert path.endswith("/.gai/projects/myproject/myproject.gp")
    assert path.startswith("/")


def test_project_file_exists_false() -> None:
    """Test project_file_exists returns False for non-existent project."""
    assert project_file_exists("nonexistent_project_xyz123") is False


def test_project_file_exists_true() -> None:
    """Test project_file_exists returns True when file exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create the project structure
        project_dir = Path(tmpdir) / ".gai" / "projects" / "testproj"
        project_dir.mkdir(parents=True)
        project_file = project_dir / "testproj.gp"
        project_file.write_text("BUG: 12345\n")

        with patch(
            "commit_workflow.changespec_queries.get_project_file_path",
            return_value=str(project_file),
        ):
            assert project_file_exists("testproj") is True


def test_changespec_exists_no_project_file() -> None:
    """Test changespec_exists returns False when project file doesn't exist."""
    assert changespec_exists("nonexistent_project_xyz123", "some_cl") is False


def test_changespec_exists_name_found() -> None:
    """Test changespec_exists returns True when NAME is found."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".gp") as f:
        f.write("BUG: 12345\n\n")
        f.write("NAME: existing_feature\n")
        f.write("DESCRIPTION:\n  A feature\n")
        f.write("PARENT: None\n")
        f.write("CL: None\n")
        f.write("STATUS: Unstarted\n")
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_queries.get_project_file_path",
            return_value=project_file,
        ):
            assert changespec_exists("testproj", "existing_feature") is True
            assert changespec_exists("testproj", "nonexistent_feature") is False
    finally:
        Path(project_file).unlink()


def test_changespec_exists_multiple_changespecs() -> None:
    """Test changespec_exists finds NAME among multiple ChangeSpecs."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".gp") as f:
        f.write("BUG: 12345\n\n")
        f.write("NAME: feature_a\n")
        f.write("DESCRIPTION:\n  Feature A\n")
        f.write("PARENT: None\n")
        f.write("CL: None\n")
        f.write("STATUS: Unstarted\n\n")
        f.write("NAME: feature_b\n")
        f.write("DESCRIPTION:\n  Feature B\n")
        f.write("PARENT: feature_a\n")
        f.write("CL: http://cl/123\n")
        f.write("STATUS: Mailed\n")
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_queries.get_project_file_path",
            return_value=project_file,
        ):
            assert changespec_exists("testproj", "feature_a") is True
            assert changespec_exists("testproj", "feature_b") is True
            assert changespec_exists("testproj", "feature_c") is False
    finally:
        Path(project_file).unlink()


def test_add_changespec_to_project_file_success() -> None:
    """Test successfully adding a ChangeSpec to project file."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".gp") as f:
        f.write("BUG: 12345\n\n")
        f.write("NAME: existing_feature\n")
        f.write("DESCRIPTION:\n  Existing feature\n")
        f.write("PARENT: None\n")
        f.write("CL: None\n")
        f.write("STATUS: Unstarted\n")
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="testproj",
                cl_name="new_feature",
                description="A new feature\nwith multiple lines",
                parent="existing_feature",
                cl_url="http://cl/54321",
            )
            assert result is True

        # Verify the file was updated correctly
        with open(project_file) as f:
            content = f.read()

        assert "NAME: new_feature" in content
        assert "  A new feature" in content
        assert "  with multiple lines" in content
        assert "PARENT: existing_feature" in content
        assert "CL: http://cl/54321" in content
        assert "STATUS: WIP" in content
    finally:
        Path(project_file).unlink()


def test_add_changespec_to_project_file_none_parent() -> None:
    """Test adding a ChangeSpec with no parent."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".gp") as f:
        f.write("BUG: 12345\n")
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="testproj",
                cl_name="root_feature",
                description="A root feature",
                parent=None,
                cl_url="http://cl/99999",
            )
            assert result is True

        with open(project_file) as f:
            content = f.read()

        # PARENT field should be absent when parent is None
        assert "PARENT:" not in content
        assert "CL: http://cl/99999" in content
    finally:
        Path(project_file).unlink()


def test_get_editor_uses_env_variable() -> None:
    """Test that _get_editor uses EDITOR environment variable."""
    with patch.dict("os.environ", {"EDITOR": "emacs"}):
        assert _get_editor() == "emacs"


def test_get_editor_falls_back_to_nvim() -> None:
    """Test that _get_editor falls back to nvim if EDITOR not set."""
    with patch.dict("os.environ", {}, clear=True):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            # Remove EDITOR from env
            with patch.dict("os.environ", {"EDITOR": ""}, clear=False):
                import os

                if "EDITOR" in os.environ:
                    del os.environ["EDITOR"]
                result = _get_editor()
                # Should be nvim since which nvim succeeds
                assert result == "nvim"


def test_get_editor_falls_back_to_vim() -> None:
    """Test that _get_editor falls back to vim if nvim not found."""
    with patch.dict("os.environ", {}, clear=True):
        mock_result = MagicMock()
        mock_result.returncode = 1  # nvim not found
        with patch("subprocess.run", return_value=mock_result):
            result = _get_editor()
            assert result == "vim"


def test_find_changespec_end_line_single_changespec() -> None:
    """Test finding end of single ChangeSpec."""
    lines = [
        "BUG: 12345\n",
        "\n",
        "NAME: feature_a\n",
        "DESCRIPTION:\n",
        "  A feature\n",
        "PARENT: None\n",
        "CL: None\n",
        "STATUS: Unstarted\n",
    ]
    assert _find_changespec_end_line(lines, "feature_a") == 7


def test_find_changespec_end_line_multiple_changespecs() -> None:
    """Test finding end of ChangeSpec when multiple exist."""
    lines = [
        "BUG: 12345\n",
        "\n",
        "NAME: feature_a\n",
        "DESCRIPTION:\n",
        "  A feature\n",
        "PARENT: None\n",
        "CL: None\n",
        "STATUS: Unstarted\n",
        "\n",
        "\n",
        "NAME: feature_b\n",
        "DESCRIPTION:\n",
        "  B feature\n",
        "PARENT: feature_a\n",
        "CL: http://cl/123\n",
        "STATUS: Mailed\n",
    ]
    # feature_a ends at line 7 (STATUS: Unstarted)
    assert _find_changespec_end_line(lines, "feature_a") == 7
    # feature_b ends at line 15 (STATUS: Mailed)
    assert _find_changespec_end_line(lines, "feature_b") == 15


def test_find_changespec_end_line_not_found() -> None:
    """Test when ChangeSpec is not found."""
    lines = [
        "BUG: 12345\n",
        "\n",
        "NAME: feature_a\n",
        "STATUS: Unstarted\n",
    ]
    assert _find_changespec_end_line(lines, "nonexistent") is None


def test_add_changespec_placed_after_parent() -> None:
    """Test that ChangeSpec is placed directly after its parent."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".gp") as f:
        f.write("BUG: 12345\n\n")
        f.write("NAME: feature_a\n")
        f.write("DESCRIPTION:\n  Feature A\n")
        f.write("PARENT: None\n")
        f.write("CL: http://cl/111\n")
        f.write("STATUS: Mailed\n\n")
        f.write("NAME: feature_c\n")
        f.write("DESCRIPTION:\n  Feature C\n")
        f.write("PARENT: feature_a\n")
        f.write("CL: http://cl/333\n")
        f.write("STATUS: Unstarted\n")
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="testproj",
                cl_name="feature_b",
                description="Feature B",
                parent="feature_a",
                cl_url="http://cl/222",
            )
            assert result is True

        # Read and verify order
        with open(project_file) as f:
            content = f.read()

        # feature_b should appear between feature_a and feature_c
        pos_a = content.find("NAME: feature_a")
        pos_b = content.find("NAME: feature_b")
        pos_c = content.find("NAME: feature_c")

        assert pos_a < pos_b < pos_c
    finally:
        Path(project_file).unlink()


def test_add_changespec_no_parent_placed_at_bottom() -> None:
    """Test that ChangeSpec with no parent is placed at bottom."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".gp") as f:
        f.write("BUG: 12345\n\n")
        f.write("NAME: existing_feature\n")
        f.write("DESCRIPTION:\n  Existing feature\n")
        f.write("PARENT: None\n")
        f.write("CL: http://cl/111\n")
        f.write("STATUS: Mailed\n")
        project_file = f.name

    try:
        with patch(
            "commit_workflow.changespec_operations.get_project_file_path",
            return_value=project_file,
        ):
            result = add_changespec_to_project_file(
                project="testproj",
                cl_name="new_root_feature",
                description="New root feature",
                parent=None,
                cl_url="http://cl/999",
            )
            assert result is True

        # Read and verify order
        with open(project_file) as f:
            content = f.read()

        # new_root_feature should appear after existing_feature (at bottom)
        pos_new = content.find("NAME: new_root_feature")
        pos_existing = content.find("NAME: existing_feature")

        assert pos_existing < pos_new
    finally:
        Path(project_file).unlink()
