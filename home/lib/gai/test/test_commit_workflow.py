"""Tests for commit workflow operations."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from commit_workflow import (
    _add_changespec_to_project_file,
    _changespec_exists,
    _get_editor,
    _get_project_file_path,
    _project_file_exists,
)


def test_get_project_file_path() -> None:
    """Test that project file path is correctly constructed."""
    path = _get_project_file_path("myproject")
    assert path.endswith("/.gai/projects/myproject/myproject.gp")
    assert path.startswith("/")


def test_project_file_exists_false() -> None:
    """Test project_file_exists returns False for non-existent project."""
    assert _project_file_exists("nonexistent_project_xyz123") is False


def test_project_file_exists_true() -> None:
    """Test project_file_exists returns True when file exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create the project structure
        project_dir = Path(tmpdir) / ".gai" / "projects" / "testproj"
        project_dir.mkdir(parents=True)
        project_file = project_dir / "testproj.gp"
        project_file.write_text("BUG: 12345\n")

        with patch(
            "commit_workflow._get_project_file_path", return_value=str(project_file)
        ):
            assert _project_file_exists("testproj") is True


def test_changespec_exists_no_project_file() -> None:
    """Test changespec_exists returns False when project file doesn't exist."""
    assert _changespec_exists("nonexistent_project_xyz123", "some_cl") is False


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
        with patch("commit_workflow._get_project_file_path", return_value=project_file):
            assert _changespec_exists("testproj", "existing_feature") is True
            assert _changespec_exists("testproj", "nonexistent_feature") is False
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
        with patch("commit_workflow._get_project_file_path", return_value=project_file):
            assert _changespec_exists("testproj", "feature_a") is True
            assert _changespec_exists("testproj", "feature_b") is True
            assert _changespec_exists("testproj", "feature_c") is False
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
        with patch("commit_workflow._get_project_file_path", return_value=project_file):
            result = _add_changespec_to_project_file(
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
        assert "STATUS: Needs Presubmit" in content
    finally:
        Path(project_file).unlink()


def test_add_changespec_to_project_file_none_parent() -> None:
    """Test adding a ChangeSpec with no parent."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".gp") as f:
        f.write("BUG: 12345\n")
        project_file = f.name

    try:
        with patch("commit_workflow._get_project_file_path", return_value=project_file):
            result = _add_changespec_to_project_file(
                project="testproj",
                cl_name="root_feature",
                description="A root feature",
                parent=None,
                cl_url="http://cl/99999",
            )
            assert result is True

        with open(project_file) as f:
            content = f.read()

        assert "PARENT: None" in content
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
