"""Tests for update_to_changespec operations."""

import tempfile
from unittest.mock import MagicMock, patch

from ace.changespec import ChangeSpec
from ace.operations import update_to_changespec


def _make_changespec(**kwargs: object) -> ChangeSpec:
    """Create a ChangeSpec with sensible defaults for testing."""
    defaults: dict[str, object] = {
        "name": "test_feature",
        "description": "Test",
        "parent": None,
        "cl": None,
        "status": "Drafted",
        "test_targets": None,
        "kickstart": None,
        "file_path": "/path/to/project.gp",
        "line_number": 1,
    }
    defaults.update(kwargs)
    return ChangeSpec(**defaults)  # type: ignore[arg-type]


def test_update_to_changespec_with_parent() -> None:
    """Test that update_to_changespec uses PARENT field when set."""
    changespec = _make_changespec(parent="parent_cl_123")

    mock_provider = MagicMock()
    mock_provider.checkout.return_value = (True, None)

    with patch("ace.operations.get_workspace_dir_from_project") as mock_get_ws:
        mock_get_ws.return_value = "/tmp/project/src"
        with patch("os.path.exists", return_value=True):
            with patch("os.path.isdir", return_value=True):
                with patch("vcs_provider.get_vcs_provider", return_value=mock_provider):
                    success, error = update_to_changespec(changespec)

    assert success is True
    assert error is None
    mock_provider.checkout.assert_called_once_with("parent_cl_123", "/tmp/project/src")


def test_update_to_changespec_without_parent() -> None:
    """Test that update_to_changespec uses provider default when PARENT is None."""
    changespec = _make_changespec(parent=None)

    mock_provider = MagicMock()
    mock_provider.checkout.return_value = (True, None)
    mock_provider.get_default_parent_revision.return_value = "p4head"

    with patch("ace.operations.get_workspace_dir_from_project") as mock_get_ws:
        mock_get_ws.return_value = "/tmp/project/src"
        with patch("os.path.exists", return_value=True):
            with patch("os.path.isdir", return_value=True):
                with patch("vcs_provider.get_vcs_provider", return_value=mock_provider):
                    success, error = update_to_changespec(changespec)

    assert success is True
    assert error is None
    # Verify get_default_parent_revision was called
    mock_provider.get_default_parent_revision.assert_called_once_with(
        "/tmp/project/src"
    )
    # Verify checkout was called with the resolved default
    mock_provider.checkout.assert_called_once_with("p4head", "/tmp/project/src")


def test_update_to_changespec_with_revision() -> None:
    """Test that update_to_changespec uses provided revision when specified."""
    changespec = _make_changespec(parent="parent_cl_123", cl="cl_456")

    mock_provider = MagicMock()
    mock_provider.checkout.return_value = (True, None)

    with patch("ace.operations.get_workspace_dir_from_project") as mock_get_ws:
        mock_get_ws.return_value = "/tmp/project/src"
        with patch("os.path.exists", return_value=True):
            with patch("os.path.isdir", return_value=True):
                with patch("vcs_provider.get_vcs_provider", return_value=mock_provider):
                    success, error = update_to_changespec(
                        changespec, revision="custom_revision"
                    )

    assert success is True
    assert error is None
    mock_provider.checkout.assert_called_once_with(
        "custom_revision", "/tmp/project/src"
    )


def test_update_to_changespec_with_workspace_dir() -> None:
    """Test that update_to_changespec uses provided workspace_dir."""
    changespec = _make_changespec(parent="parent_cl_123")

    mock_provider = MagicMock()
    mock_provider.checkout.return_value = (True, None)

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("vcs_provider.get_vcs_provider", return_value=mock_provider):
            success, error = update_to_changespec(changespec, workspace_dir=tmpdir)

    assert success is True
    assert error is None
    mock_provider.checkout.assert_called_once_with("parent_cl_123", tmpdir)
