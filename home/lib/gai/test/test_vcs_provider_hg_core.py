"""Tests for the Mercurial VCS provider — core operations.

Covers: diff_revision, apply_patch, apply_patches, add_remove, clean_workspace.
"""

from unittest.mock import MagicMock, patch

from vcs_provider._hg import _HgProvider

# === Tests for diff_revision ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_diff_revision_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.diff_revision on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="diff output", stderr="")

    provider = _HgProvider()
    success, diff_text = provider.diff_revision("abc123", "/workspace")

    assert success is True
    assert diff_text == "diff output"
    assert mock_run.call_args[0][0] == ["hg", "diff", "-c", "abc123"]


@patch("vcs_provider._hg.subprocess.run")
def test_hg_diff_revision_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.diff_revision on failure."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="unknown revision"
    )

    provider = _HgProvider()
    success, error = provider.diff_revision("bad_rev", "/workspace")

    assert success is False
    assert error is not None
    assert "hg diff failed" in error


# === Tests for apply_patch ===


@patch("vcs_provider._hg.subprocess.run")
@patch("os.path.exists", return_value=True)
def test_hg_apply_patch_success(mock_exists: MagicMock, mock_run: MagicMock) -> None:
    """Test _HgProvider.apply_patch on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, error = provider.apply_patch("/tmp/fix.patch", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == ["hg", "import", "--no-commit", "/tmp/fix.patch"]


@patch("os.path.exists", return_value=False)
def test_hg_apply_patch_file_not_found(mock_exists: MagicMock) -> None:
    """Test _HgProvider.apply_patch when file doesn't exist."""
    provider = _HgProvider()
    success, error = provider.apply_patch("/tmp/missing.patch", "/workspace")

    assert success is False
    assert error is not None
    assert "Diff file not found" in error


@patch("vcs_provider._hg.subprocess.run")
@patch("os.path.exists", return_value=True)
def test_hg_apply_patch_failure(mock_exists: MagicMock, mock_run: MagicMock) -> None:
    """Test _HgProvider.apply_patch when hg import fails."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="patch does not apply"
    )

    provider = _HgProvider()
    success, error = provider.apply_patch("/tmp/bad.patch", "/workspace")

    assert success is False
    assert error is not None
    assert "patch does not apply" in error


# === Tests for apply_patches ===


def test_hg_apply_patches_empty_list() -> None:
    """Test _HgProvider.apply_patches with empty list."""
    provider = _HgProvider()
    success, error = provider.apply_patches([], "/workspace")

    assert success is True
    assert error is None


@patch("vcs_provider._hg.subprocess.run")
@patch("os.path.exists", return_value=True)
def test_hg_apply_patches_success(mock_exists: MagicMock, mock_run: MagicMock) -> None:
    """Test _HgProvider.apply_patches on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, error = provider.apply_patches(
        ["/tmp/a.patch", "/tmp/b.patch"], "/workspace"
    )

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == [
        "hg",
        "import",
        "--no-commit",
        "/tmp/a.patch",
        "/tmp/b.patch",
    ]


@patch("os.path.exists", side_effect=[True, False])
def test_hg_apply_patches_missing_file(mock_exists: MagicMock) -> None:
    """Test _HgProvider.apply_patches when a file is missing."""
    provider = _HgProvider()
    success, error = provider.apply_patches(
        ["/tmp/a.patch", "/tmp/missing.patch"], "/workspace"
    )

    assert success is False
    assert error is not None
    assert "Diff file not found" in error


@patch("vcs_provider._hg.subprocess.run")
@patch("os.path.exists", return_value=True)
def test_hg_apply_patches_failure(mock_exists: MagicMock, mock_run: MagicMock) -> None:
    """Test _HgProvider.apply_patches when hg import fails."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="conflict")

    provider = _HgProvider()
    success, error = provider.apply_patches(["/tmp/a.patch"], "/workspace")

    assert success is False
    assert error is not None
    assert "conflict" in error


# === Tests for add_remove ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_add_remove_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.add_remove on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, error = provider.add_remove("/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == ["hg", "addremove"]


@patch("vcs_provider._hg.subprocess.run")
def test_hg_add_remove_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.add_remove on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not a hg repo")

    provider = _HgProvider()
    success, error = provider.add_remove("/workspace")

    assert success is False
    assert error is not None
    assert "hg addremove failed" in error


# === Tests for clean_workspace ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_clean_workspace_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.clean_workspace on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, error = provider.clean_workspace("/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_count == 2
    assert mock_run.call_args_list[0][0][0] == ["hg", "update", "--clean", "."]
    assert mock_run.call_args_list[1][0][0] == ["hg", "clean"]


@patch("vcs_provider._hg.subprocess.run")
def test_hg_clean_workspace_revert_fails(mock_run: MagicMock) -> None:
    """Test _HgProvider.clean_workspace when revert step fails."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="revert error")

    provider = _HgProvider()
    success, error = provider.clean_workspace("/workspace")

    assert success is False
    assert error is not None
    assert "hg update --clean failed" in error


@patch("vcs_provider._hg.subprocess.run")
def test_hg_clean_workspace_clean_fails(mock_run: MagicMock) -> None:
    """Test _HgProvider.clean_workspace when clean step fails."""
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="", stderr=""),  # update --clean succeeds
        MagicMock(returncode=1, stdout="", stderr="clean error"),  # hg clean fails
    ]

    provider = _HgProvider()
    success, error = provider.clean_workspace("/workspace")

    assert success is False
    assert error is not None
    assert "hg clean failed" in error
