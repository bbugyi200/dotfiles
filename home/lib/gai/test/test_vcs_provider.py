"""Tests for the vcs_provider package."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from vcs_provider import (
    VCSOperationError,
    VCSProvider,
    VCSProviderNotFoundError,
    get_vcs_provider,
)
from vcs_provider._hg import _HgProvider
from vcs_provider._registry import _resolve_vcs_name
from vcs_provider._types import CommandOutput
from vcs_provider.config import get_vcs_provider_config

# === Tests for CommandOutput ===


def test_command_output_success() -> None:
    """Test CommandOutput reports success for returncode 0."""
    out = CommandOutput(0, "output", "")
    assert out.success is True


def test_command_output_failure() -> None:
    """Test CommandOutput reports failure for non-zero returncode."""
    out = CommandOutput(1, "", "error")
    assert out.success is False


# === Tests for errors ===


def test_vcs_operation_error() -> None:
    """Test VCSOperationError stores operation and message."""
    err = VCSOperationError("checkout", "branch not found")
    assert err.operation == "checkout"
    assert err.message == "branch not found"
    assert "checkout" in str(err)
    assert "branch not found" in str(err)


def test_vcs_provider_not_found_error() -> None:
    """Test VCSProviderNotFoundError stores directory."""
    err = VCSProviderNotFoundError("/some/dir")
    assert err.directory == "/some/dir"
    assert "/some/dir" in str(err)


# === Tests for registry / auto-detect ===


def test_get_vcs_provider_detects_hg() -> None:
    """Test get_vcs_provider detects .hg directory and returns _HgProvider."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, ".hg"))
        provider = get_vcs_provider(tmpdir)
        assert isinstance(provider, _HgProvider)


def test_get_vcs_provider_not_found() -> None:
    """Test get_vcs_provider raises when no VCS detected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(VCSProviderNotFoundError) as exc_info:
            get_vcs_provider(tmpdir)
        assert tmpdir in str(exc_info.value)


# === Tests for _HgProvider methods ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_checkout_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.checkout on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, error = provider.checkout("my_branch", "/workspace")

    assert success is True
    assert error is None
    mock_run.assert_called_once()
    assert mock_run.call_args[0][0] == ["bb_hg_update", "my_branch"]


@patch("vcs_provider._hg.subprocess.run")
def test_hg_checkout_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.checkout on failure."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="branch not found"
    )

    provider = _HgProvider()
    success, error = provider.checkout("bad_branch", "/workspace")

    assert success is False
    assert error is not None
    assert "bb_hg_update failed" in error


@patch("vcs_provider._hg.subprocess.run")
def test_hg_diff_with_changes(mock_run: MagicMock) -> None:
    """Test _HgProvider.diff returns diff text when changes exist."""
    mock_run.return_value = MagicMock(
        returncode=0, stdout="diff --git a/file.py b/file.py\n+new line", stderr=""
    )

    provider = _HgProvider()
    success, diff_text = provider.diff("/workspace")

    assert success is True
    assert diff_text is not None
    assert "new line" in diff_text


@patch("vcs_provider._hg.subprocess.run")
def test_hg_diff_no_changes(mock_run: MagicMock) -> None:
    """Test _HgProvider.diff returns None when no changes."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, diff_text = provider.diff("/workspace")

    assert success is True
    assert diff_text is None


@patch("vcs_provider._hg.subprocess.run")
def test_hg_diff_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.diff on failure."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="repository error"
    )

    provider = _HgProvider()
    success, error = provider.diff("/workspace")

    assert success is False
    assert error is not None
    assert "hg diff failed" in error


