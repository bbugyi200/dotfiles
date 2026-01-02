"""Core utility functions shared across gai modules."""

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from ace.changespec import ChangeSpec

# Standard timezone used throughout the codebase
EASTERN_TZ = ZoneInfo("America/New_York")


def generate_timestamp() -> str:
    """Generate a timestamp in YYmmdd_HHMMSS format (Eastern timezone).

    Returns:
        Timestamp string like "251227_143052"
    """
    return datetime.now(EASTERN_TZ).strftime("%y%m%d_%H%M%S")


def get_gai_directory(subdir: str) -> str:
    """Get the path to a subdirectory under ~/.gai/.

    Args:
        subdir: The subdirectory name (e.g., "hooks", "diffs", "chats")

    Returns:
        Full path like "/home/user/.gai/hooks"
    """
    return os.path.expanduser(f"~/.gai/{subdir}")


def ensure_gai_directory(subdir: str) -> str:
    """Ensure a ~/.gai subdirectory exists and return its path.

    Args:
        subdir: The subdirectory name (e.g., "hooks", "diffs", "chats")

    Returns:
        Full path to the created/existing directory
    """
    dir_path = get_gai_directory(subdir)
    Path(dir_path).mkdir(parents=True, exist_ok=True)
    return dir_path


def make_safe_filename(name: str) -> str:
    """Convert a string to a safe filename by replacing non-alphanumeric chars.

    Args:
        name: The string to convert

    Returns:
        Safe filename with only alphanumeric chars and underscores
    """
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def strip_reverted_suffix(name: str) -> str:
    """Remove the __<N> suffix from a reverted ChangeSpec name.

    Args:
        name: ChangeSpec name (e.g., "foobar_feature__2")

    Returns:
        Name without the suffix (e.g., "foobar_feature")
    """
    match = re.match(r"^(.+)__\d+$", name)
    return match.group(1) if match else name


def shorten_path(path: str) -> str:
    """Shorten a file path by replacing home directory with ~.

    Args:
        path: Full file path

    Returns:
        Path with home directory replaced by ~
    """
    return path.replace(str(Path.home()), "~")


def get_workspace_directory_for_changespec(changespec: "ChangeSpec") -> str | None:
    """Get the workspace directory for a ChangeSpec.

    Args:
        changespec: The ChangeSpec to get workspace directory for

    Returns:
        The workspace directory path, or None if not found
    """
    from running_field import get_workspace_directory as get_workspace_dir

    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]
    try:
        return get_workspace_dir(project_basename)
    except RuntimeError:
        return None


def strip_hook_prefix(hook_command: str) -> str:
    """Strip the '!' and '$' prefixes from a hook command if present.

    Prefixes:
    - '!' indicates FAILED status lines should auto-append error suffix
    - '$' indicates the hook should not run for proposal HISTORY entries

    Args:
        hook_command: The hook command string.

    Returns:
        The command with all prefixes stripped.
    """
    return hook_command.lstrip("!$")


@contextmanager
def _working_directory(target_dir: str) -> Iterator[None]:
    """Context manager that temporarily changes the working directory.

    NOTE: This is private for now since existing try/finally blocks are
    too complex to safely refactor. Available for new code to use.

    Args:
        target_dir: Directory to change to.

    Yields:
        None

    Example:
        with _working_directory('/path/to/workspace'):
            # do work here
        # original directory is restored
    """
    original_dir = os.getcwd()
    try:
        os.chdir(target_dir)
        yield
    finally:
        os.chdir(original_dir)
