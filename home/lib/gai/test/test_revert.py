"""Tests for gai.work.revert module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from work.changespec import ChangeSpec
from work.revert import (
    _get_next_reverted_suffix,
    _has_children,
    _has_valid_cl,
    revert_changespec,
)


def _create_test_changespec(
    name: str = "test_feature",
    cl: str | None = "http://cl/123456789",
    status: str = "Mailed",
    parent: str | None = None,
) -> ChangeSpec:
    """Create a test ChangeSpec."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".gp") as f:
        parent_val = parent if parent else "None"
        cl_val = cl if cl else "None"
        f.write(
            f"""# Test Project

## ChangeSpec

NAME: {name}
DESCRIPTION:
  A test feature
PARENT: {parent_val}
CL: {cl_val}
STATUS: {status}

---
"""
        )
        return ChangeSpec(
            name=name,
            description="A test feature",
            parent=parent,
            cl=cl,
            status=status,
            test_targets=None,
            kickstart=None,
            file_path=f.name,
            line_number=6,
            presubmit=None,
        )


def test__has_valid_cl_with_valid_cl() -> None:
    """Test _has_valid_cl returns True when CL is set."""
    changespec = _create_test_changespec(cl="http://cl/123456789")
    assert _has_valid_cl(changespec) is True
    Path(changespec.file_path).unlink()


def test__has_valid_cl_with_none_cl() -> None:
    """Test _has_valid_cl returns False when CL is None."""
    changespec = _create_test_changespec(cl=None)
    assert _has_valid_cl(changespec) is False
    Path(changespec.file_path).unlink()


def test__has_valid_cl_with_none_string() -> None:
    """Test _has_valid_cl returns False when CL is 'None' string."""
    changespec = _create_test_changespec()
    changespec.cl = "None"
    assert _has_valid_cl(changespec) is False
    Path(changespec.file_path).unlink()


def test__has_children_with_no_children() -> None:
    """Test _has_children returns False when no children exist."""
    parent = _create_test_changespec(name="parent_feature")
    child = _create_test_changespec(name="unrelated_feature", parent=None)
    all_changespecs = [parent, child]

    assert _has_children(parent, all_changespecs) is False

    Path(parent.file_path).unlink()
    Path(child.file_path).unlink()


def test__has_children_with_children() -> None:
    """Test _has_children returns True when children exist."""
    parent = _create_test_changespec(name="parent_feature")
    child = _create_test_changespec(name="child_feature", parent="parent_feature")
    all_changespecs = [parent, child]

    assert _has_children(parent, all_changespecs) is True

    Path(parent.file_path).unlink()
    Path(child.file_path).unlink()


def test__get_next_reverted_suffix_first_revert() -> None:
    """Test _get_next_reverted_suffix returns 1 for first revert."""
    changespec = _create_test_changespec(name="test_feature")
    all_changespecs = [changespec]

    suffix = _get_next_reverted_suffix("test_feature", all_changespecs)

    assert suffix == 1
    Path(changespec.file_path).unlink()


def test__get_next_reverted_suffix_second_revert() -> None:
    """Test _get_next_reverted_suffix returns 2 when __1 already exists."""
    original = _create_test_changespec(name="test_feature")
    reverted1 = _create_test_changespec(name="test_feature__1")
    all_changespecs = [original, reverted1]

    suffix = _get_next_reverted_suffix("test_feature", all_changespecs)

    assert suffix == 2
    Path(original.file_path).unlink()
    Path(reverted1.file_path).unlink()


def test__get_next_reverted_suffix_fills_gap() -> None:
    """Test _get_next_reverted_suffix finds lowest available number."""
    original = _create_test_changespec(name="test_feature")
    reverted2 = _create_test_changespec(name="test_feature__2")
    reverted3 = _create_test_changespec(name="test_feature__3")
    all_changespecs = [original, reverted2, reverted3]

    suffix = _get_next_reverted_suffix("test_feature", all_changespecs)

    assert suffix == 1
    Path(original.file_path).unlink()
    Path(reverted2.file_path).unlink()
    Path(reverted3.file_path).unlink()


