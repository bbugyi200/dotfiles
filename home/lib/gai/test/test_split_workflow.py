"""Tests for the split_workflow module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from ace.changespec import ChangeSpec
from ace.split_workflow import SplitWorkflow
from ace.split_workflow.spec import archive_spec_file
from ace.split_workflow.utils import (
    get_editor,
    get_splits_directory,
    has_children,
)
from gai_utils import generate_timestamp


def _create_test_changespec(
    name: str = "test_feature",
    parent: str | None = None,
    status: str = "Drafted",
) -> ChangeSpec:
    """Create a test ChangeSpec."""
    return ChangeSpec(
        name=name,
        description="Test description",
        parent=parent,
        cl=None,
        status=status,
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
    )


def test_generate_timestamp() -> None:
    """Test generate_timestamp returns valid format."""
    timestamp = generate_timestamp()

    # Should be 13 characters: YYmmdd_HHMMSS
    assert len(timestamp) == 13
    # Should have underscore at position 6
    assert timestamp[6] == "_"
    # Date and time parts should be digits
    assert timestamp[:6].isdigit()
    assert timestamp[7:].isdigit()


def test_get_splits_directory() -> None:
    """Test get_splits_directory returns expected path."""
    splits_dir = get_splits_directory()

    assert splits_dir.endswith(".gai/splits")
    assert splits_dir.startswith(str(Path.home()))


def test_archive_spec_file() -> None:
    """Test archive_spec_file saves spec and returns path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("ace.split_workflow.spec.get_splits_directory", return_value=tmpdir):
            spec_content = "- name: test\n  description: Test\n  files:\n    - a.py"
            archive_path = archive_spec_file("myfeature", spec_content, "251221_123456")

            # Check the file was created
            expected_path = os.path.join(tmpdir, "myfeature-251221_123456.yml")
            assert os.path.exists(expected_path)

            # Check content was written
            with open(expected_path) as f:
                assert f.read() == spec_content

            # Check returned path contains ~
            assert "~" in archive_path or tmpdir in archive_path


def test_has_children_with_no_children() -> None:
    """Test has_children returns False when no children exist."""
    parent = _create_test_changespec(name="parent_cl")
    unrelated = _create_test_changespec(name="other_cl")

    with patch(
        "ace.split_workflow.utils.find_all_changespecs",
        return_value=[parent, unrelated],
    ):
        assert has_children("parent_cl") is False


def test_has_children_with_children() -> None:
    """Test has_children returns True when children exist."""
    parent = _create_test_changespec(name="parent_cl")
    child = _create_test_changespec(name="child_cl", parent="parent_cl")

    with patch(
        "ace.split_workflow.utils.find_all_changespecs", return_value=[parent, child]
    ):
        assert has_children("parent_cl") is True


def test_has_children_ignores_reverted_children() -> None:
    """Test has_children returns False when only child is Reverted."""
    parent = _create_test_changespec(name="parent_cl")
    reverted_child = _create_test_changespec(
        name="child_cl__1", parent="parent_cl", status="Reverted"
    )

    with patch(
        "ace.split_workflow.utils.find_all_changespecs",
        return_value=[parent, reverted_child],
    ):
        assert has_children("parent_cl") is False


def test_get_editor_from_env() -> None:
    """Test get_editor uses EDITOR environment variable."""
    with patch.dict(os.environ, {"EDITOR": "nano"}):
        assert get_editor() == "nano"


def test_get_editor_fallback_to_vim() -> None:
    """Test get_editor falls back to vim when nvim not available."""
    with patch.dict(os.environ, {}, clear=True):
        # Clear EDITOR
        if "EDITOR" in os.environ:
            del os.environ["EDITOR"]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)  # nvim not found
            editor = get_editor()
            assert editor == "vim"


def test_split_workflow_init() -> None:
    """Test SplitWorkflow initialization."""
    workflow = SplitWorkflow(
        name="my_feature",
        spec_path="/path/to/spec.yml",
        create_spec=False,
    )

    assert workflow._cl_name == "my_feature"
    assert workflow._spec_path == "/path/to/spec.yml"
    assert workflow._create_spec is False


def test_split_workflow_name_property() -> None:
    """Test SplitWorkflow.name property."""
    workflow = SplitWorkflow(name=None, spec_path=None, create_spec=True)
    assert workflow.name == "split"


def test_split_workflow_description_property() -> None:
    """Test SplitWorkflow.description property."""
    workflow = SplitWorkflow(name=None, spec_path=None, create_spec=True)
    assert workflow.description == "Split a CL into multiple smaller CLs"