@patch("vcs_provider._hg.subprocess.run")
def test_hg_amend_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.amend on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, error = provider.amend("fix typo", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == ["bb_hg_amend", "fix typo"]


@patch("vcs_provider._hg.subprocess.run")
def test_hg_amend_no_upload(mock_run: MagicMock) -> None:
    """Test _HgProvider.amend with no_upload flag."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, _ = provider.amend("fix typo", "/workspace", no_upload=True)

    assert success is True
    assert mock_run.call_args[0][0] == ["bb_hg_amend", "--no-upload", "fix typo"]


@patch("vcs_provider._hg.subprocess.run")
def test_hg_get_branch_name_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.get_branch_name on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="my_branch\n", stderr="")

    provider = _HgProvider()
    success, name = provider.get_branch_name("/workspace")

    assert success is True
    assert name == "my_branch"


@patch("vcs_provider._hg.subprocess.run")
def test_hg_get_branch_name_empty(mock_run: MagicMock) -> None:
    """Test _HgProvider.get_branch_name returns None when empty."""
    mock_run.return_value = MagicMock(returncode=0, stdout="\n", stderr="")

    provider = _HgProvider()
    success, name = provider.get_branch_name("/workspace")

    assert success is True
    assert name is None


@patch("vcs_provider._hg.subprocess.run")
def test_hg_get_cl_number_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.get_cl_number on success with digit output."""
    mock_run.return_value = MagicMock(returncode=0, stdout="12345\n", stderr="")

    provider = _HgProvider()
    success, number = provider.get_cl_number("/workspace")

    assert success is True
    assert number == "12345"


@patch("vcs_provider._hg.subprocess.run")
def test_hg_get_cl_number_non_digit(mock_run: MagicMock) -> None:
    """Test _HgProvider.get_cl_number returns None for non-digit output."""
    mock_run.return_value = MagicMock(returncode=0, stdout="not_a_number\n", stderr="")

    provider = _HgProvider()
    success, number = provider.get_cl_number("/workspace")

    assert success is True
    assert number is None


@patch("vcs_provider._hg.subprocess.run")
def test_hg_stash_and_clean_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.stash_and_clean on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, error = provider.stash_and_clean("backup_diff", "/workspace")

    assert success is True
    assert error is None
    assert mock_run.call_args[0][0] == ["bb_hg_clean", "backup_diff"]


@patch("vcs_provider._hg.subprocess.run")
def test_hg_stash_and_clean_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.stash_and_clean on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="clean failed")

    provider = _HgProvider()
    success, error = provider.stash_and_clean("backup_diff", "/workspace")

    assert success is False
    assert error is not None
    assert "clean failed" in error


@patch("vcs_provider._hg.subprocess.run")
def test_hg_rename_branch(mock_run: MagicMock) -> None:
    """Test _HgProvider.rename_branch on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, _error = provider.rename_branch("new_name", "/workspace")

    assert success is True
    assert mock_run.call_args[0][0] == ["bb_hg_rename", "new_name"]


@patch("vcs_provider._hg.subprocess.run")
def test_hg_command_timeout(mock_run: MagicMock) -> None:
    """Test _HgProvider handles command timeout."""
    import subprocess

    mock_run.side_effect = subprocess.TimeoutExpired(cmd="bb_hg_update", timeout=300)

    provider = _HgProvider()
    success, error = provider.checkout("my_branch", "/workspace")

    assert success is False
    assert error is not None
    assert "timed out" in error


@patch("vcs_provider._hg.subprocess.run")
def test_hg_command_not_found(mock_run: MagicMock) -> None:
    """Test _HgProvider handles command not found."""
    mock_run.side_effect = FileNotFoundError()

    provider = _HgProvider()
    success, _error = provider.checkout("my_branch", "/workspace")

    assert success is False
    assert _error is not None
    assert "not found" in _error


# === Tests for _HgProvider.sync_workspace ===


@patch("vcs_provider._hg.subprocess.run")
def test_hg_sync_workspace_success(mock_run: MagicMock) -> None:
    """Test _HgProvider.sync_workspace on success."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    provider = _HgProvider()
    success, error = provider.sync_workspace("/workspace")

    assert success is True
    assert error is None
    mock_run.assert_called_once()
    assert mock_run.call_args[0][0] == ["bb_hg_sync"]


