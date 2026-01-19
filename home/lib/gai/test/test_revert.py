"""Tests for gai.work.revert module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from ace.changespec import ChangeSpec, MentorEntry, MentorStatusLine
from ace.revert import (
    _has_children,
    _has_valid_cl,
    revert_changespec,
)
from gai_utils import get_next_suffix_number
from running_field import _WorkspaceClaim


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
        f.write(f"""# Test Project

## ChangeSpec

NAME: {name}
DESCRIPTION:
  A test feature
PARENT: {parent_val}
CL: {cl_val}
STATUS: {status}

---
""")
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


def test__has_children_ignores_reverted_children() -> None:
    """Test _has_children returns False when only child is Reverted."""
    parent = _create_test_changespec(name="parent_feature")
    reverted_child = _create_test_changespec(
        name="child_feature__1", parent="parent_feature", status="Reverted"
    )
    all_changespecs = [parent, reverted_child]

    assert _has_children(parent, all_changespecs) is False

    Path(parent.file_path).unlink()
    Path(reverted_child.file_path).unlink()


def test_get_next_suffix_number_first_revert() -> None:
    """Test get_next_suffix_number returns 1 for first revert."""
    existing_names = {"test_feature"}

    suffix = get_next_suffix_number("test_feature", existing_names)

    assert suffix == 1


def test_get_next_suffix_number_second_revert() -> None:
    """Test get_next_suffix_number returns 2 when __1 already exists."""
    existing_names = {"test_feature", "test_feature__1"}

    suffix = get_next_suffix_number("test_feature", existing_names)

    assert suffix == 2


def test_get_next_suffix_number_fills_gap() -> None:
    """Test get_next_suffix_number finds lowest available number."""
    existing_names = {"test_feature", "test_feature__2", "test_feature__3"}

    suffix = get_next_suffix_number("test_feature", existing_names)

    assert suffix == 1


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

    with patch("ace.revert.find_all_changespecs", return_value=[parent, child]):
        success, error = revert_changespec(parent)

    assert success is False
    assert error is not None
    assert "Cannot revert: other ChangeSpecs have this one as their parent" in error

    Path(parent.file_path).unlink()
    Path(child.file_path).unlink()


def test_revert_changespec_fails_without_workspace_dir() -> None:
    """Test revert_changespec fails when workspace directory cannot be determined."""
    changespec = _create_test_changespec()

    with patch("ace.revert.find_all_changespecs", return_value=[changespec]):
        with patch.dict("os.environ", {}, clear=True):
            success, error = revert_changespec(changespec)

    assert success is False
    assert error is not None
    assert "Could not determine workspace directory" in error

    Path(changespec.file_path).unlink()


def test_revert_changespec_fails_with_nonexistent_workspace() -> None:
    """Test revert_changespec fails when workspace directory doesn't exist."""
    changespec = _create_test_changespec()

    with patch("ace.revert.find_all_changespecs", return_value=[changespec]):
        with patch("ace.revert.get_workspace_directory_for_changespec") as mock_get_ws:
            mock_get_ws.return_value = "/nonexistent/workspace"
            success, error = revert_changespec(changespec)

    assert success is False
    assert error is not None
    assert "Workspace directory does not exist" in error

    Path(changespec.file_path).unlink()


def test_revert_changespec_success() -> None:
    """Test revert_changespec succeeds with all requirements met."""
    changespec = _create_test_changespec()
    console = MagicMock()

    with patch("ace.revert.find_all_changespecs", return_value=[changespec]):
        with patch(
            "ace.revert.get_workspace_directory_for_changespec", return_value="/tmp"
        ):
            with patch("ace.revert._save_diff_to_file", return_value=(True, None)):
                with patch("ace.revert._run_bb_hg_prune", return_value=(True, None)):
                    with patch(
                        "ace.revert.update_changespec_name_atomic"
                    ) as mock_rename:
                        with patch(
                            "ace.revert.transition_changespec_status",
                            return_value=(True, "Mailed", None),
                        ):
                            with patch("ace.revert.reset_changespec_cl"):
                                success, error = revert_changespec(changespec, console)

    assert success is True
    assert error is None
    mock_rename.assert_called_once()

    Path(changespec.file_path).unlink()


def test_revert_changespec_fails_on_diff_error() -> None:
    """Test revert_changespec fails when diff cannot be saved."""
    changespec = _create_test_changespec()

    with patch("ace.revert.find_all_changespecs", return_value=[changespec]):
        with patch(
            "ace.revert.get_workspace_directory_for_changespec", return_value="/tmp"
        ):
            with patch(
                "ace.revert._save_diff_to_file",
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

    with patch("ace.revert.find_all_changespecs", return_value=[changespec]):
        with patch(
            "ace.revert.get_workspace_directory_for_changespec", return_value="/tmp"
        ):
            with patch("ace.revert._save_diff_to_file", return_value=(True, None)):
                with patch(
                    "ace.revert._run_bb_hg_prune",
                    return_value=(False, "prune failed"),
                ):
                    success, error = revert_changespec(changespec)

    assert success is False
    assert error is not None
    assert "Failed to prune revision" in error

    Path(changespec.file_path).unlink()


def test_revert_changespec_releases_mentor_workspace() -> None:
    """Test revert_changespec releases workspace claims for killed mentors."""
    changespec = _create_test_changespec()
    # Add a mentor with a running agent suffix
    changespec.mentors = [
        MentorEntry(
            entry_id="1",
            profiles=[],
            status_lines=[
                MentorStatusLine(
                    profile_name="code",
                    mentor_name="complete",
                    status="RUNNING",
                    suffix="mentor_complete-235059-260112_201552",
                    suffix_type="running_agent",
                )
            ],
        )
    ]

    with patch("ace.revert.find_all_changespecs", return_value=[changespec]):
        with patch(
            "ace.revert.get_workspace_directory_for_changespec", return_value="/tmp"
        ):
            with patch("ace.revert._save_diff_to_file", return_value=(True, None)):
                with patch("ace.revert._run_bb_hg_prune", return_value=(True, None)):
                    with patch("ace.revert.update_changespec_name_atomic"):
                        with patch(
                            "ace.revert.transition_changespec_status",
                            return_value=(True, "Mailed", None),
                        ):
                            with patch("ace.revert.reset_changespec_cl"):
                                with patch(
                                    "ace.revert.release_workspace"
                                ) as mock_release:
                                    with patch(
                                        "ace.revert.get_claimed_workspaces"
                                    ) as mock_claims:
                                        mock_claims.return_value = [
                                            _WorkspaceClaim(
                                                workspace_num=100,
                                                workflow="axe(mentor)-complete-260112_201552",
                                                cl_name="test_feature",
                                                pid=235059,
                                            )
                                        ]
                                        success, _error = revert_changespec(changespec)

    assert success is True
    mock_release.assert_called_once()

    Path(changespec.file_path).unlink()
