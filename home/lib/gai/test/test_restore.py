"""Tests for the restore module."""

from unittest.mock import MagicMock, patch

from gai_utils import (
    get_workspace_directory_for_changespec,
    strip_reverted_suffix,
)
from search.changespec import ChangeSpec
from search.restore import (
    list_reverted_changespecs,
    restore_changespec,
)


def _create_test_changespec(
    name: str = "test_project_feature__1",
    status: str = "Reverted",
    parent: str | None = None,
    description: str = "Test description",
) -> ChangeSpec:
    """Create a test ChangeSpec."""
    return ChangeSpec(
        name=name,
        description=description,
        parent=parent,
        cl=None,
        status=status,
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test_project.gp",
        line_number=1,
    )


def test_strip_reverted_suffix_with_suffix() -> None:
    """Test strip_reverted_suffix removes __<N> suffix."""
    assert strip_reverted_suffix("foobar_feature__1") == "foobar_feature"
    assert strip_reverted_suffix("test_project_cl__2") == "test_project_cl"
    assert strip_reverted_suffix("name__10") == "name"
    assert strip_reverted_suffix("a__123") == "a"


def test_strip_reverted_suffix_without_suffix() -> None:
    """Test strip_reverted_suffix returns original name when no suffix."""
    assert strip_reverted_suffix("foobar_feature") == "foobar_feature"
    assert strip_reverted_suffix("test") == "test"
    assert strip_reverted_suffix("name_with_underscore") == "name_with_underscore"


def test_strip_reverted_suffix_invalid_suffix() -> None:
    """Test strip_reverted_suffix with invalid suffix patterns."""
    # Single underscore doesn't match the pattern
    assert strip_reverted_suffix("name_1") == "name_1"
    # Non-numeric suffix
    assert strip_reverted_suffix("name__abc") == "name__abc"
    # Empty after suffix
    assert strip_reverted_suffix("__1") == "__1"


def test_list_reverted_changespecs() -> None:
    """Test list_reverted_changespecs filters by Reverted status."""
    reverted_cs = _create_test_changespec(status="Reverted")
    mailed_cs = _create_test_changespec(name="other__1", status="Mailed")
    submitted_cs = _create_test_changespec(name="submitted__1", status="Submitted")

    with patch(
        "search.restore.find_all_changespecs",
        return_value=[reverted_cs, mailed_cs, submitted_cs],
    ):
        result = list_reverted_changespecs()

    assert len(result) == 1
    assert result[0].name == "test_project_feature__1"
    assert result[0].status == "Reverted"


def test_list_reverted_changespecs_empty() -> None:
    """Test list_reverted_changespecs returns empty list when no reverted."""
    with patch("search.restore.find_all_changespecs", return_value=[]):
        result = list_reverted_changespecs()
    assert result == []


def test_get_workspace_directory_success() -> None:
    """Test get_workspace_directory_for_changespec constructs correct path."""
    changespec = _create_test_changespec()

    with patch("running_field.get_workspace_directory") as mock_get_ws:
        mock_get_ws.return_value = "/cloud/test_project/src"
        result = get_workspace_directory_for_changespec(changespec)

    assert result == "/cloud/test_project/src"
    mock_get_ws.assert_called_once_with("test_project")


def test_get_workspace_directory_failure() -> None:
    """Test get_workspace_directory_for_changespec returns None when bb_get_workspace fails."""
    changespec = _create_test_changespec()

    with patch("running_field.get_workspace_directory") as mock_get_ws:
        mock_get_ws.side_effect = RuntimeError("bb_get_workspace failed")
        result = get_workspace_directory_for_changespec(changespec)

    assert result is None


def test_restore_changespec_wrong_status() -> None:
    """Test restore_changespec fails if status is not Reverted."""
    changespec = _create_test_changespec(status="Mailed")

    success, error = restore_changespec(changespec)

    assert success is False
    assert error is not None
    assert "not 'Reverted'" in error


def test_restore_changespec_no_workspace_dir() -> None:
    """Test restore_changespec fails if workspace directory not determined."""
    changespec = _create_test_changespec()

    with patch(
        "search.restore.get_workspace_directory_for_changespec", return_value=None
    ):
        success, error = restore_changespec(changespec)

    assert success is False
    assert error is not None
    assert "Could not determine workspace directory" in error


def test_restore_changespec_workspace_not_exists() -> None:
    """Test restore_changespec fails if workspace directory doesn't exist."""
    changespec = _create_test_changespec()

    with patch(
        "search.restore.get_workspace_directory_for_changespec",
        return_value="/nonexistent/path",
    ):
        success, error = restore_changespec(changespec)

    assert success is False
    assert error is not None
    assert "does not exist" in error


