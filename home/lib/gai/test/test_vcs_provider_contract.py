"""Cross-provider contract tests.

Verifies that both Git and Hg providers conform to the same VCSProvider
interface contract using parameterized tests.
"""

from unittest.mock import MagicMock, patch

import pytest
from vcs_provider._base import VCSProvider
from vcs_provider._git import _GitProvider
from vcs_provider._hg import _HgProvider

# Shared parameterization for both providers.
_PROVIDERS = pytest.mark.parametrize(
    "provider_cls,mock_target",
    [
        (_GitProvider, "vcs_provider._git.subprocess.run"),
        (_HgProvider, "vcs_provider._hg.subprocess.run"),
    ],
    ids=["git", "hg"],
)


# === Tests for isinstance check ===


@_PROVIDERS
def test_provider_is_vcs_provider(
    provider_cls: type[VCSProvider], mock_target: str
) -> None:
    """Both providers are instances of VCSProvider."""
    provider = provider_cls()
    assert isinstance(provider, VCSProvider)


# === Tests for checkout contract ===


@_PROVIDERS
def test_checkout_success_returns_true_none(
    provider_cls: type[VCSProvider], mock_target: str
) -> None:
    """checkout returns (True, None) on success."""
    with patch(mock_target) as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        provider = provider_cls()
        success, error = provider.checkout("main", "/workspace")

    assert success is True
    assert error is None


@_PROVIDERS
def test_checkout_failure_returns_false_str(
    provider_cls: type[VCSProvider], mock_target: str
) -> None:
    """checkout returns (False, str) on failure."""
    with patch(mock_target) as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="branch not found"
        )
        provider = provider_cls()
        success, error = provider.checkout("bad", "/workspace")

    assert success is False
    assert isinstance(error, str)


# === Tests for diff contract ===


@_PROVIDERS
def test_diff_success_returns_true(
    provider_cls: type[VCSProvider], mock_target: str
) -> None:
    """diff returns (True, ...) on success."""
    with patch(mock_target) as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="diff output", stderr="")
        provider = provider_cls()
        success, text = provider.diff("/workspace")

    assert success is True
    assert text is not None


@_PROVIDERS
def test_diff_clean_returns_true_none(
    provider_cls: type[VCSProvider], mock_target: str
) -> None:
    """diff returns (True, None) when workspace is clean."""
    with patch(mock_target) as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        provider = provider_cls()
        success, text = provider.diff("/workspace")

    assert success is True
    assert text is None


# === Tests for add_remove contract ===


@_PROVIDERS
def test_add_remove_success_returns_true_none(
    provider_cls: type[VCSProvider], mock_target: str
) -> None:
    """add_remove returns (True, None) on success."""
    with patch(mock_target) as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        provider = provider_cls()
        success, error = provider.add_remove("/workspace")

    assert success is True
    assert error is None


@_PROVIDERS
def test_add_remove_failure_returns_false_str(
    provider_cls: type[VCSProvider], mock_target: str
) -> None:
    """add_remove returns (False, str) on failure."""
    with patch(mock_target) as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not a repo")
        provider = provider_cls()
        success, error = provider.add_remove("/workspace")

    assert success is False
    assert isinstance(error, str)


# === Tests for amend contract ===


@_PROVIDERS
def test_amend_success_returns_true_none(
    provider_cls: type[VCSProvider], mock_target: str
) -> None:
    """amend returns (True, None) on success."""
    with patch(mock_target) as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        provider = provider_cls()
        success, error = provider.amend("fix typo", "/workspace")

    assert success is True
    assert error is None


@_PROVIDERS
def test_amend_failure_returns_false_str(
    provider_cls: type[VCSProvider], mock_target: str
) -> None:
    """amend returns (False, str) on failure."""
    with patch(mock_target) as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="nothing to amend"
        )
        provider = provider_cls()
        success, error = provider.amend("note", "/workspace")

    assert success is False
    assert isinstance(error, str)


# === Tests for rename_branch contract ===


@_PROVIDERS
def test_rename_branch_success_returns_true_none(
    provider_cls: type[VCSProvider], mock_target: str
) -> None:
    """rename_branch returns (True, None) on success."""
    with patch(mock_target) as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        provider = provider_cls()
        success, error = provider.rename_branch("new_name", "/workspace")

    assert success is True
    assert error is None


@_PROVIDERS
def test_rename_branch_failure_returns_false_str(
    provider_cls: type[VCSProvider], mock_target: str
) -> None:
    """rename_branch returns (False, str) on failure."""
    with patch(mock_target) as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="rename error"
        )
        provider = provider_cls()
        success, error = provider.rename_branch("bad", "/workspace")

    assert success is False
    assert isinstance(error, str)


# === Tests for rebase contract ===


@_PROVIDERS
def test_rebase_success_returns_true_none(
    provider_cls: type[VCSProvider], mock_target: str
) -> None:
    """rebase returns (True, None) on success."""
    with patch(mock_target) as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        provider = provider_cls()
        success, error = provider.rebase("feature", "main", "/workspace")

    assert success is True
    assert error is None


@_PROVIDERS
def test_rebase_failure_returns_false_str(
    provider_cls: type[VCSProvider], mock_target: str
) -> None:
    """rebase returns (False, str) on failure."""
    with patch(mock_target) as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="conflict")
        provider = provider_cls()
        success, error = provider.rebase("feature", "main", "/workspace")

    assert success is False
    assert isinstance(error, str)


# === Tests for clean_workspace contract ===


@_PROVIDERS
def test_clean_workspace_success_returns_true_none(
    provider_cls: type[VCSProvider], mock_target: str
) -> None:
    """clean_workspace returns (True, None) on success."""
    with patch(mock_target) as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        provider = provider_cls()
        success, error = provider.clean_workspace("/workspace")

    assert success is True
    assert error is None


@_PROVIDERS
def test_clean_workspace_failure_returns_false_str(
    provider_cls: type[VCSProvider], mock_target: str
) -> None:
    """clean_workspace returns (False, str) on failure."""
    with patch(mock_target) as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="clean error")
        provider = provider_cls()
        success, error = provider.clean_workspace("/workspace")

    assert success is False
    assert isinstance(error, str)


# === Tests for archive contract ===


@_PROVIDERS
def test_archive_success_returns_true_none(
    provider_cls: type[VCSProvider], mock_target: str
) -> None:
    """archive returns (True, None) on success.

    Git archive is multi-step (tag + branch delete), Hg is single command.
    Both should return (True, None) on full success.
    """
    with patch(mock_target) as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        provider = provider_cls()
        success, error = provider.archive("old-feature", "/workspace")

    assert success is True
    assert error is None


@_PROVIDERS
def test_archive_failure_returns_false_str(
    provider_cls: type[VCSProvider], mock_target: str
) -> None:
    """archive returns (False, str) on failure."""
    with patch(mock_target) as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="archive error"
        )
        provider = provider_cls()
        success, error = provider.archive("old-feature", "/workspace")

    assert success is False
    assert isinstance(error, str)


# === Tests for prepare_description_for_reword contract ===


@_PROVIDERS
def test_prepare_description_returns_str(
    provider_cls: type[VCSProvider], mock_target: str
) -> None:
    """prepare_description_for_reword always returns a str."""
    provider = provider_cls()
    result = provider.prepare_description_for_reword("hello\nworld")

    assert isinstance(result, str)
    # Both providers should handle the input without error;
    # the actual escaping differs (Hg escapes newlines, Git passes through)