@patch("vcs_provider._hg.subprocess.run")
def test_hg_sync_workspace_failure(mock_run: MagicMock) -> None:
    """Test _HgProvider.sync_workspace on failure."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="sync error")

    provider = _HgProvider()
    success, error = provider.sync_workspace("/workspace")

    assert success is False
    assert error is not None
    assert "bb_hg_sync failed" in error


# === Tests for Google-internal method defaults ===


def test_vcs_provider_google_methods_raise() -> None:
    """Test that Google-internal methods raise NotImplementedError by default."""
    provider = _MinimalProvider()

    methods_to_test = [
        lambda: provider.sync_workspace("/cwd"),
        lambda: provider.reword("desc", "/cwd"),
        lambda: provider.reword_add_tag("tag", "val", "/cwd"),
        lambda: provider.get_description("rev", "/cwd"),
        lambda: provider.get_branch_name("/cwd"),
        lambda: provider.get_cl_number("/cwd"),
        lambda: provider.get_workspace_name("/cwd"),
        lambda: provider.has_local_changes("/cwd"),
        lambda: provider.get_bug_number("/cwd"),
        lambda: provider.mail("rev", "/cwd"),
        lambda: provider.fix("/cwd"),
        lambda: provider.upload("/cwd"),
        lambda: provider.find_reviewers("123", "/cwd"),
        lambda: provider.rewind(["/path"], "/cwd"),
        lambda: provider.get_change_url("/cwd"),
    ]

    for method in methods_to_test:
        with pytest.raises(NotImplementedError):
            method()


# === Tests for prepare_description_for_reword ===


def test_hg_prepare_description_for_reword_escapes_newlines() -> None:
    """Test that _HgProvider escapes newlines for bb_hg_reword."""
    provider = _HgProvider()
    assert provider.prepare_description_for_reword("hello\nworld") == "hello\\nworld"


def test_git_prepare_description_for_reword_passthrough() -> None:
    """Test that _GitProvider returns description unchanged."""
    from vcs_provider._git import _GitProvider

    provider = _GitProvider()
    assert provider.prepare_description_for_reword("hello\nworld") == "hello\nworld"


def test_default_prepare_description_for_reword_passthrough() -> None:
    """Test that the base default returns description unchanged."""
    provider = _MinimalProvider()
    assert provider.prepare_description_for_reword("hello\nworld") == "hello\nworld"


class _MinimalProvider(VCSProvider):
    """Minimal concrete provider for testing defaults."""

    def checkout(self, revision: str, cwd: str) -> tuple[bool, str | None]:
        return (True, None)

    def diff(self, cwd: str) -> tuple[bool, str | None]:
        return (True, None)

    def diff_revision(self, revision: str, cwd: str) -> tuple[bool, str | None]:
        return (True, None)

    def apply_patch(self, patch_path: str, cwd: str) -> tuple[bool, str | None]:
        return (True, None)

    def apply_patches(
        self, patch_paths: list[str], cwd: str
    ) -> tuple[bool, str | None]:
        return (True, None)

    def add_remove(self, cwd: str) -> tuple[bool, str | None]:
        return (True, None)

    def clean_workspace(self, cwd: str) -> tuple[bool, str | None]:
        return (True, None)

    def commit(self, name: str, logfile: str, cwd: str) -> tuple[bool, str | None]:
        return (True, None)

    def amend(
        self, note: str, cwd: str, *, no_upload: bool = False
    ) -> tuple[bool, str | None]:
        return (True, None)

    def rename_branch(self, new_name: str, cwd: str) -> tuple[bool, str | None]:
        return (True, None)

    def rebase(
        self, branch_name: str, new_parent: str, cwd: str
    ) -> tuple[bool, str | None]:
        return (True, None)

    def archive(self, revision: str, cwd: str) -> tuple[bool, str | None]:
        return (True, None)

    def prune(self, revision: str, cwd: str) -> tuple[bool, str | None]:
        return (True, None)

    def stash_and_clean(
        self, diff_name: str, cwd: str, *, timeout: int = 300
    ) -> tuple[bool, str | None]:
        return (True, None)


# === Tests for _resolve_vcs_name ===


def test_resolve_vcs_name_env_var_override() -> None:
    """Env var GAI_VCS_PROVIDER=hg overrides auto-detection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, ".git"))
        with patch.dict(os.environ, {"GAI_VCS_PROVIDER": "hg"}):
            assert _resolve_vcs_name(tmpdir) == "hg"


