"""Tests for the Mercurial VCS provider — commit and branch operations.

Covers: commit, rename_branch (failure), rebase, archive, prune.
"""

from unittest.mock import MagicMock, patch

from vcs_provider._hg import _HgProvider

# === Tests for commit ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_commit_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.commit on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, error = provider.commit("feature", "/tmp/msg.txt", "/workspace")

    assert success is True
    assert error is None
    # commit uses _run_shell, so call_args[0][0] is a string
    cmd_str = mock_run.call_args[0][0]
    assert 'hg commit --name "feature" --logfile "/tmp/msg.txt"' == cmd_str


@patch("vcs_provider._hg.subprocess.run")
def test_hg_commit_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.commit on failure."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="nothing to commit"
    )

    provider = _HgProvider()
    success, error = provider.commit("feature", "/tmp/msg.txt", "/workspace")

    assert success is False
    assert error is not None
    assert "hg commit failed" in error


# === Tests for rename_branch (failure case) ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_rename_branch_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.rename_branch on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="rename failed")

    provider = _HgProvider()
    success, error = provider.rename_branch("bad_name", "/workspace")

    assert success is False
    assert error is not None
    assert "bb_hg_rename failed" in error


# === Tests for rebase ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_rebase_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.rebase on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, error = provider.rebase("feature", "main", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == ["bb_hg_rebase", "feature", "main"]
    # Verify 600s timeout
    assert mock_run.call_args[1]["timeout"] == 600


@patch("vcs_provider._hg.subprocess.run")
def test_hg_rebase_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.rebase on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="merge conflict")

    provider = _HgProvider()
    success, error = provider.rebase("feature", "main", "/workspace")

    assert success is False
    assert error is not None
    assert "bb_hg_rebase failed" in error


# === Tests for archive ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_archive_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.archive on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, error = provider.archive("old-feature", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == ["bb_hg_archive", "old-feature"]


@patch("vcs_provider._hg.subprocess.run")
def test_hg_archive_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.archive on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="archive error")

    provider = _HgProvider()
    success, error = provider.archive("old-feature", "/workspace")

    assert success is False
    assert error is not None
    assert "bb_hg_archive failed" in error


# === Tests for prune ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_prune_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.prune on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, error = provider.prune("dead-branch", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == ["bb_hg_prune", "dead-branch"]


@patch("vcs_provider._hg.subprocess.run")
def test_hg_prune_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.prune on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="prune error")

    provider = _HgProvider()
    success, error = provider.prune("nonexistent", "/workspace")

    assert success is False
    assert error is not None
    assert "bb_hg_prune failed" in error
