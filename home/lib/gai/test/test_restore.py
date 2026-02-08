"""Tests for the restore module."""

from unittest.mock import MagicMock, patch

from ace.restore import (
    list_reverted_changespecs,
    restore_changespec,
)


def test_list_reverted_changespecs(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test list_reverted_changespecs filters by Reverted status."""
    reverted_cs = make_changespec.create(
        name="test_project_feature__1", status="Reverted"
    )
    mailed_cs = make_changespec.create(name="other__1", status="Mailed")
    submitted_cs = make_changespec.create(name="submitted__1", status="Submitted")

    with patch(
        "ace.restore.find_all_changespecs",
        return_value=[reverted_cs, mailed_cs, submitted_cs],
    ):
        result = list_reverted_changespecs()

    assert len(result) == 1
    assert result[0].name == "test_project_feature__1"
    assert result[0].status == "Reverted"


def test_list_reverted_changespecs_empty() -> None:
    """Test list_reverted_changespecs returns empty list when no reverted."""
    with patch("ace.restore.find_all_changespecs", return_value=[]):
        result = list_reverted_changespecs()
    assert result == []


def test_restore_changespec_wrong_status(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test restore_changespec fails if status is not Reverted."""
    changespec = make_changespec.create(name="test_project_feature__1", status="Mailed")

    success, error = restore_changespec(changespec)

    assert success is False
    assert error is not None
    assert "not 'Reverted'" in error


def test_restore_changespec_no_workspace_dir(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test restore_changespec fails if workspace directory not determined."""
    changespec = make_changespec.create(
        name="test_project_feature__1", status="Reverted"
    )

    with patch("ace.restore.get_workspace_directory_for_changespec", return_value=None):
        success, error = restore_changespec(changespec)

    assert success is False
    assert error is not None
    assert "Could not determine workspace directory" in error


def test_restore_changespec_workspace_not_exists(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test restore_changespec fails if workspace directory doesn't exist."""
    changespec = make_changespec.create(
        name="test_project_feature__1", status="Reverted"
    )

    with patch(
        "ace.restore.get_workspace_directory_for_changespec",
        return_value="/nonexistent/path",
    ):
        success, error = restore_changespec(changespec)

    assert success is False
    assert error is not None
    assert "does not exist" in error


def test_restore_changespec_success(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test restore_changespec succeeds with all requirements met."""
    changespec = make_changespec.create(
        name="test_project_feature__1", status="Reverted"
    )
    console = MagicMock()

    with patch(
        "ace.restore.get_workspace_directory_for_changespec", return_value="/tmp"
    ):
        with patch("os.path.isdir", return_value=True):
            with patch("ace.restore.update_changespec_name_atomic") as mock_rename:
                with patch(
                    "ace.restore.run_workspace_command", return_value=(True, None)
                ):
                    with patch("pathlib.Path.exists", return_value=True):
                        success, error = restore_changespec(changespec, console)

    assert success is True
    assert error is None
    mock_rename.assert_called_once_with(
        changespec.file_path, "test_project_feature__1", "test_project_feature"
    )


def test_restore_changespec_with_parent(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test restore_changespec uses parent for bb_hg_update."""
    changespec = make_changespec.create(
        name="test_project_feature__1", status="Reverted", parent="parent_branch"
    )

    with patch(
        "ace.restore.get_workspace_directory_for_changespec", return_value="/tmp"
    ):
        with patch("os.path.isdir", return_value=True):
            with patch("ace.restore.update_changespec_name_atomic"):
                with patch(
                    "ace.restore.run_workspace_command", return_value=(True, None)
                ) as mock_update:
                    with patch("pathlib.Path.exists", return_value=True):
                        restore_changespec(changespec)

    # First call should be bb_hg_update with parent
    mock_update.assert_any_call(["bb_hg_update", "parent_branch"], "/tmp")


def test_restore_changespec_without_parent_uses_p4head(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test restore_changespec uses p4head when no parent."""
    changespec = make_changespec.create(
        name="test_project_feature__1", status="Reverted", parent=None
    )

    with patch(
        "ace.restore.get_workspace_directory_for_changespec", return_value="/tmp"
    ):
        with patch("os.path.isdir", return_value=True):
            with patch("ace.restore.update_changespec_name_atomic"):
                with patch(
                    "ace.restore.run_workspace_command", return_value=(True, None)
                ) as mock_update:
                    with patch("pathlib.Path.exists", return_value=True):
                        restore_changespec(changespec)

    # First call should be bb_hg_update with p4head
    mock_update.assert_any_call(["bb_hg_update", "p4head"], "/tmp")


def test_restore_changespec_bb_hg_update_fails(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test restore_changespec fails when bb_hg_update fails."""
    changespec = make_changespec.create(
        name="test_project_feature__1", status="Reverted"
    )

    with patch(
        "ace.restore.get_workspace_directory_for_changespec", return_value="/tmp"
    ):
        with patch("os.path.isdir", return_value=True):
            with patch("ace.restore.update_changespec_name_atomic"):
                with patch(
                    "ace.restore.run_workspace_command",
                    return_value=(False, "update failed"),
                ):
                    success, error = restore_changespec(changespec)

    assert success is False
    assert error == "update failed"


def test_restore_changespec_diff_not_found(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test restore_changespec fails when diff file not found."""
    changespec = make_changespec.create(
        name="test_project_feature__1", status="Reverted"
    )

    with patch(
        "ace.restore.get_workspace_directory_for_changespec", return_value="/tmp"
    ):
        with patch("os.path.isdir", return_value=True):
            with patch("ace.restore.update_changespec_name_atomic"):
                with patch(
                    "ace.restore.run_workspace_command", return_value=(True, None)
                ):
                    with patch("pathlib.Path.exists", return_value=False):
                        success, error = restore_changespec(changespec)

    assert success is False
    assert error is not None
    assert "Diff file not found" in error


def test_restore_changespec_hg_import_fails(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test restore_changespec fails when hg import fails."""
    changespec = make_changespec.create(
        name="test_project_feature__1", status="Reverted"
    )

    with patch(
        "ace.restore.get_workspace_directory_for_changespec", return_value="/tmp"
    ):
        with patch("os.path.isdir", return_value=True):
            with patch("ace.restore.update_changespec_name_atomic"):
                with patch(
                    "ace.restore.run_workspace_command",
                    side_effect=[(True, None), (False, "hg failed: import failed")],
                ):
                    with patch("pathlib.Path.exists", return_value=True):
                        success, error = restore_changespec(changespec)

    assert success is False
    assert error is not None
    assert "import failed" in error


def test_restore_changespec_gai_commit_fails(make_changespec) -> None:  # type: ignore[no-untyped-def]
    """Test restore_changespec fails when gai commit fails."""
    changespec = make_changespec.create(
        name="test_project_feature__1", status="Reverted"
    )

    with patch(
        "ace.restore.get_workspace_directory_for_changespec", return_value="/tmp"
    ):
        with patch("os.path.isdir", return_value=True):
            with patch("ace.restore.update_changespec_name_atomic"):
                with patch(
                    "ace.restore.run_workspace_command",
                    side_effect=[
                        (True, None),
                        (True, None),
                        (False, "gai failed: commit failed"),
                    ],
                ):
                    with patch("pathlib.Path.exists", return_value=True):
                        success, error = restore_changespec(changespec)

    assert success is False
    assert error is not None
    assert "commit failed" in error