def test_restore_changespec_success() -> None:
    """Test restore_changespec succeeds with all requirements met."""
    changespec = _create_test_changespec()
    console = MagicMock()

    with patch(
        "search.restore.get_workspace_directory_for_changespec", return_value="/tmp"
    ):
        with patch("os.path.isdir", return_value=True):
            with patch("search.restore.update_changespec_name_atomic") as mock_rename:
                with patch(
                    "search.restore._run_bb_hg_update", return_value=(True, None)
                ):
                    with patch("pathlib.Path.exists", return_value=True):
                        with patch(
                            "search.restore._run_hg_import", return_value=(True, None)
                        ):
                            with patch(
                                "search.restore._run_gai_commit",
                                return_value=(True, None),
                            ):
                                success, error = restore_changespec(changespec, console)

    assert success is True
    assert error is None
    mock_rename.assert_called_once_with(
        changespec.file_path, "test_project_feature__1", "test_project_feature"
    )


def test_restore_changespec_with_parent() -> None:
    """Test restore_changespec uses parent for bb_hg_update."""
    changespec = _create_test_changespec(parent="parent_branch")

    with patch(
        "search.restore.get_workspace_directory_for_changespec", return_value="/tmp"
    ):
        with patch("os.path.isdir", return_value=True):
            with patch("search.restore.update_changespec_name_atomic"):
                with patch(
                    "search.restore._run_bb_hg_update", return_value=(True, None)
                ) as mock_update:
                    with patch("pathlib.Path.exists", return_value=True):
                        with patch(
                            "search.restore._run_hg_import", return_value=(True, None)
                        ):
                            with patch(
                                "search.restore._run_gai_commit",
                                return_value=(True, None),
                            ):
                                restore_changespec(changespec)

    mock_update.assert_called_once_with("parent_branch", "/tmp")


def test_restore_changespec_without_parent_uses_p4head() -> None:
    """Test restore_changespec uses p4head when no parent."""
    changespec = _create_test_changespec(parent=None)

    with patch(
        "search.restore.get_workspace_directory_for_changespec", return_value="/tmp"
    ):
        with patch("os.path.isdir", return_value=True):
            with patch("search.restore.update_changespec_name_atomic"):
                with patch(
                    "search.restore._run_bb_hg_update", return_value=(True, None)
                ) as mock_update:
                    with patch("pathlib.Path.exists", return_value=True):
                        with patch(
                            "search.restore._run_hg_import", return_value=(True, None)
                        ):
                            with patch(
                                "search.restore._run_gai_commit",
                                return_value=(True, None),
                            ):
                                restore_changespec(changespec)

    mock_update.assert_called_once_with("p4head", "/tmp")


def test_restore_changespec_bb_hg_update_fails() -> None:
    """Test restore_changespec fails when bb_hg_update fails."""
    changespec = _create_test_changespec()

    with patch(
        "search.restore.get_workspace_directory_for_changespec", return_value="/tmp"
    ):
        with patch("os.path.isdir", return_value=True):
            with patch("search.restore.update_changespec_name_atomic"):
                with patch(
                    "search.restore._run_bb_hg_update",
                    return_value=(False, "update failed"),
                ):
                    success, error = restore_changespec(changespec)

    assert success is False
    assert error == "update failed"


def test_restore_changespec_diff_not_found() -> None:
    """Test restore_changespec fails when diff file not found."""
    changespec = _create_test_changespec()

    with patch(
        "search.restore.get_workspace_directory_for_changespec", return_value="/tmp"
    ):
        with patch("os.path.isdir", return_value=True):
            with patch("search.restore.update_changespec_name_atomic"):
                with patch(
                    "search.restore._run_bb_hg_update", return_value=(True, None)
                ):
                    with patch("pathlib.Path.exists", return_value=False):
                        success, error = restore_changespec(changespec)

    assert success is False
    assert error is not None
    assert "Diff file not found" in error


def test_restore_changespec_hg_import_fails() -> None:
    """Test restore_changespec fails when hg import fails."""
    changespec = _create_test_changespec()

    with patch(
        "search.restore.get_workspace_directory_for_changespec", return_value="/tmp"
    ):
        with patch("os.path.isdir", return_value=True):
            with patch("search.restore.update_changespec_name_atomic"):
                with patch(
                    "search.restore._run_bb_hg_update", return_value=(True, None)
                ):
                    with patch("pathlib.Path.exists", return_value=True):
                        with patch(
                            "search.restore._run_hg_import",
                            return_value=(False, "import failed"),
                        ):
                            success, error = restore_changespec(changespec)

    assert success is False
    assert error == "import failed"


def test_restore_changespec_gai_commit_fails() -> None:
    """Test restore_changespec fails when gai commit fails."""
    changespec = _create_test_changespec()

    with patch(
        "search.restore.get_workspace_directory_for_changespec", return_value="/tmp"
    ):
        with patch("os.path.isdir", return_value=True):
            with patch("search.restore.update_changespec_name_atomic"):
                with patch(
                    "search.restore._run_bb_hg_update", return_value=(True, None)
                ):
                    with patch("pathlib.Path.exists", return_value=True):
                        with patch(
                            "search.restore._run_hg_import", return_value=(True, None)
                        ):
                            with patch(
                                "search.restore._run_gai_commit",
                                return_value=(False, "commit failed"),
                            ):
                                success, error = restore_changespec(changespec)

    assert success is False
    assert error == "commit failed"
