"""Editor utilities for commit message editing."""

import os
import subprocess
import tempfile

from rich_utils import print_status


def _get_editor() -> str:
    """Get the editor to use for commit messages.

    Returns:
        The editor command to use. Checks $EDITOR first, then falls back to
        nvim if available, otherwise vim.
    """
    # Check EDITOR environment variable first
    editor = os.environ.get("EDITOR")
    if editor:
        return editor

    # Fall back to nvim if it exists
    try:
        result = subprocess.run(
            ["which", "nvim"], capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            return "nvim"
    except Exception:
        pass

    # Default to vim
    return "vim"


def open_editor_for_commit_message() -> str | None:
    """Open the user's editor with a temporary file for the commit message.

    Returns:
        Path to the temporary file containing the commit message, or None if
        the user didn't write anything or the editor failed.
    """
    # Create a temporary file that won't be automatically deleted
    fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix="gai_commit_")
    os.close(fd)

    editor = _get_editor()

    try:
        # Open editor with the temporary file
        result = subprocess.run([editor, temp_path], check=False)
        if result.returncode != 0:
            print_status("Editor exited with non-zero status.", "error")
            os.unlink(temp_path)
            return None

        # Check if the user wrote anything
        with open(temp_path, encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            print_status("No commit message provided. Aborting.", "error")
            os.unlink(temp_path)
            return None

        return temp_path

    except Exception as e:
        print_status(f"Failed to open editor: {e}", "error")
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        return None
