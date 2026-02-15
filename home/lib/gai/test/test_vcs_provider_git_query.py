"""Tests for the git VCS provider — query/info methods and Phase 5 additions.

Covers: get_branch_name, get_description, has_local_changes, get_workspace_name,
reword, unimplemented methods, get_change_url, get_cl_number, get_bug_number,
fix, upload, mail, reword_add_tag.
"""

from unittest.mock import MagicMock, patch

import pytest
from vcs_provider._git import _GitProvider

# === Tests for get_branch_name ===


@patch("vcs_provider._git.subprocess.run")
def test_git_get_branch_name_success(mock_run: MagicMock) -> None:
    """Test _GitProvider.get_branch_name on success."""
    mock_run.return_value = MagicMock(
        returncode=0, stdout="feature-branch\n", stderr=""
    )

    provider = _GitProvider()
    success, name = provider.get_branch_name("/workspace")

    assert success is True
    assert name == "feature-branch"


@patch("vcs_provider._git.subprocess.run")
def test_git_get_branch_name_detached_head(mock_run: MagicMock) -> None:
    """Test _GitProvider.get_branch_name returns None in detached HEAD."""
    mock_run.return_value = MagicMock(returncode=0, stdout="HEAD\n", stderr="")

    provider = _GitProvider()
    success, name = provider.get_branch_name("/workspace")

    assert success is True
    assert name is None


@patch("vcs_provider._git.subprocess.run")
def test_git_get_branch_name_failure(mock_run: MagicMock) -> None:
    """Test _GitProvider.get_branch_name on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not a git repo")

    provider = _GitProvider()
    success, error = provider.get_branch_name("/workspace")

    assert success is False
    assert error is not None
    assert "failed" in error


# === Tests for get_description ===


@patch("vcs_provider._git.subprocess.run")
def test_git_get_description_full(mock_run: MagicMock) -> None:
    """Test _GitProvider.get_description returns full description."""
    mock_run.return_value = MagicMock(
        returncode=0, stdout="Full commit message\n\nBody text\n", stderr=""
    )

    provider = _GitProvider()
    success, desc = provider.get_description("abc123", "/workspace")

    assert success is True
    assert desc is not None
    assert "Full commit message" in desc
    assert mock_run.call_args[0][0] == ["git", "log", "--format=%B", "-n1", "abc123"]


@patch("vcs_provider._git.subprocess.run")
def test_git_get_description_short(mock_run: MagicMock) -> None:
    """Test _GitProvider.get_description with short=True."""
    mock_run.return_value = MagicMock(returncode=0, stdout="Short subject\n", stderr="")

    provider = _GitProvider()
    success, desc = provider.get_description("abc123", "/workspace", short=True)

    assert success is True
    assert desc is not None
    assert "Short subject" in desc
    assert mock_run.call_args[0][0] == ["git", "log", "--format=%s", "-n1", "abc123"]


@patch("vcs_provider._git.subprocess.run")
def test_git_get_description_failure(mock_run: MagicMock) -> None:
    """Test _GitProvider.get_description on failure."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="unknown revision"
    )

    provider = _GitProvider()
    success, error = provider.get_description("bad_rev", "/workspace")

    assert success is False
    assert error is not None
    assert "unknown revision" in error


# === Tests for has_local_changes ===


@patch("vcs_provider._git.subprocess.run")
def test_git_has_local_changes_with_changes(mock_run: MagicMock) -> None:
    """Test _GitProvider.has_local_changes when changes exist."""
    mock_run.return_value = MagicMock(
        returncode=0, stdout=" M file.py\n?? new.py\n", stderr=""
    )

    provider = _GitProvider()
    success, text = provider.has_local_changes("/workspace")

    assert success is True
    assert text is not None
    assert "file.py" in text


@patch("vcs_provider._git.subprocess.run")
def test_git_has_local_changes_clean(mock_run: MagicMock) -> None:
    """Test _GitProvider.has_local_changes when workspace is clean."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _GitProvider()
    success, text = provider.has_local_changes("/workspace")

    assert success is True
    assert text is None


@patch("vcs_provider._git.subprocess.run")
def test_git_has_local_changes_failure(mock_run: MagicMock) -> None:
    """Test _GitProvider.has_local_changes on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not a repo")

    provider = _GitProvider()
    success, error = provider.has_local_changes("/workspace")

    assert success is False
    assert error is not None
    assert "not a repo" in error