def test_revert_changespec_fails_without_cl() -> None:
    """Test revert_changespec fails when CL is not set."""
    changespec = _create_test_changespec(cl=None)

    success, error = revert_changespec(changespec)

    assert success is False
    assert error == "ChangeSpec does not have a valid CL set"
    Path(changespec.file_path).unlink()


def test_revert_changespec_fails_with_children() -> None:
    """Test revert_changespec fails when ChangeSpec has children."""
    parent = _create_test_changespec(name="parent_feature")
    child = _create_test_changespec(name="child_feature", parent="parent_feature")

    with patch("work.revert.find_all_changespecs", return_value=[parent, child]):
        success, error = revert_changespec(parent)

    assert success is False
    assert error is not None
    assert "Cannot revert: other ChangeSpecs have this one as their parent" in error

    Path(parent.file_path).unlink()
    Path(child.file_path).unlink()


def test_revert_changespec_fails_without_workspace_dir() -> None:
    """Test revert_changespec fails when workspace directory cannot be determined."""
    changespec = _create_test_changespec()

    with patch("work.revert.find_all_changespecs", return_value=[changespec]):
        with patch.dict("os.environ", {}, clear=True):
            success, error = revert_changespec(changespec)

    assert success is False
    assert error is not None
    assert "Could not determine workspace directory" in error

    Path(changespec.file_path).unlink()


def test_revert_changespec_fails_with_nonexistent_workspace() -> None:
    """Test revert_changespec fails when workspace directory doesn't exist."""
    changespec = _create_test_changespec()

    with patch("work.revert.find_all_changespecs", return_value=[changespec]):
        with patch.dict(
            "os.environ",
            {"GOOG_CLOUD_DIR": "/nonexistent", "GOOG_SRC_DIR_BASE": "src"},
        ):
            success, error = revert_changespec(changespec)

    assert success is False
    assert error is not None
    assert "Workspace directory does not exist" in error

    Path(changespec.file_path).unlink()


def test_revert_changespec_success() -> None:
    """Test revert_changespec succeeds with all requirements met."""
    changespec = _create_test_changespec()
    console = MagicMock()

    with patch("work.revert.find_all_changespecs", return_value=[changespec]):
        with patch("work.revert._get_workspace_directory", return_value="/tmp"):
            with patch("work.revert._save_diff_to_file", return_value=(True, None)):
                with patch("work.revert._run_bb_hg_prune", return_value=(True, None)):
                    with patch(
                        "work.revert.update_changespec_name_atomic"
                    ) as mock_rename:
                        with patch(
                            "work.revert.transition_changespec_status",
                            return_value=(True, "Mailed", None),
                        ):
                            with patch("work.revert.reset_changespec_cl"):
                                success, error = revert_changespec(changespec, console)

    assert success is True
    assert error is None
    mock_rename.assert_called_once()

    Path(changespec.file_path).unlink()


def test_revert_changespec_fails_on_diff_error() -> None:
    """Test revert_changespec fails when diff cannot be saved."""
    changespec = _create_test_changespec()

    with patch("work.revert.find_all_changespecs", return_value=[changespec]):
        with patch("work.revert._get_workspace_directory", return_value="/tmp"):
            with patch(
                "work.revert._save_diff_to_file",
                return_value=(False, "hg diff failed"),
            ):
                success, error = revert_changespec(changespec)

    assert success is False
    assert error is not None
    assert "Failed to save diff" in error

    Path(changespec.file_path).unlink()


def test_revert_changespec_fails_on_prune_error() -> None:
    """Test revert_changespec fails when prune fails."""
    changespec = _create_test_changespec()

    with patch("work.revert.find_all_changespecs", return_value=[changespec]):
        with patch("work.revert._get_workspace_directory", return_value="/tmp"):
            with patch("work.revert._save_diff_to_file", return_value=(True, None)):
                with patch(
                    "work.revert._run_bb_hg_prune",
                    return_value=(False, "prune failed"),
                ):
                    success, error = revert_changespec(changespec)

    assert success is False
    assert error is not None
    assert "Failed to prune revision" in error

    Path(changespec.file_path).unlink()
