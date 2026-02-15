"""Tests for the git VCS provider — core operations.

Covers: registry detection, private helpers, checkout, diff, diff_revision,
apply_patch, apply_patches, add_remove, clean_workspace.
"""

import os
import subprocess
import tempfile
from unittest.mock import MagicMock, patch

from vcs_provider import get_vcs_provider
from vcs_provider._git import _GitProvider

# === Tests for registry detection ===


def test_get_vcs_provider_detects_git() -> None:
    """Test get_vcs_provider detects .git directory and returns _GitProvider."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, ".git"))
        provider = get_vcs_provider(tmpdir)
        assert isinstance(provider, _GitProvider)


# === Tests for private helpers ===


@patch("vcs_provider._git.subprocess.run")
def test_git_run_timeout(mock_run: MagicMock) -> None:
    """Test _GitProvider._run handles timeout."""
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=300)

    provider = _GitProvider()
    success, error = provider.checkout("main", "/workspace")

    assert success is False
    assert error is not None
    assert "timed out" in error


@patch("vcs_provider._git.subprocess.run")
def test_git_run_command_not_found(mock_run: MagicMock) -> None:
    """Test _GitProvider._run handles command not found."""
    mock_run.side_effect = FileNotFoundError()

    provider = _GitProvider()
    success, error = provider.checkout("main", "/workspace")

    assert success is False
    assert error is not None
    assert "not found" in error


@patch("vcs_provider._git.subprocess.run")
def test_git_run_generic_exception(mock_run: MagicMock) -> None:
    """Test _GitProvider._run handles generic exceptions."""
    mock_run.side_effect = OSError("permission denied")

    provider = _GitProvider()
    success, error = provider.checkout("main", "/workspace")

    assert success is False
    assert error is not None
    assert "Error running" in error


# === Tests for checkout ===


@patch("vcs_provider._git.subprocess.run")
def test_git_checkout_success(mock_run: MagicMock) -> None:
    """Test _GitProvider.checkout on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _GitProvider()
    success, error = provider.checkout("main", "/workspace")

    assert success is True
    assert error is None
    mock_run.assert_called_once()
    assert mock_run.call_args[0][0] == ["git", "checkout", "main"]


@patch("vcs_provider._git.subprocess.run")
def test_git_checkout_failure(mock_run: MagicMock) -> None:
    """Test _GitProvider.checkout on failure."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="error: pathspec 'bad' did not match"
    )

    provider = _GitProvider()
    success, error = provider.checkout("bad", "/workspace")

    assert success is False
    assert error is not None
    assert "git checkout failed" in error


# === Tests for diff ===


@patch("vcs_provider._git.subprocess.run")
def test_git_diff_with_changes(mock_run: MagicMock) -> None:
    """Test _GitProvider.diff returns diff text when changes exist."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="diff --git a/file.py b/file.py\n+new line",
        stderr="",
    )

    provider = _GitProvider()
    success, diff_text = provider.diff("/workspace")

    assert success is True
    assert diff_text is not None
    assert "new line" in diff_text
    assert mock_run.call_args[0][0] == ["git", "diff", "HEAD"]


@patch("vcs_provider._git.subprocess.run")
def test_git_diff_no_changes(mock_run: MagicMock) -> None:
    """Test _GitProvider.diff returns None when no changes."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _GitProvider()
    success, diff_text = provider.diff("/workspace")

    assert success is True
    assert diff_text is None


@patch("vcs_provider._git.subprocess.run")
def test_git_diff_fallback_empty_repo(mock_run: MagicMock) -> None:
    """Test _GitProvider.diff falls back to 'git diff' for empty repos."""
    # First call (git diff HEAD) fails, second (git diff) succeeds
    mock_run.side_effect = [
        MagicMock(returncode=1, stdout="", stderr="fatal: bad revision 'HEAD'"),
        MagicMock(returncode=0, stdout="diff content", stderr=""),
    ]

    provider = _GitProvider()
    success, diff_text = provider.diff("/workspace")

    assert success is True
    assert diff_text == "diff content"
    assert mock_run.call_count == 2


@patch("vcs_provider._git.subprocess.run")
def test_git_diff_both_fail(mock_run: MagicMock) -> None:
    """Test _GitProvider.diff when both HEAD and plain diff fail."""
    mock_run.side_effect = [
        MagicMock(returncode=1, stdout="", stderr="fatal: bad revision 'HEAD'"),
        MagicMock(returncode=1, stdout="", stderr="repository error"),
    ]

    provider = _GitProvider()
    success, error = provider.diff("/workspace")

    assert success is False
    assert error is not None
    assert "git diff failed" in error


# === Tests for diff_revision ===


@patch("vcs_provider._git.subprocess.run")
def test_git_diff_revision_success(mock_run: MagicMock) -> None:
    """Test _GitProvider.diff_revision on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="diff output", stderr="")

    provider = _GitProvider()
    success, diff_text = provider.diff_revision("abc123", "/workspace")

    assert success is True
    assert diff_text == "diff output"
    assert mock_run.call_args[0][0] == ["git", "diff", "abc123~1", "abc123"]


@patch("vcs_provider._git.subprocess.run")
def test_git_diff_revision_root_commit_fallback(mock_run: MagicMock) -> None:
    """Test _GitProvider.diff_revision falls back for root commits."""
    mock_run.side_effect = [
        MagicMock(returncode=1, stdout="", stderr="fatal: bad revision"),
        MagicMock(returncode=0, stdout="root diff", stderr=""),
    ]

    provider = _GitProvider()
    success, diff_text = provider.diff_revision("abc123", "/workspace")

    assert success is True
    assert diff_text == "root diff"
    second_call = mock_run.call_args_list[1]
    assert second_call[0][0] == ["git", "show", "--format=", "--patch", "abc123"]


