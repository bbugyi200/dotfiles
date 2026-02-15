"""Tests for the Mercurial VCS provider — query/info methods.

Covers: get_description, has_local_changes, get_workspace_name, reword,
reword_add_tag, get_change_url, get_bug_number, mail, fix, upload,
find_reviewers, rewind.
"""

from unittest.mock import MagicMock, patch

from vcs_provider._hg import _HgProvider

# === Tests for get_description ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_get_description_full(mock_run: MagicMock) -> None:
    """Test _HgProvider.get_description returns full description."""
    mock_run.return_value = MagicMock(
        returncode=0, stdout="Full commit message\n\nBody text\n", stderr=""
    )

    provider = _HgProvider()
    success, desc = provider.get_description("abc123", "/workspace")

    assert success is True
    assert desc is not None
    assert "Full commit message" in desc
    assert mock_run.call_args[0][0] == ["cl_desc", "-r", "abc123"]


@patch("vcs_provider._hg.subprocess.run")
def test_hg_get_description_short(mock_run: MagicMock) -> None:
    """Test _HgProvider.get_description with short=True."""
    mock_run.return_value = MagicMock(returncode=0, stdout="Short subject\n", stderr="")

    provider = _HgProvider()
    success, desc = provider.get_description("abc123", "/workspace", short=True)

    assert success is True
    assert desc is not None
    assert "Short subject" in desc
    assert mock_run.call_args[0][0] == ["cl_desc", "-s"]


@patch("vcs_provider._hg.subprocess.run")
def test_hg_get_description_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.get_description on failure."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="unknown revision"
    )

    provider = _HgProvider()
    success, error = provider.get_description("bad_rev", "/workspace")

    assert success is False
    assert error is not None
    assert "unknown revision" in error


# === Tests for has_local_changes ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_has_local_changes_with_changes(mock_run: MagicMock) -> None:
    """Test _HgProvider.has_local_changes when changes exist."""
    mock_run.return_value = MagicMock(returncode=0, stdout="M file.py\n", stderr="")

    provider = _HgProvider()
    success, text = provider.has_local_changes("/workspace")

    assert success is True
    assert text is not None
    assert "file.py" in text


