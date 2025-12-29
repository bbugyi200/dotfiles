"""Core utility functions for xfile processing."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

# Command cache to avoid running the same command multiple times
_command_cache: dict[str, tuple[str | None, bool]] = {}


def clear_command_cache() -> None:
    """Clear the command cache."""
    global _command_cache
    _command_cache = {}


def execute_cached_command(cmd: str) -> tuple[str | None, bool]:
    """Execute a command with caching to avoid duplicate runs."""
    if cmd in _command_cache:
        return _command_cache[cmd]

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout
        success = result.returncode == 0
        _command_cache[cmd] = (output, success)
        return output, success
    except Exception:
        _command_cache[cmd] = (None, False)
        return None, False


def expand_braces(pattern: str) -> list[str]:
    """Expand brace patterns like {py,txt} into multiple patterns.

    Example: 'file.{py,txt}' -> ['file.py', 'file.txt']
    """
    brace_match = re.search(r"\{([^}]+)\}", pattern)
    if not brace_match:
        return [pattern]

    options = brace_match.group(1).split(",")
    expanded = []
    for option in options:
        new_pattern = (
            pattern[: brace_match.start()] + option + pattern[brace_match.end() :]
        )
        # Recursively expand in case there are more braces
        expanded.extend(expand_braces(new_pattern))

    return expanded


def process_command_substitution(filename: str) -> str:
    """Process command substitution in the filename (e.g., foo_$(echo bar))."""
    result = filename

    def _replace_cmd(match: re.Match[str]) -> str:
        cmd = match.group(1)
        output, success = execute_cached_command(cmd)
        if success and output:
            return output.strip()
        return ""

    result = re.sub(r"\$\(([^)]+)\)", _replace_cmd, result)
    return result


def get_global_xfiles_dir() -> Path:
    """Get the global xfiles directory path."""
    return Path.home() / ".local/share/nvim/codecompanion/user/xfiles"


def get_local_xfiles_dir() -> Path:
    """Get the local xfiles directory path."""
    return Path.cwd() / "xfiles"


def ensure_xfiles_dirs() -> None:
    """Ensure both global and local xfiles directories exist."""
    get_global_xfiles_dir().mkdir(parents=True, exist_ok=True)
    get_local_xfiles_dir().mkdir(parents=True, exist_ok=True)


def find_xfile(name: str) -> Path | None:
    """Find an xfile by name, checking local directory first, then global."""
    # Remove .txt extension if provided
    if name.endswith(".txt"):
        name = name[:-4]

    local_path = get_local_xfiles_dir() / f"{name}.txt"
    if local_path.exists():
        return local_path

    global_path = get_global_xfiles_dir() / f"{name}.txt"
    if global_path.exists():
        return global_path

    return None


def make_relative_to_home(path: Path) -> Path:
    """Convert absolute path to be relative to home directory with ~ prefix."""
    try:
        return Path("~") / path.relative_to(Path.home())
    except ValueError:
        return path


def format_output_path(path: Path, absolute: bool, cwd: Path) -> str:
    """Format a path for output based on the absolute flag."""
    if absolute:
        path_str = str(path)
    else:
        # Default: relative to cwd
        try:
            path_str = str(path.relative_to(cwd))
        except ValueError:
            # Path is outside cwd, return absolute path
            path_str = str(path)

    return path_str
