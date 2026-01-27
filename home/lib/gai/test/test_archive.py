"""Tests for gai.ace.archive module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from ace.archive import (
    _has_non_terminal_children,
    _has_valid_cl,
    archive_changespec,
)
from ace.changespec import ChangeSpec


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


def test_has_non_terminal_children_with_no_children() -> None:
    """Test has_non_terminal_children returns False when no children exist."""
    parent = _create_test_changespec(name="parent_feature")
    child = _create_test_changespec(name="unrelated_feature", parent=None)
    all_changespecs = [parent, child]

    assert _has_non_terminal_children(parent, all_changespecs) is False

    Path(parent.file_path).unlink()
    Path(child.file_path).unlink()


def test_has_non_terminal_children_with_wip_child() -> None:
    """Test has_non_terminal_children returns True when child is WIP."""
    parent = _create_test_changespec(name="parent_feature")
    child = _create_test_changespec(
        name="child_feature", parent="parent_feature", status="WIP"
    )
    all_changespecs = [parent, child]

    assert _has_non_terminal_children(parent, all_changespecs) is True

    Path(parent.file_path).unlink()
    Path(child.file_path).unlink()


def test_has_non_terminal_children_ignores_reverted_children() -> None:
    """Test has_non_terminal_children returns False when only child is Reverted."""
    parent = _create_test_changespec(name="parent_feature")
    reverted_child = _create_test_changespec(
        name="child_feature__1", parent="parent_feature", status="Reverted"
    )
    all_changespecs = [parent, reverted_child]

    assert _has_non_terminal_children(parent, all_changespecs) is False

    Path(parent.file_path).unlink()
    Path(reverted_child.file_path).unlink()


def test_has_non_terminal_children_ignores_archived_children() -> None:
    """Test has_non_terminal_children returns False when only child is Archived."""
    parent = _create_test_changespec(name="parent_feature")
    archived_child = _create_test_changespec(
        name="child_feature__1", parent="parent_feature", status="Archived"
    )
    all_changespecs = [parent, archived_child]

    assert _has_non_terminal_children(parent, all_changespecs) is False

    Path(parent.file_path).unlink()
    Path(archived_child.file_path).unlink()


def test_has_non_terminal_children_allows_mix_of_archived_and_reverted() -> None:
    """Test has_non_terminal_children returns False with mix of Archived/Reverted."""
    parent = _create_test_changespec(name="parent_feature")
    archived_child = _create_test_changespec(
        name="child_feature__1", parent="parent_feature", status="Archived"
    )
    reverted_child = _create_test_changespec(
        name="child_feature__2", parent="parent_feature", status="Reverted"
    )
    all_changespecs = [parent, archived_child, reverted_child]

    assert _has_non_terminal_children(parent, all_changespecs) is False

    Path(parent.file_path).unlink()
    Path(archived_child.file_path).unlink()
    Path(reverted_child.file_path).unlink()


def test_archive_changespec_fails_without_cl() -> None:
    """Test archive_changespec fails when CL is not set."""
    changespec = _create_test_changespec(cl=None)

    success, error = archive_changespec(changespec)

    assert success is False
    assert error == "ChangeSpec does not have a valid CL set"
    Path(changespec.file_path).unlink()


def test_archive_changespec_fails_with_non_terminal_children() -> None:
    """Test archive_changespec fails when ChangeSpec has non-terminal children."""
    parent = _create_test_changespec(name="parent_feature")
    child = _create_test_changespec(
        name="child_feature", parent="parent_feature", status="WIP"
    )

    with patch("ace.archive.find_all_changespecs", return_value=[parent, child]):
        with patch("ace.archive.get_first_available_axe_workspace", return_value=100):
            with patch(
                "ace.archive.get_workspace_directory_for_num",
                return_value=("/tmp", None),
            ):
                with patch("ace.archive.claim_workspace", return_value=True):
                    with patch(
                        "ace.archive._run_bb_hg_update", return_value=(True, None)
                    ):
                        with patch("ace.archive.release_workspace"):
                            success, error = archive_changespec(parent)

    assert success is False
    assert error is not None
    assert "Cannot archive" in error
    assert "not Archived or Reverted" in error

    Path(parent.file_path).unlink()
    Path(child.file_path).unlink()


def test_archive_changespec_succeeds_with_terminal_children() -> None:
    """Test archive_changespec succeeds when all children are Archived/Reverted."""
    parent = _create_test_changespec(name="parent_feature")
    archived_child = _create_test_changespec(
        name="child_feature__1", parent="parent_feature", status="Archived"
    )
    console = MagicMock()

    with patch(
        "ace.archive.find_all_changespecs", return_value=[parent, archived_child]
    ):
        with patch("ace.archive.get_first_available_axe_workspace", return_value=100):
            with patch(
                "ace.archive.get_workspace_directory_for_num",
                return_value=("/tmp", None),
            ):
                with patch("ace.archive.claim_workspace", return_value=True):
                    with patch(
                        "ace.archive._run_bb_hg_update", return_value=(True, None)
                    ):
                        with patch(
                            "ace.archive._save_diff_to_file", return_value=(True, None)
                        ):
                            with patch(
                                "ace.archive._run_bb_hg_archive",
                                return_value=(True, None),
                            ):
                                with patch("ace.archive.update_changespec_name_atomic"):
                                    with patch(
                                        "ace.archive.transition_changespec_status",
                                        return_value=(True, "Mailed", None, []),
                                    ):
                                        with patch("ace.archive.reset_changespec_cl"):
                                            with patch("ace.archive.release_workspace"):
                                                success, error = archive_changespec(
                                                    parent, console
                                                )

    assert success is True
    assert error is None

    Path(parent.file_path).unlink()
    Path(archived_child.file_path).unlink()


def test_archive_changespec_claims_workspace_100_plus() -> None:
    """Test archive_changespec claims workspace in >=100 range."""
    changespec = _create_test_changespec()
    console = MagicMock()

    with patch("ace.archive.find_all_changespecs", return_value=[changespec]):
        with patch(
            "ace.archive.get_first_available_axe_workspace", return_value=100
        ) as mock_get_ws:
            with patch(
                "ace.archive.get_workspace_directory_for_num",
                return_value=("/tmp", None),
            ):
                with patch(
                    "ace.archive.claim_workspace", return_value=True
                ) as mock_claim:
                    with patch(
                        "ace.archive._run_bb_hg_update", return_value=(True, None)
                    ):
                        with patch(
                            "ace.archive._save_diff_to_file", return_value=(True, None)
                        ):
                            with patch(
                                "ace.archive._run_bb_hg_archive",
                                return_value=(True, None),
                            ):
                                with patch("ace.archive.update_changespec_name_atomic"):
                                    with patch(
                                        "ace.archive.transition_changespec_status",
                                        return_value=(True, "Mailed", None, []),
                                    ):
                                        with patch("ace.archive.reset_changespec_cl"):
                                            with patch("ace.archive.release_workspace"):
                                                success, _error = archive_changespec(
                                                    changespec, console
                                                )

    assert success is True
    mock_get_ws.assert_called_once_with(changespec.file_path)
    # Verify claim_workspace was called with workspace_num >= 100
    mock_claim.assert_called_once()
    call_args = mock_claim.call_args
    assert call_args[0][1] == 100  # workspace_num argument

    Path(changespec.file_path).unlink()


def test_archive_changespec_fails_on_archive_error() -> None:
    """Test archive_changespec fails when bb_hg_archive fails."""
    changespec = _create_test_changespec()

    with patch("ace.archive.find_all_changespecs", return_value=[changespec]):
        with patch("ace.archive.get_first_available_axe_workspace", return_value=100):
            with patch(
                "ace.archive.get_workspace_directory_for_num",
                return_value=("/tmp", None),
            ):
                with patch("ace.archive.claim_workspace", return_value=True):
                    with patch(
                        "ace.archive._run_bb_hg_update", return_value=(True, None)
                    ):
                        with patch(
                            "ace.archive._save_diff_to_file", return_value=(True, None)
                        ):
                            with patch(
                                "ace.archive._run_bb_hg_archive",
                                return_value=(False, "archive failed"),
                            ):
                                with patch("ace.archive.release_workspace"):
                                    success, error = archive_changespec(changespec)

    assert success is False
    assert error is not None
    assert "Failed to archive revision" in error

    Path(changespec.file_path).unlink()


def test_archive_changespec_releases_workspace_on_failure() -> None:
    """Test archive_changespec releases workspace even on failure."""
    changespec = _create_test_changespec()

    with patch("ace.archive.find_all_changespecs", return_value=[changespec]):
        with patch("ace.archive.get_first_available_axe_workspace", return_value=100):
            with patch(
                "ace.archive.get_workspace_directory_for_num",
                return_value=("/tmp", None),
            ):
                with patch("ace.archive.claim_workspace", return_value=True):
                    with patch(
                        "ace.archive._run_bb_hg_update",
                        return_value=(False, "update failed"),
                    ):
                        with patch("ace.archive.release_workspace") as mock_release:
                            success, error = archive_changespec(changespec)

    assert success is False
    assert error is not None
    assert "Failed to checkout CL" in error
    mock_release.assert_called_once()

    Path(changespec.file_path).unlink()
