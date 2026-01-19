"""Core utility functions shared across gai modules."""

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from ace.changespec import ChangeSpec

# Standard timezone used throughout the codebase
EASTERN_TZ = ZoneInfo("America/New_York")


def run_shell_command(
    cmd: str, capture_output: bool = True
) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    return subprocess.run(
        cmd,
        shell=True,
        capture_output=capture_output,
        text=True,
    )


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


def has_suffix(name: str) -> bool:
    """Check if a ChangeSpec name has a __<N> suffix.

    Args:
        name: ChangeSpec name to check

    Returns:
        True if name has __<N> suffix, False otherwise
    """
    return bool(re.match(r"^.+__\d+$", name))


def get_next_suffix_number(base_name: str, existing_names: set[str]) -> int:
    """Find the lowest positive integer N such that `<base_name>__<N>` doesn't exist.

    Args:
        base_name: The base name to append suffix to
        existing_names: Set of existing names to check for conflicts

    Returns:
        The lowest available suffix number
    """
    n = 1
    while f"{base_name}__{n}" in existing_names:
        n += 1
    return n


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

    try:
        return get_workspace_dir(changespec.project_basename)
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


def get_context_files(directory: str | None) -> list[str]:
    """Get list of context file paths (.md, .txt) from a directory.

    Scans the directory for .md and .txt files and returns their full paths.

    Args:
        directory: Path to context directory, or None.

    Returns:
        Sorted list of full paths to .md and .txt files.
        Returns empty list if directory is None or doesn't exist.
    """
    if not directory or not os.path.isdir(directory):
        return []

    try:
        return sorted(
            [
                os.path.join(directory, f)
                for f in os.listdir(directory)
                if f.endswith((".md", ".txt"))
            ]
        )
    except OSError:
        return []