# === Tests for get_workspace_name ===


@patch("vcs_provider._git.subprocess.run")
def test_git_get_workspace_name_from_remote(mock_run: MagicMock) -> None:
    """Test _GitProvider.get_workspace_name extracts from remote URL."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="https://github.com/user/my-repo.git\n",
        stderr="",
    )

    provider = _GitProvider()
    success, name = provider.get_workspace_name("/workspace")

    assert success is True
    assert name == "my-repo"


@patch("vcs_provider._git.subprocess.run")
def test_git_get_workspace_name_no_git_suffix(mock_run: MagicMock) -> None:
    """Test _GitProvider.get_workspace_name with URL without .git suffix."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="https://github.com/user/my-repo\n",
        stderr="",
    )

    provider = _GitProvider()
    success, name = provider.get_workspace_name("/workspace")

    assert success is True
    assert name == "my-repo"


@patch("vcs_provider._git.subprocess.run")
def test_git_get_workspace_name_fallback_to_root(mock_run: MagicMock) -> None:
    """Test _GitProvider.get_workspace_name falls back to repo root."""
    mock_run.side_effect = [
        MagicMock(returncode=1, stdout="", stderr=""),  # no remote
        MagicMock(
            returncode=0, stdout="/home/user/my-project\n", stderr=""
        ),  # toplevel
    ]

    provider = _GitProvider()
    success, name = provider.get_workspace_name("/workspace")

    assert success is True
    assert name == "my-project"


@patch("vcs_provider._git.subprocess.run")
def test_git_get_workspace_name_both_fail(mock_run: MagicMock) -> None:
    """Test _GitProvider.get_workspace_name when everything fails."""
    mock_run.side_effect = [
        MagicMock(returncode=1, stdout="", stderr=""),  # no remote
        MagicMock(returncode=1, stdout="", stderr=""),  # no toplevel
    ]

    provider = _GitProvider()
    success, error = provider.get_workspace_name("/workspace")

    assert success is False
    assert error is not None
    assert "Could not determine workspace name" in error


# === Tests for reword ===


@patch("vcs_provider._git.subprocess.run")
def test_git_reword_success(mock_run: MagicMock) -> None:
    """Test _GitProvider.reword on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _GitProvider()
    success, error = provider.reword("new description", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == [
        "git",
        "commit",
        "--amend",
        "-m",
        "new description",
    ]


@patch("vcs_provider._git.subprocess.run")
def test_git_reword_failure(mock_run: MagicMock) -> None:
    """Test _GitProvider.reword on failure."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="nothing to amend"
    )

    provider = _GitProvider()
    success, error = provider.reword("desc", "/workspace")

    assert success is False
    assert error is not None
    assert "git commit --amend failed" in error


# === Tests for unimplemented methods ===


def test_git_unimplemented_methods() -> None:
    """Test that Google-internal methods raise NotImplementedError."""
    provider = _GitProvider()

    methods_to_test = [
        lambda: provider.find_reviewers("123", "/cwd"),
        lambda: provider.rewind(["/path"], "/cwd"),
    ]

    for method in methods_to_test:
        with pytest.raises(NotImplementedError):
            method()


# === Tests for get_change_url ===


@patch("vcs_provider._git.subprocess.run")
def test_git_get_change_url_with_pr(mock_run: MagicMock) -> None:
    """Test _GitProvider.get_change_url when PR exists."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="https://github.com/user/repo/pull/42\n",
        stderr="",
    )

    provider = _GitProvider()
    success, url = provider.get_change_url("/workspace")

    assert success is True
    assert url == "https://github.com/user/repo/pull/42"


@patch("vcs_provider._git.subprocess.run")
def test_git_get_change_url_no_pr(mock_run: MagicMock) -> None:
    """Test _GitProvider.get_change_url when no PR exists."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="no pull requests found"
    )

    provider = _GitProvider()
    success, url = provider.get_change_url("/workspace")

    assert success is True
    assert url is None


# === Tests for get_cl_number (PR number) ===


