"""File locking for ChangeSpec files to prevent race conditions."""

import fcntl
import os
import subprocess
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

GAI_DIR = Path.home() / ".gai"


class LockTimeoutError(Exception):
    """Raised when file lock acquisition times out."""

    def __init__(self, lock_file: str, timeout: float) -> None:
        self.lock_file = lock_file
        self.timeout = timeout
        super().__init__(f"Timeout waiting for lock on {lock_file} after {timeout}s")


def _ensure_gai_git_repo() -> None:
    """Ensure ~/.gai is a git repository with .gitignore."""
    git_dir = GAI_DIR / ".git"
    if not git_dir.exists():
        subprocess.run(
            ["git", "init"],
            cwd=str(GAI_DIR),
            capture_output=True,
            check=True,
        )
        # Create .gitignore
        gitignore = GAI_DIR / ".gitignore"
        gitignore.write_text(
            "# Lock files\n*.lock\n\n# Temp files from atomic writes\n.tmp_*\n"
        )


def _git_commit_changespec(project_file: str, commit_message: str) -> None:
    """Stage and commit changes to the project file.

    Only commits if the file is inside ~/.gai directory.
    """
    # Only commit files inside ~/.gai
    try:
        project_path = Path(project_file).resolve()
        gai_path = GAI_DIR.resolve()
        if not str(project_path).startswith(str(gai_path)):
            return
    except (OSError, ValueError):
        return

    _ensure_gai_git_repo()
    # Stage the specific file
    subprocess.run(
        ["git", "add", project_file],
        cwd=str(GAI_DIR),
        capture_output=True,
        check=True,
    )
    # Commit (don't fail if nothing to commit)
    subprocess.run(
        ["git", "commit", "-m", commit_message, "--", project_file],
        cwd=str(GAI_DIR),
        capture_output=True,
        check=False,
    )


@contextmanager
def changespec_lock(
    project_file: str,
    exclusive: bool = True,
    timeout: float = 30.0,
    poll_interval: float = 0.1,
) -> Iterator[None]:
    """Context manager for locking a ChangeSpec file.

    Uses fcntl.flock() for advisory locking. All processes must cooperate
    by using this lock for exclusive access to be effective.

    Args:
        project_file: Path to the .gp file to lock.
        exclusive: If True (default), acquire exclusive write lock.
                  If False, acquire shared read lock.
        timeout: Maximum seconds to wait for lock (default 30).
        poll_interval: Seconds between lock acquisition attempts (default 0.1).

    Raises:
        LockTimeoutError: If lock cannot be acquired within timeout.

    Example:
        with changespec_lock(project_file):
            content = Path(project_file).read_text()
            # ... modify content ...
            write_changespec_atomic(project_file, content, "Update XYZ")
    """
    lock_file = f"{project_file}.lock"

    # Create lock file directory if needed
    lock_dir = os.path.dirname(lock_file)
    if lock_dir and not os.path.exists(lock_dir):
        os.makedirs(lock_dir, exist_ok=True)

    # Open lock file (create if needed)
    fd = os.open(lock_file, os.O_RDWR | os.O_CREAT, 0o644)
    lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH

    try:
        start = time.monotonic()
        while True:
            try:
                fcntl.flock(fd, lock_type | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() - start >= timeout:
                    os.close(fd)
                    raise LockTimeoutError(lock_file, timeout) from None
                time.sleep(poll_interval)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def write_changespec_atomic(
    project_file: str,
    content: str,
    commit_message: str,
) -> None:
    """Write content to a ChangeSpec file atomically and commit to git.

    This function should be called WHILE holding a lock on the file.
    It handles the temp file + os.replace() pattern and commits to git.

    Args:
        project_file: Path to the .gp file.
        content: The full file content to write.
        commit_message: Git commit message describing the change.
    """
    project_dir = os.path.dirname(project_file)
    fd, temp_path = tempfile.mkstemp(dir=project_dir, prefix=".tmp_", suffix=".gp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(temp_path, project_file)
        # Commit the change while still holding lock
        _git_commit_changespec(project_file, commit_message)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
