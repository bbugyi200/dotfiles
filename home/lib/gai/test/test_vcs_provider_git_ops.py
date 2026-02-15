"""Tests for the git VCS provider — commit and branch operations.

Covers: commit, amend, rename_branch, rebase, archive, prune, stash_and_clean.
"""

from unittest.mock import MagicMock, mock_open, patch

from vcs_provider._git import _GitProvider

# === Tests for commit ===


@patch("vcs_provider._git.subprocess.run")
def test_git_commit_new_branch(mock_run: MagicMock) -> None:
    """Test _GitProvider.commit creates new branch when needed."""
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="main\n", stderr=""),  # rev-parse
        MagicMock(returncode=0, stdout="", stderr=""),  # checkout -b
        MagicMock(returncode=0, stdout="", stderr=""),  # commit
    ]

    provider = _GitProvider()
    success, error = provider.commit("feature", "/tmp/msg.txt", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args_list[1][0][0] == ["git", "checkout", "-b", "feature"]
    assert mock_run.call_args_list[2][0][0] == ["git", "commit", "-F", "/tmp/msg.txt"]


@patch("vcs_provider._git.subprocess.run")
def test_git_commit_same_branch(mock_run: MagicMock) -> None:
    """Test _GitProvider.commit skips branch creation when already on branch."""
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="feature\n", stderr=""),  # rev-parse
        MagicMock(returncode=0, stdout="", stderr=""),  # commit
    ]

    provider = _GitProvider()
    success, error = provider.commit("feature", "/tmp/msg.txt", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_count == 2  # No checkout -b call


@patch("vcs_provider._git.subprocess.run")
def test_git_commit_branch_creation_fails(mock_run: MagicMock) -> None:
    """Test _GitProvider.commit when branch creation fails."""
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="main\n", stderr=""),  # rev-parse
        MagicMock(
            returncode=1, stdout="", stderr="branch already exists"
        ),  # checkout -b fails
    ]

    provider = _GitProvider()
    success, error = provider.commit("feature", "/tmp/msg.txt", "/workspace")

    assert success is False
    assert error is not None
    assert "git checkout -b failed" in error


@patch("vcs_provider._git.subprocess.run")
def test_git_commit_failure(mock_run: MagicMock) -> None:
    """Test _GitProvider.commit when commit itself fails."""
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="feature\n", stderr=""),  # rev-parse
        MagicMock(returncode=1, stdout="", stderr="nothing to commit"),  # commit fails
    ]

    provider = _GitProvider()
    success, error = provider.commit("feature", "/tmp/msg.txt", "/workspace")

    assert success is False
    assert error is not None
    assert "git commit failed" in error


# === Tests for amend ===


@patch("vcs_provider._git.subprocess.run")
def test_git_amend_success(mock_run: MagicMock) -> None:
    """Test _GitProvider.amend on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _GitProvider()
    success, error = provider.amend("fix typo", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == ["git", "commit", "--amend", "-m", "fix typo"]


@patch("vcs_provider._git.subprocess.run")
def test_git_amend_no_upload_ignored(mock_run: MagicMock) -> None:
    """Test _GitProvider.amend silently ignores no_upload flag."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _GitProvider()
    success, _ = provider.amend("fix typo", "/workspace", no_upload=True)

    assert success is True
    # Same command regardless of no_upload
    assert mock_run.call_args[0][0] == ["git", "commit", "--amend", "-m", "fix typo"]


