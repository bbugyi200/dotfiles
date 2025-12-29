"""Spec file handling functions for the split workflow."""

import os
import subprocess
import tempfile
from pathlib import Path

from rich_utils import print_status
from shared_utils import run_shell_command
from split_spec import parse_split_spec

from .utils import get_editor, get_splits_directory


def archive_spec_file(name: str, spec_content: str, timestamp: str) -> str:
    """Save spec file to ~/.gai/splits/<NAME>-<timestamp>.yml.

    Args:
        name: The CL name.
        spec_content: The YAML content of the spec.
        timestamp: The timestamp for the filename.

    Returns:
        The archive path with ~ for display.
    """
    splits_dir = get_splits_directory()
    Path(splits_dir).mkdir(parents=True, exist_ok=True)

    archive_path = os.path.join(splits_dir, f"{name}-{timestamp}.yml")
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(spec_content)

    # Return path with ~ for display
    return archive_path.replace(str(Path.home()), "~")


def create_and_edit_spec(name: str, timestamp: str) -> tuple[str, str] | None:
    """Create empty spec file, open in editor, and archive.

    Args:
        name: The CL name for the spec.
        timestamp: The timestamp for archiving.

    Returns:
        Tuple of (spec_content, archive_path) or None if user cancelled.
    """
    # Create temp file for editing
    fd, temp_path = tempfile.mkstemp(suffix=".yml", prefix=f"{name}_split_")
    os.close(fd)

    # Get workspace name prefix
    ws_result = run_shell_command("workspace_name", capture_output=True)
    ws_prefix = f"{ws_result.stdout.strip()}_" if ws_result.returncode == 0 else ""

    # Write empty template
    template = f"""- name: {ws_prefix}
  description:

- name: {ws_prefix}
  description:
  parent: {ws_prefix}
"""

    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(template)

    # Open in editor
    editor = get_editor()
    subprocess.run([editor, temp_path], check=False)

    # Check if user saved content
    with open(temp_path, encoding="utf-8") as f:
        content = f.read()

    # Clean up temp file
    os.unlink(temp_path)

    # Check if content is essentially empty
    content_stripped = content.strip()
    if not content_stripped or content_stripped == template.strip():
        return None

    # Try to parse to validate
    try:
        parse_split_spec(content)
    except ValueError as e:
        print_status(f"Invalid SplitSpec: {e}", "error")
        return None

    # Archive the spec file
    archive_path = archive_spec_file(name, content, timestamp)

    return (content, archive_path)


def load_and_archive_spec(name: str, spec_path: str, timestamp: str) -> tuple[str, str]:
    """Load existing spec file and archive it.

    Args:
        name: The CL name.
        spec_path: Path to the existing spec file.
        timestamp: The timestamp for archiving.

    Returns:
        Tuple of (spec_content, archive_path).
    """
    with open(spec_path, encoding="utf-8") as f:
        content = f.read()

    archive_path = archive_spec_file(name, content, timestamp)
    return (content, archive_path)


def edit_spec_content(content: str, name: str) -> str | None:
    """Open spec content in editor for user modification.

    Args:
        content: The YAML content to edit.
        name: The CL name for temp file naming.

    Returns:
        The edited content, or None if cancelled.
    """
    # Create temp file for editing
    fd, temp_path = tempfile.mkstemp(suffix=".yml", prefix=f"{name}_split_")
    os.close(fd)

    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Open in editor
    editor = get_editor()
    subprocess.run([editor, temp_path], check=False)

    # Read edited content
    with open(temp_path, encoding="utf-8") as f:
        edited_content = f.read()

    # Clean up temp file
    os.unlink(temp_path)

    # Check if content is essentially empty
    if not edited_content.strip():
        return None

    return edited_content
