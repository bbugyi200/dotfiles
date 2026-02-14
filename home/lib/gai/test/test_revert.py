"""Tests for gai.work.revert module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from ace.revert import (
    has_children,
    revert_changespec,
)


def test_has_children_with_no_children(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test has_children returns False when no children exist."""
    parent = make_changespec.create_with_file(name="parent_feature")
    child = make_changespec.create_with_file(name="unrelated_feature", parent=None)
    all_changespecs = [parent, child]

    assert has_children(parent, all_changespecs) is False

    Path(parent.file_path).unlink()
    Path(child.file_path).unlink()


def test_has_children_with_children(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test has_children returns True when children exist."""
    parent = make_changespec.create_with_file(name="parent_feature")
    child = make_changespec.create_with_file(
        name="child_feature", parent="parent_feature"
    )
    all_changespecs = [parent, child]

    assert has_children(parent, all_changespecs) is True

    Path(parent.file_path).unlink()
    Path(child.file_path).unlink()


def test_has_children_ignores_reverted_children(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test has_children returns False when only child is Reverted."""
    parent = make_changespec.create_with_file(name="parent_feature")
    reverted_child = make_changespec.create_with_file(
        name="child_feature__1", parent="parent_feature", status="Reverted"
    )
    all_changespecs = [parent, reverted_child]

    assert has_children(parent, all_changespecs) is False

    Path(parent.file_path).unlink()
    Path(reverted_child.file_path).unlink()


def test_revert_changespec_fails_without_cl(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test revert_changespec fails when CL is not set."""
    changespec = make_changespec.create_with_file(cl=None)

    success, error = revert_changespec(changespec)

    assert success is False
    assert error == "ChangeSpec does not have a valid CL set"
    Path(changespec.file_path).unlink()


def test_revert_changespec_fails_with_children(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test revert_changespec fails when ChangeSpec has children."""
    parent = make_changespec.create_with_file(name="parent_feature")
    child = make_changespec.create_with_file(
        name="child_feature", parent="parent_feature"
    )

    with patch("ace.revert.find_all_changespecs", return_value=[parent, child]):
        success, error = revert_changespec(parent)

    assert success is False
    assert error is not None
    assert "Cannot revert: other ChangeSpecs have this one as their parent" in error

    Path(parent.file_path).unlink()
    Path(child.file_path).unlink()


def test_revert_changespec_fails_without_workspace_dir(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test revert_changespec fails when workspace directory cannot be determined."""
    changespec = make_changespec.create_with_file()

    with patch("ace.revert.find_all_changespecs", return_value=[changespec]):
        with patch.dict("os.environ", {}, clear=True):
            success, error = revert_changespec(changespec)

    assert success is False
    assert error is not None
    assert "Could not determine workspace directory" in error

    Path(changespec.file_path).unlink()


def test_revert_changespec_fails_with_nonexistent_workspace(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test revert_changespec fails when workspace directory doesn't exist."""
    changespec = make_changespec.create_with_file()

    with patch("ace.revert.find_all_changespecs", return_value=[changespec]):
        with patch("ace.revert.get_workspace_directory_for_changespec") as mock_get_ws:
            mock_get_ws.return_value = "/nonexistent/workspace"
            success, error = revert_changespec(changespec)

    assert success is False
    assert error is not None
    assert "Workspace directory does not exist" in error

    Path(changespec.file_path).unlink()


def test_revert_changespec_success(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test revert_changespec succeeds with all requirements met."""
    changespec = make_changespec.create_with_file()
    console = MagicMock()

    mock_provider = MagicMock()
    mock_provider.prune.return_value = (True, None)

    with patch("ace.revert.find_all_changespecs", return_value=[changespec]):
        with patch(
            "ace.revert.get_workspace_directory_for_changespec", return_value="/tmp"
        ):
            with patch("ace.revert.save_diff_to_file", return_value=(True, None)):
                with patch("ace.revert.get_vcs_provider", return_value=mock_provider):
                    with patch(
                        "ace.revert.update_changespec_name_atomic"
                    ) as mock_rename:
                        with patch(
                            "ace.revert.transition_changespec_status",
                            return_value=(True, "Mailed", None, []),
                        ):
                            with patch("ace.revert.reset_changespec_cl"):
                                success, error = revert_changespec(changespec, console)

    assert success is True
    assert error is None
    mock_rename.assert_called_once()

    Path(changespec.file_path).unlink()


def test_revert_changespec_fails_on_diff_error(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test revert_changespec fails when diff cannot be saved."""
    changespec = make_changespec.create_with_file()

    with patch("ace.revert.find_all_changespecs", return_value=[changespec]):
        with patch(
            "ace.revert.get_workspace_directory_for_changespec", return_value="/tmp"
        ):
            with patch(
                "ace.revert.save_diff_to_file",
                return_value=(False, "hg diff failed"),
            ):
                success, error = revert_changespec(changespec)

    assert success is False
    assert error is not None
    assert "Failed to save diff" in error

    Path(changespec.file_path).unlink()


def test_revert_changespec_fails_on_prune_error(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test revert_changespec fails when prune fails."""
    changespec = make_changespec.create_with_file()

    mock_provider = MagicMock()
    mock_provider.prune.return_value = (False, "prune failed")

    with patch("ace.revert.find_all_changespecs", return_value=[changespec]):
        with patch(
            "ace.revert.get_workspace_directory_for_changespec", return_value="/tmp"
        ):
            with patch("ace.revert.save_diff_to_file", return_value=(True, None)):
                with patch("ace.revert.get_vcs_provider", return_value=mock_provider):
                    success, error = revert_changespec(changespec)

    assert success is False
    assert error is not None
    assert "Failed to prune revision" in error

    Path(changespec.file_path).unlink()


def test_revert_changespec_calls_kill_and_persist(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test revert_changespec calls kill_and_persist_all_running_processes."""
    changespec = make_changespec.create_with_file()

    mock_provider = MagicMock()
    mock_provider.prune.return_value = (True, None)

    with patch("ace.revert.find_all_changespecs", return_value=[changespec]):
        with patch(
            "ace.revert.get_workspace_directory_for_changespec", return_value="/tmp"
        ):
            with patch("ace.revert.save_diff_to_file", return_value=(True, None)):
                with patch("ace.revert.get_vcs_provider", return_value=mock_provider):
                    with patch("ace.revert.update_changespec_name_atomic"):
                        with patch(
                            "ace.revert.transition_changespec_status",
                            return_value=(True, "Mailed", None, []),
                        ):
                            with patch("ace.revert.reset_changespec_cl"):
                                with patch(
                                    "ace.revert.kill_and_persist_all_running_processes"
                                ) as mock_kill:
                                    success, _error = revert_changespec(changespec)

    assert success is True
    mock_kill.assert_called_once()
    call_args = mock_kill.call_args
    assert call_args[0][0] is changespec  # changespec
    assert call_args[0][1] == changespec.file_path  # project_file
    assert call_args[0][2] == changespec.name  # cl_name
    assert "reverted" in call_args[0][3].lower()  # kill_reason

    Path(changespec.file_path).unlink()