@patch("vcs_provider._hg.subprocess.run")
def test_hg_has_local_changes_clean(mock_run: MagicMock) -> None:
    """Test _HgProvider.has_local_changes when workspace is clean."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, text = provider.has_local_changes("/workspace")

    assert success is True
    assert text is None


# === Tests for get_workspace_name ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_get_workspace_name_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.get_workspace_name on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="my-workspace\n", stderr="")

    provider = _HgProvider()
    success, name = provider.get_workspace_name("/workspace")

    assert success is True
    assert name == "my-workspace"


@patch("vcs_provider._hg.subprocess.run")
def test_hg_get_workspace_name_empty(mock_run: MagicMock) -> None:
    """Test _HgProvider.get_workspace_name returns None when empty."""
    mock_run.return_value = MagicMock(returncode=0, stdout="\n", stderr="")

    provider = _HgProvider()
    success, name = provider.get_workspace_name("/workspace")

    assert success is True
    assert name is None


@patch("vcs_provider._hg.subprocess.run")
def test_hg_get_workspace_name_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.get_workspace_name on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")

    provider = _HgProvider()
    success, error = provider.get_workspace_name("/workspace")

    assert success is False
    assert error is not None
    assert "workspace_name command failed" in error


# === Tests for reword ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_reword_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.reword on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, error = provider.reword("new description", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == ["bb_hg_reword", "new description"]


@patch("vcs_provider._hg.subprocess.run")
def test_hg_reword_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.reword on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="reword error")

    provider = _HgProvider()
    success, error = provider.reword("desc", "/workspace")

    assert success is False
    assert error is not None
    assert "bb_hg_reword failed" in error


# === Tests for reword_add_tag ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_reword_add_tag_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.reword_add_tag on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, error = provider.reword_add_tag("BUG", "12345", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == [
        "bb_hg_reword",
        "--add-tag",
        "BUG",
        "12345",
    ]


@patch("vcs_provider._hg.subprocess.run")
def test_hg_reword_add_tag_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.reword_add_tag on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="reword error")

    provider = _HgProvider()
    success, error = provider.reword_add_tag("BUG", "12345", "/workspace")

    assert success is False
    assert error is not None
    assert "bb_hg_reword failed" in error


# === Tests for get_change_url ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_get_change_url_with_cl(mock_run: MagicMock) -> None:
    """Test _HgProvider.get_change_url when CL number exists."""
    mock_run.return_value = MagicMock(returncode=0, stdout="12345\n", stderr="")

    provider = _HgProvider()
    success, url = provider.get_change_url("/workspace")

    assert success is True
    assert url == "http://cl/12345"


@patch("vcs_provider._hg.subprocess.run")
def test_hg_get_change_url_no_cl(mock_run: MagicMock) -> None:
    """Test _HgProvider.get_change_url when no CL number."""
    mock_run.return_value = MagicMock(returncode=0, stdout="not_a_number\n", stderr="")

    provider = _HgProvider()
    success, url = provider.get_change_url("/workspace")

    assert success is True
    assert url is None


@patch("vcs_provider._hg.subprocess.run")
def test_hg_get_change_url_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.get_change_url when branch_number command fails."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")

    provider = _HgProvider()
    success, url = provider.get_change_url("/workspace")

    assert success is False
    assert url is None


# === Tests for get_bug_number ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_get_bug_number_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.get_bug_number on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="b/54321\n", stderr="")

    provider = _HgProvider()
    success, bug = provider.get_bug_number("/workspace")

    assert success is True
    assert bug == "b/54321"


@patch("vcs_provider._hg.subprocess.run")
def test_hg_get_bug_number_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.get_bug_number on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")

    provider = _HgProvider()
    success, error = provider.get_bug_number("/workspace")

    assert success is False
    assert error is not None
    assert "branch_bug command failed" in error


# === Tests for mail ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_mail_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.mail on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, error = provider.mail("abc123", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == ["hg", "mail", "-r", "abc123"]


@patch("vcs_provider._hg.subprocess.run")
def test_hg_mail_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.mail on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="mail error")

    provider = _HgProvider()
    success, error = provider.mail("abc123", "/workspace")

    assert success is False
    assert error is not None
    assert "hg mail failed" in error


# === Tests for fix ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_fix_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.fix on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, error = provider.fix("/workspace")

    assert success is True
    assert error is None
    # fix uses _run_shell
    assert mock_run.call_args[0][0] == "hg fix"


@patch("vcs_provider._hg.subprocess.run")
def test_hg_fix_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.fix on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="fix error")

    provider = _HgProvider()
    success, error = provider.fix("/workspace")

    assert success is False
    assert error is not None
    assert "hg fix failed" in error


# === Tests for upload ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_upload_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.upload on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, error = provider.upload("/workspace")

    assert success is True
    assert error is None
    # upload uses _run_shell
    assert mock_run.call_args[0][0] == "hg upload tree"


@patch("vcs_provider._hg.subprocess.run")
def test_hg_upload_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.upload on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="upload error")

    provider = _HgProvider()
    success, error = provider.upload("/workspace")

    assert success is False
    assert error is not None
    assert "hg upload tree failed" in error


# === Tests for find_reviewers ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_find_reviewers_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.find_reviewers on success."""
    mock_run.return_value = MagicMock(
        returncode=0, stdout="reviewer1,reviewer2\n", stderr=""
    )

    provider = _HgProvider()
    success, reviewers = provider.find_reviewers("12345", "/workspace")

    assert success is True
    assert reviewers is not None
    assert "reviewer1" in reviewers
    assert mock_run.call_args[0][0] == ["p4", "findreviewers", "-c", "12345"]


@patch("vcs_provider._hg.subprocess.run")
def test_hg_find_reviewers_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.find_reviewers on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="p4 error")

    provider = _HgProvider()
    success, error = provider.find_reviewers("12345", "/workspace")

    assert success is False
    assert error is not None
    assert "p4 error" in error


# === Tests for rewind ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_rewind_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.rewind on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, error = provider.rewind(["/tmp/a.diff", "/tmp/b.diff"], "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == [
        "gai_rewind",
        "/tmp/a.diff",
        "/tmp/b.diff",
    ]
    # Verify 600s timeout
    assert mock_run.call_args[1]["timeout"] == 600


@patch("vcs_provider._hg.subprocess.run")
def test_hg_rewind_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.rewind on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="rewind error")

    provider = _HgProvider()
    success, error = provider.rewind(["/tmp/a.diff"], "/workspace")

    assert success is False
    assert error is not None
    assert "gai_rewind failed" in error


@patch("vcs_provider._hg.subprocess.run")
def test_hg_rewind_timeout(mock_run: MagicMock) -> None:
    """Test _HgProvider.rewind handles timeout."""
    import subprocess

    mock_run.side_effect = subprocess.TimeoutExpired(cmd="gai_rewind", timeout=600)

    provider = _HgProvider()
    success, error = provider.rewind(["/tmp/a.diff"], "/workspace")

    assert success is False
    assert error is not None
    assert "timed out" in error
