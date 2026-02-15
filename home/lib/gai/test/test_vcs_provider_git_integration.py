"""Integration tests for the Git VCS provider using real git commands.

These tests exercise _GitProvider against actual temporary git repositories
rather than mocking subprocess. They are skipped when git is not available.
"""

import os
import shutil
import subprocess
import tempfile

import pytest
from vcs_provider._git import _GitProvider

_GIT_AVAILABLE = shutil.which("git") is not None

pytestmark = pytest.mark.skipif(not _GIT_AVAILABLE, reason="git not available")


@pytest.fixture()
def git_repo(tmp_path: object) -> str:
    """Create a temporary git repo with one initial commit."""
    repo = str(tmp_path)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    # Create initial commit
    readme = os.path.join(repo, "README.md")
    with open(readme, "w") as f:
        f.write("# Test Repo\n")
    subprocess.run(
        ["git", "add", "README.md"], cwd=repo, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    return repo


# === Tests for diff ===


def test_integration_diff_detects_changes(git_repo: str) -> None:
    """diff returns diff text when there are uncommitted changes."""
    # Create a change
    with open(os.path.join(git_repo, "README.md"), "a") as f:
        f.write("new line\n")

    provider = _GitProvider()
    success, diff_text = provider.diff(git_repo)

    assert success is True
    assert diff_text is not None
    assert "new line" in diff_text


def test_integration_diff_clean_workspace(git_repo: str) -> None:
    """diff returns (True, None) when workspace is clean."""
    provider = _GitProvider()
    success, diff_text = provider.diff(git_repo)

    assert success is True
    assert diff_text is None


# === Tests for get_branch_name ===


def test_integration_get_branch_name(git_repo: str) -> None:
    """get_branch_name returns the current branch name."""
    provider = _GitProvider()
    success, name = provider.get_branch_name(git_repo)

    assert success is True
    # Default branch after git init (usually "main" or "master")
    assert name is not None
    assert len(name) > 0


# === Tests for get_description ===


def test_integration_get_description(git_repo: str) -> None:
    """get_description returns the commit message for HEAD."""
    provider = _GitProvider()
    success, desc = provider.get_description("HEAD", git_repo)

    assert success is True
    assert desc is not None
    assert "Initial commit" in desc


# === Tests for has_local_changes ===


def test_integration_has_local_changes_clean(git_repo: str) -> None:
    """has_local_changes returns (True, None) when clean."""
    provider = _GitProvider()
    success, text = provider.has_local_changes(git_repo)

    assert success is True
    assert text is None


def test_integration_has_local_changes_dirty(git_repo: str) -> None:
    """has_local_changes returns (True, str) when dirty."""
    with open(os.path.join(git_repo, "new_file.txt"), "w") as f:
        f.write("content\n")

    provider = _GitProvider()
    success, text = provider.has_local_changes(git_repo)

    assert success is True
    assert text is not None
    assert "new_file.txt" in text


# === Tests for commit ===


def test_integration_commit_creates_branch(git_repo: str) -> None:
    """commit creates a new branch and commits."""
    # Stage a file
    new_file = os.path.join(git_repo, "feature.txt")
    with open(new_file, "w") as f:
        f.write("feature content\n")
    subprocess.run(
        ["git", "add", "feature.txt"], cwd=git_repo, capture_output=True, check=True
    )

    # Write a log message file
    logfile = os.path.join(git_repo, "commit_msg.txt")
    with open(logfile, "w") as f:
        f.write("Add feature\n")

    provider = _GitProvider()
    success, error = provider.commit("my-feature", logfile, git_repo)

    assert success is True
    assert error is None

    # Verify branch was created
    branch_success, branch_name = provider.get_branch_name(git_repo)
    assert branch_success is True
    assert branch_name == "my-feature"


# === Tests for amend ===


def test_integration_amend_changes_message(git_repo: str) -> None:
    """amend changes the commit message."""
    provider = _GitProvider()
    success, error = provider.amend("Amended message", git_repo)

    assert success is True
    assert error is None

    # Verify message changed
    desc_success, desc = provider.get_description("HEAD", git_repo)
    assert desc_success is True
    assert desc is not None
    assert "Amended message" in desc


# === Tests for clean_workspace ===


def test_integration_clean_workspace_reverts(git_repo: str) -> None:
    """clean_workspace reverts tracked changes and removes untracked files."""
    # Modify tracked file
    with open(os.path.join(git_repo, "README.md"), "a") as f:
        f.write("dirty change\n")
    # Create untracked file
    with open(os.path.join(git_repo, "untracked.txt"), "w") as f:
        f.write("untracked\n")

    provider = _GitProvider()
    success, error = provider.clean_workspace(git_repo)

    assert success is True
    assert error is None

    # Verify workspace is clean
    has_changes_ok, changes = provider.has_local_changes(git_repo)
    assert has_changes_ok is True
    assert changes is None

    # Verify untracked file is gone
    assert not os.path.exists(os.path.join(git_repo, "untracked.txt"))


# === Tests for rename_branch ===


def test_integration_rename_branch(git_repo: str) -> None:
    """rename_branch renames the current branch."""
    provider = _GitProvider()
    success, error = provider.rename_branch("renamed-branch", git_repo)

    assert success is True
    assert error is None

    name_ok, name = provider.get_branch_name(git_repo)
    assert name_ok is True
    assert name == "renamed-branch"


# === Tests for apply_patch roundtrip ===


def test_integration_apply_patch_roundtrip(git_repo: str) -> None:
    """apply_patch applies a diff file generated from the same repo."""
    # Create a change and generate a raw diff (not via provider.diff which strips)
    readme = os.path.join(git_repo, "README.md")
    with open(readme, "a") as f:
        f.write("patch content\n")

    result = subprocess.run(
        ["git", "diff", "HEAD"],
        cwd=git_repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    diff_text = result.stdout  # raw output, not stripped

    # Save the diff to a file OUTSIDE the repo (clean_workspace removes untracked)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
        f.write(diff_text)
        patch_file = f.name

    provider = _GitProvider()
    try:
        # Revert the change
        clean_ok, _ = provider.clean_workspace(git_repo)
        assert clean_ok is True

        # Apply the patch
        apply_ok, error = provider.apply_patch(patch_file, git_repo)
        assert apply_ok is True
        assert error is None

        # Verify the change was applied
        with open(readme) as f:
            content = f.read()
        assert "patch content" in content
    finally:
        os.unlink(patch_file)


# === Tests for stash_and_clean ===


def test_integration_stash_and_clean(git_repo: str) -> None:
    """stash_and_clean saves diff to file and cleans workspace."""
    # Create a change
    with open(os.path.join(git_repo, "README.md"), "a") as f:
        f.write("stashed content\n")

    # Use a path OUTSIDE the repo (clean step removes untracked files inside)
    diff_fd, diff_file = tempfile.mkstemp(suffix=".diff")
    os.close(diff_fd)
    try:
        provider = _GitProvider()
        success, error = provider.stash_and_clean(diff_file, git_repo)

        assert success is True
        assert error is None

        # Diff file should exist with content
        assert os.path.exists(diff_file)
        with open(diff_file) as f:
            content = f.read()
        assert "stashed content" in content

        # Workspace should be clean
        has_changes_ok, changes = provider.has_local_changes(git_repo)
        assert has_changes_ok is True
        assert changes is None
    finally:
        os.unlink(diff_file)


# === Tests for archive and prune ===


def test_integration_archive(git_repo: str) -> None:
    """archive tags and deletes a branch."""
    # Create a branch to archive
    subprocess.run(
        ["git", "checkout", "-b", "to-archive"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )
    # Go back to original branch
    subprocess.run(
        ["git", "checkout", "-"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )

    provider = _GitProvider()
    success, error = provider.archive("to-archive", git_repo)

    assert success is True
    assert error is None

    # Tag should exist
    tag_check = subprocess.run(
        ["git", "tag", "-l", "archive/to-archive"],
        cwd=git_repo,
        capture_output=True,
        text=True,
    )
    assert "archive/to-archive" in tag_check.stdout


def test_integration_prune(git_repo: str) -> None:
    """prune deletes a branch."""
    # Create a branch to prune
    subprocess.run(
        ["git", "checkout", "-b", "to-prune"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "checkout", "-"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )

    provider = _GitProvider()
    success, error = provider.prune("to-prune", git_repo)

    assert success is True
    assert error is None

    # Branch should be gone
    branch_list = subprocess.run(
        ["git", "branch"],
        cwd=git_repo,
        capture_output=True,
        text=True,
    )
    assert "to-prune" not in branch_list.stdout