@patch("vcs_provider._git.subprocess.run")
def test_git_amend_failure(mock_run: MagicMock) -> None:
    """Test _GitProvider.amend on failure."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="nothing to amend"
    )

    provider = _GitProvider()
    success, error = provider.amend("note", "/workspace")

    assert success is False
    assert error is not None
    assert "git commit --amend failed" in error


# === Tests for rename_branch ===


@patch("vcs_provider._git.subprocess.run")
def test_git_rename_branch_success(mock_run: MagicMock) -> None:
    """Test _GitProvider.rename_branch on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _GitProvider()
    success, error = provider.rename_branch("new_name", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == ["git", "branch", "-m", "new_name"]


@patch("vcs_provider._git.subprocess.run")
def test_git_rename_branch_failure(mock_run: MagicMock) -> None:
    """Test _GitProvider.rename_branch on failure."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="fatal: rename failed"
    )

    provider = _GitProvider()
    success, error = provider.rename_branch("bad", "/workspace")

    assert success is False
    assert error is not None
    assert "git branch -m failed" in error


# === Tests for rebase ===


@patch("vcs_provider._git.subprocess.run")
def test_git_rebase_success(mock_run: MagicMock) -> None:
    """Test _GitProvider.rebase on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _GitProvider()
    success, error = provider.rebase("feature", "main", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == ["git", "rebase", "--onto", "main", "feature"]
    # Verify 600s timeout
    assert mock_run.call_args[1]["timeout"] == 600


@patch("vcs_provider._git.subprocess.run")
def test_git_rebase_failure(mock_run: MagicMock) -> None:
    """Test _GitProvider.rebase on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="merge conflict")

    provider = _GitProvider()
    success, error = provider.rebase("feature", "main", "/workspace")

    assert success is False
    assert error is not None
    assert "git rebase failed" in error


# === Tests for archive ===


@patch("vcs_provider._git.subprocess.run")
def test_git_archive_success(mock_run: MagicMock) -> None:
    """Test _GitProvider.archive on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _GitProvider()
    success, error = provider.archive("old-feature", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_count == 2
    assert mock_run.call_args_list[0][0][0] == [
        "git",
        "tag",
        "archive/old-feature",
        "old-feature",
    ]
    assert mock_run.call_args_list[1][0][0] == ["git", "branch", "-D", "old-feature"]


@patch("vcs_provider._git.subprocess.run")
def test_git_archive_tag_fails(mock_run: MagicMock) -> None:
    """Test _GitProvider.archive when tagging fails."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="tag already exists"
    )

    provider = _GitProvider()
    success, error = provider.archive("old-feature", "/workspace")

    assert success is False
    assert error is not None
    assert "git tag failed" in error
    # Should not attempt branch delete
    mock_run.assert_called_once()


@patch("vcs_provider._git.subprocess.run")
def test_git_archive_branch_delete_fails(mock_run: MagicMock) -> None:
    """Test _GitProvider.archive when branch delete fails."""
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="", stderr=""),  # tag succeeds
        MagicMock(returncode=1, stdout="", stderr="branch not found"),  # delete fails
    ]

    provider = _GitProvider()
    success, error = provider.archive("old-feature", "/workspace")

    assert success is False
    assert error is not None
    assert "git branch -D failed" in error


# === Tests for prune ===


@patch("vcs_provider._git.subprocess.run")
def test_git_prune_success(mock_run: MagicMock) -> None:
    """Test _GitProvider.prune on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _GitProvider()
    success, error = provider.prune("dead-branch", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == ["git", "branch", "-D", "dead-branch"]


@patch("vcs_provider._git.subprocess.run")
def test_git_prune_failure(mock_run: MagicMock) -> None:
    """Test _GitProvider.prune on failure."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="error: branch not found"
    )

    provider = _GitProvider()
    success, error = provider.prune("nonexistent", "/workspace")

    assert success is False
    assert error is not None
    assert "git branch -D failed" in error


# === Tests for stash_and_clean ===


@patch("builtins.open", mock_open())
@patch("vcs_provider._git.subprocess.run")
def test_git_stash_and_clean_success(mock_run: MagicMock) -> None:
    """Test _GitProvider.stash_and_clean on success."""
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="diff content", stderr=""),  # diff
        MagicMock(returncode=0, stdout="", stderr=""),  # reset
        MagicMock(returncode=0, stdout="", stderr=""),  # clean
    ]

    provider = _GitProvider()
    success, error = provider.stash_and_clean("/tmp/backup.diff", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_count == 3


@patch("vcs_provider._git.subprocess.run")
def test_git_stash_and_clean_diff_fails(mock_run: MagicMock) -> None:
    """Test _GitProvider.stash_and_clean when diff fails."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="diff error")

    provider = _GitProvider()
    success, error = provider.stash_and_clean("/tmp/backup.diff", "/workspace")

    assert success is False
    assert error is not None
    assert "diff error" in error


@patch("builtins.open", side_effect=OSError("permission denied"))
@patch("vcs_provider._git.subprocess.run")
def test_git_stash_and_clean_write_fails(
    mock_run: MagicMock, mock_open_fn: MagicMock
) -> None:
    """Test _GitProvider.stash_and_clean when file write fails."""
    mock_run.return_value = MagicMock(returncode=0, stdout="diff content", stderr="")

    provider = _GitProvider()
    success, error = provider.stash_and_clean("/tmp/backup.diff", "/workspace")

    assert success is False
    assert error is not None
    assert "Failed to write diff file" in error


@patch("builtins.open", mock_open())
@patch("vcs_provider._git.subprocess.run")
def test_git_stash_and_clean_reset_fails(mock_run: MagicMock) -> None:
    """Test _GitProvider.stash_and_clean when reset step fails."""
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="diff content", stderr=""),  # diff
        MagicMock(returncode=1, stdout="", stderr="reset error"),  # reset
    ]

    provider = _GitProvider()
    success, error = provider.stash_and_clean("/tmp/backup.diff", "/workspace")

    assert success is False
    assert error is not None
    assert "git reset --hard failed" in error


@patch("builtins.open", mock_open())
@patch("vcs_provider._git.subprocess.run")
def test_git_stash_and_clean_clean_fails(mock_run: MagicMock) -> None:
    """Test _GitProvider.stash_and_clean when clean step fails."""
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="diff content", stderr=""),  # diff
        MagicMock(returncode=0, stdout="", stderr=""),  # reset ok
        MagicMock(returncode=1, stdout="", stderr="clean error"),  # clean fails
    ]

    provider = _GitProvider()
    success, error = provider.stash_and_clean("/tmp/backup.diff", "/workspace")

    assert success is False
    assert error is not None
    assert "git clean -fd failed" in error