@patch("vcs_provider._git.subprocess.run")
def test_git_get_cl_number_with_pr(mock_run: MagicMock) -> None:
    """Test _GitProvider.get_cl_number when PR exists."""
    mock_run.return_value = MagicMock(returncode=0, stdout="42\n", stderr="")

    provider = _GitProvider()
    success, number = provider.get_cl_number("/workspace")

    assert success is True
    assert number == "42"


@patch("vcs_provider._git.subprocess.run")
def test_git_get_cl_number_no_pr(mock_run: MagicMock) -> None:
    """Test _GitProvider.get_cl_number when no PR exists."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="no pull requests found"
    )

    provider = _GitProvider()
    success, number = provider.get_cl_number("/workspace")

    assert success is True
    assert number is None


# === Tests for get_bug_number ===


def test_git_get_bug_number() -> None:
    """Test _GitProvider.get_bug_number returns empty string."""
    provider = _GitProvider()
    success, bug = provider.get_bug_number("/workspace")

    assert success is True
    assert bug == ""


# === Tests for fix / upload (no-ops) ===


def test_git_fix_noop() -> None:
    """Test _GitProvider.fix returns success (no-op)."""
    provider = _GitProvider()
    success, error = provider.fix("/workspace")

    assert success is True
    assert error is None


def test_git_upload_noop() -> None:
    """Test _GitProvider.upload returns success (no-op)."""
    provider = _GitProvider()
    success, error = provider.upload("/workspace")

    assert success is True
    assert error is None


# === Tests for mail ===


@patch("vcs_provider._git.subprocess.run")
def test_git_mail_push_and_create_pr(mock_run: MagicMock) -> None:
    """Test _GitProvider.mail pushes and creates PR when none exists."""
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="", stderr=""),  # git push
        MagicMock(returncode=1, stdout="", stderr="no PR"),  # gh pr view (no PR)
        MagicMock(returncode=0, stdout="", stderr=""),  # gh pr create
    ]

    provider = _GitProvider()
    success, error = provider.mail("feature-branch", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_count == 3
    assert mock_run.call_args_list[0][0][0] == [
        "git",
        "push",
        "-u",
        "origin",
        "feature-branch",
    ]
    assert mock_run.call_args_list[2][0][0] == ["gh", "pr", "create", "--fill"]


@patch("vcs_provider._git.subprocess.run")
def test_git_mail_push_existing_pr(mock_run: MagicMock) -> None:
    """Test _GitProvider.mail just pushes when PR already exists."""
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="", stderr=""),  # git push
        MagicMock(returncode=0, stdout="42\n", stderr=""),  # gh pr view (PR exists)
    ]

    provider = _GitProvider()
    success, error = provider.mail("feature-branch", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_count == 2


@patch("vcs_provider._git.subprocess.run")
def test_git_mail_push_fails(mock_run: MagicMock) -> None:
    """Test _GitProvider.mail when push fails."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="permission denied"
    )

    provider = _GitProvider()
    success, error = provider.mail("feature-branch", "/workspace")

    assert success is False
    assert error is not None
    assert "git push failed" in error


# === Tests for reword_add_tag ===


@patch("vcs_provider._git.subprocess.run")
def test_git_reword_add_tag_success(mock_run: MagicMock) -> None:
    """Test _GitProvider.reword_add_tag appends tag to commit message."""
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="Existing message\n", stderr=""),  # git log
        MagicMock(returncode=0, stdout="", stderr=""),  # git commit --amend
    ]

    provider = _GitProvider()
    success, error = provider.reword_add_tag("BUG", "12345", "/workspace")

    assert success is True
    assert error is None
    # Verify the amended message includes the tag
    amend_call = mock_run.call_args_list[1]
    new_msg = amend_call[0][0][4]  # -m argument
    assert "Existing message\nBUG=12345" in new_msg


@patch("vcs_provider._git.subprocess.run")
def test_git_reword_add_tag_log_fails(mock_run: MagicMock) -> None:
    """Test _GitProvider.reword_add_tag when git log fails."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not a git repo")

    provider = _GitProvider()
    success, error = provider.reword_add_tag("BUG", "12345", "/workspace")

    assert success is False
    assert error is not None