@patch("vcs_provider._git.subprocess.run")
def test_git_diff_revision_both_fail(mock_run: MagicMock) -> None:
    """Test _GitProvider.diff_revision when both attempts fail."""
    mock_run.side_effect = [
        MagicMock(returncode=1, stdout="", stderr="bad revision"),
        MagicMock(returncode=1, stdout="", stderr="unknown revision"),
    ]

    provider = _GitProvider()
    success, error = provider.diff_revision("bad_rev", "/workspace")

    assert success is False
    assert error is not None
    assert "git diff failed" in error


# === Tests for apply_patch ===


@patch("vcs_provider._git.subprocess.run")
@patch("os.path.exists", return_value=True)
def test_git_apply_patch_success(mock_exists: MagicMock, mock_run: MagicMock) -> None:
    """Test _GitProvider.apply_patch on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _GitProvider()
    success, error = provider.apply_patch("/tmp/fix.patch", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == ["git", "apply", "/tmp/fix.patch"]


@patch("os.path.exists", return_value=False)
def test_git_apply_patch_file_not_found(mock_exists: MagicMock) -> None:
    """Test _GitProvider.apply_patch when file doesn't exist."""
    provider = _GitProvider()
    success, error = provider.apply_patch("/tmp/missing.patch", "/workspace")

    assert success is False
    assert error is not None
    assert "Diff file not found" in error


@patch("vcs_provider._git.subprocess.run")
@patch("os.path.exists", return_value=True)
def test_git_apply_patch_failure(mock_exists: MagicMock, mock_run: MagicMock) -> None:
    """Test _GitProvider.apply_patch when git apply fails."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="patch does not apply"
    )

    provider = _GitProvider()
    success, error = provider.apply_patch("/tmp/bad.patch", "/workspace")

    assert success is False
    assert error is not None
    assert "patch does not apply" in error


# === Tests for apply_patches ===


def test_git_apply_patches_empty_list() -> None:
    """Test _GitProvider.apply_patches with empty list."""
    provider = _GitProvider()
    success, error = provider.apply_patches([], "/workspace")

    assert success is True
    assert error is None


@patch("vcs_provider._git.subprocess.run")
@patch("os.path.exists", return_value=True)
def test_git_apply_patches_success(mock_exists: MagicMock, mock_run: MagicMock) -> None:
    """Test _GitProvider.apply_patches on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _GitProvider()
    success, error = provider.apply_patches(
        ["/tmp/a.patch", "/tmp/b.patch"], "/workspace"
    )

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == ["git", "apply", "/tmp/a.patch", "/tmp/b.patch"]


@patch("os.path.exists", side_effect=[True, False])
def test_git_apply_patches_missing_file(mock_exists: MagicMock) -> None:
    """Test _GitProvider.apply_patches when a file is missing."""
    provider = _GitProvider()
    success, error = provider.apply_patches(
        ["/tmp/a.patch", "/tmp/missing.patch"], "/workspace"
    )

    assert success is False
    assert error is not None
    assert "Diff file not found" in error


@patch("vcs_provider._git.subprocess.run")
@patch("os.path.exists", return_value=True)
def test_git_apply_patches_failure(mock_exists: MagicMock, mock_run: MagicMock) -> None:
    """Test _GitProvider.apply_patches when git apply fails."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="conflict")

    provider = _GitProvider()
    success, error = provider.apply_patches(["/tmp/a.patch"], "/workspace")

    assert success is False
    assert error is not None
    assert "conflict" in error


# === Tests for add_remove ===


@patch("vcs_provider._git.subprocess.run")
def test_git_add_remove_success(mock_run: MagicMock) -> None:
    """Test _GitProvider.add_remove on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _GitProvider()
    success, error = provider.add_remove("/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == ["git", "add", "-A"]


@patch("vcs_provider._git.subprocess.run")
def test_git_add_remove_failure(mock_run: MagicMock) -> None:
    """Test _GitProvider.add_remove on failure."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="fatal: not a git repo"
    )

    provider = _GitProvider()
    success, error = provider.add_remove("/workspace")

    assert success is False
    assert error is not None
    assert "git add -A failed" in error


# === Tests for clean_workspace ===


@patch("vcs_provider._git.subprocess.run")
def test_git_clean_workspace_success(mock_run: MagicMock) -> None:
    """Test _GitProvider.clean_workspace on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _GitProvider()
    success, error = provider.clean_workspace("/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_count == 2
    assert mock_run.call_args_list[0][0][0] == ["git", "reset", "--hard", "HEAD"]
    assert mock_run.call_args_list[1][0][0] == ["git", "clean", "-fd"]


@patch("vcs_provider._git.subprocess.run")
def test_git_clean_workspace_reset_fails(mock_run: MagicMock) -> None:
    """Test _GitProvider.clean_workspace when reset fails."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="reset error")

    provider = _GitProvider()
    success, error = provider.clean_workspace("/workspace")

    assert success is False
    assert error is not None
    assert "git reset --hard failed" in error


@patch("vcs_provider._git.subprocess.run")
def test_git_clean_workspace_clean_fails(mock_run: MagicMock) -> None:
    """Test _GitProvider.clean_workspace when clean step fails."""
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="", stderr=""),  # reset succeeds
        MagicMock(returncode=1, stdout="", stderr="clean error"),  # clean fails
    ]

    provider = _GitProvider()
    success, error = provider.clean_workspace("/workspace")

    assert success is False
    assert error is not None
    assert "git clean -fd failed" in error