def test_resolve_vcs_name_env_var_auto() -> None:
    """GAI_VCS_PROVIDER=auto bypasses config and auto-detects."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, ".git"))
        with patch.dict(os.environ, {"GAI_VCS_PROVIDER": "auto"}):
            with patch(
                "vcs_provider._registry.get_vcs_provider_config",
                return_value={"provider": "hg"},
            ):
                assert _resolve_vcs_name(tmpdir) == "git"


def test_resolve_vcs_name_config_override() -> None:
    """Config provider: hg overrides auto-detection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, ".git"))
        with patch.dict(os.environ, {}, clear=False):
            # Ensure env var is not set
            os.environ.pop("GAI_VCS_PROVIDER", None)
            with patch(
                "vcs_provider._registry.get_vcs_provider_config",
                return_value={"provider": "hg"},
            ):
                assert _resolve_vcs_name(tmpdir) == "hg"


def test_resolve_vcs_name_config_auto() -> None:
    """Config provider: auto falls through to detect_vcs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, ".git"))
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GAI_VCS_PROVIDER", None)
            with patch(
                "vcs_provider._registry.get_vcs_provider_config",
                return_value={"provider": "auto"},
            ):
                assert _resolve_vcs_name(tmpdir) == "git"


def test_resolve_vcs_name_default_auto_detects() -> None:
    """No env/config falls through to detect_vcs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, ".hg"))
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GAI_VCS_PROVIDER", None)
            with patch(
                "vcs_provider._registry.get_vcs_provider_config",
                return_value={},
            ):
                assert _resolve_vcs_name(tmpdir) == "hg"


# === Tests for get_vcs_provider_config ===


def test_get_vcs_provider_config_missing_file() -> None:
    """Returns empty dict when config file doesn't exist."""
    with patch("vcs_provider.config.os.path.exists", return_value=False):
        assert get_vcs_provider_config() == {}


def test_get_vcs_provider_config_no_section() -> None:
    """Returns empty dict when vcs_provider section is absent."""
    with patch("vcs_provider.config.os.path.exists", return_value=True):
        with patch(
            "builtins.open",
            MagicMock(
                return_value=MagicMock(
                    __enter__=lambda s: s,
                    __exit__=MagicMock(return_value=False),
                    read=MagicMock(return_value="llm_provider:\n  provider: gemini\n"),
                )
            ),
        ):
            with patch(
                "vcs_provider.config.yaml.safe_load",
                return_value={"llm_provider": {"provider": "gemini"}},
            ):
                assert get_vcs_provider_config() == {}


def test_get_vcs_provider_config_with_section() -> None:
    """Returns vcs_provider dict when section is present."""
    with patch("vcs_provider.config.os.path.exists", return_value=True):
        with patch(
            "builtins.open",
            MagicMock(
                return_value=MagicMock(
                    __enter__=lambda s: s,
                    __exit__=MagicMock(return_value=False),
                    read=MagicMock(return_value=""),
                )
            ),
        ):
            with patch(
                "vcs_provider.config.yaml.safe_load",
                return_value={"vcs_provider": {"provider": "hg"}},
            ):
                result = get_vcs_provider_config()
                assert result == {"provider": "hg"}
