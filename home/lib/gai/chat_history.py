"""Chat history management for gai agents.

This module provides functions to save and load conversation histories
from gai agent runs. Histories are stored in ~/.gai/chats/ with filenames
that encode the branch/workspace, workflow, optional agent name, and timestamp.
"""

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from shared_utils import run_shell_command


def _get_chats_directory() -> str:
    """Get the path to the chats directory (~/.gai/chats/)."""
    return os.path.expanduser("~/.gai/chats")


def _ensure_chats_directory() -> None:
    """Ensure the chats directory exists."""
    chats_dir = _get_chats_directory()
    Path(chats_dir).mkdir(parents=True, exist_ok=True)


def _get_branch_or_workspace_name() -> str:
    """Get the current branch name or workspace name."""
    result = run_shell_command("branch_or_workspace_name", capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get branch_or_workspace_name: {result.stderr}")
    return result.stdout.strip()


def _generate_timestamp() -> str:
    """Generate a timestamp in YYmmdd_HHMMSS format (2-digit year with underscore)."""
    eastern = ZoneInfo("America/New_York")
    # Use %y for 2-digit year
    return datetime.now(eastern).strftime("%y%m%d_%H%M%S")


def _generate_chat_filename(
    workflow: str,
    agent: str | None = None,
    branch_or_workspace: str | None = None,
    timestamp: str | None = None,
) -> str:
    """Generate a chat history filename.

    Args:
        workflow: The workflow name (e.g., 'run', 'rerun', 'fix-tests')
        agent: Optional agent name within a multi-agent workflow
        branch_or_workspace: Optional branch/workspace name (defaults to current)
        timestamp: Optional timestamp (defaults to current time)

    Returns:
        The full path to the chat history file (without extension for basename usage)
    """
    if branch_or_workspace is None:
        branch_or_workspace = _get_branch_or_workspace_name()
    if timestamp is None:
        timestamp = _generate_timestamp()

    # Build filename parts
    parts = [branch_or_workspace, workflow]
    if agent is not None:
        parts.append(agent)
    parts.append(timestamp)

    # Join with dashes
    basename = "-".join(parts)

    return basename


def _get_chat_file_path(basename: str) -> str:
    """Get the full path to a chat history file.

    Args:
        basename: The basename of the chat file (with or without .md extension)

    Returns:
        The full path to the chat file
    """
    chats_dir = _get_chats_directory()
    if not basename.endswith(".md"):
        basename = f"{basename}.md"
    return os.path.join(chats_dir, basename)


def save_chat_history(
    prompt: str,
    response: str,
    workflow: str,
    agent: str | None = None,
    previous_history: str | None = None,
    timestamp: str | None = None,
) -> str:
    """Save a chat history to a file.

    Args:
        prompt: The prompt sent to the agent
        response: The response from the agent
        workflow: The workflow name
        agent: Optional agent name for multi-agent workflows
        previous_history: Optional previous conversation history to prepend
        timestamp: Optional timestamp for filename (YYmmdd_HHMMSS format)

    Returns:
        The full path to the saved chat history file
    """
    _ensure_chats_directory()

    basename = _generate_chat_filename(workflow, agent, timestamp=timestamp)
    file_path = _get_chat_file_path(basename)

    eastern = ZoneInfo("America/New_York")
    display_timestamp = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S EST")

    # Build content
    content_parts = []

    # Add header
    content_parts.append(f"# Chat History - {workflow}")
    if agent:
        content_parts.append(f" ({agent})")
    content_parts.append(f"\n\n**Timestamp:** {display_timestamp}\n")

    # Add previous history if present
    if previous_history:
        content_parts.append("\n## Previous Conversation\n\n")
        content_parts.append(previous_history)
        content_parts.append("\n\n---\n")

    # Add current prompt and response
    content_parts.append("\n## Prompt\n\n")
    content_parts.append(prompt)
    content_parts.append("\n\n## Response\n\n")
    content_parts.append(response)
    content_parts.append("\n")

    content = "".join(content_parts)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Return path with ~ for home directory
    return file_path.replace(str(Path.home()), "~")


def _increment_markdown_headings(content: str) -> str:
    """Increment all markdown heading levels by one.

    Args:
        content: The markdown content to process

    Returns:
        Content with all heading levels incremented (# -> ##, ## -> ###, etc.)
    """
    lines = content.split("\n")
    result_lines = []

    for line in lines:
        # Check if line starts with markdown heading
        if line.startswith("#"):
            # Add one more # to increment the heading level
            result_lines.append("#" + line)
        else:
            result_lines.append(line)

    return "\n".join(result_lines)


def load_chat_history(file_ref: str, increment_headings: bool = False) -> str:
    """Load a chat history from a file.

    Args:
        file_ref: Either a basename (e.g., 'foobar_run_251128104155')
                  or a full path (e.g., '~/.gai/chats/foobar_run_251128104155.md')
        increment_headings: If True, increment all markdown heading levels by one

    Returns:
        The content of the chat history file
    """
    # Handle full paths
    if file_ref.startswith("/") or file_ref.startswith("~"):
        file_path = os.path.expanduser(file_ref)
    else:
        # Treat as basename
        file_path = _get_chat_file_path(file_ref)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Chat history file not found: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    if increment_headings:
        content = _increment_markdown_headings(content)

    return content


def list_chat_histories() -> list[str]:
    """List all available chat history basenames.

    Returns:
        A list of chat history basenames (without .md extension),
        sorted by timestamp (most recent first)
    """
    chats_dir = _get_chats_directory()

    if not os.path.exists(chats_dir):
        return []

    # Get all .md files
    files = []
    for filename in os.listdir(chats_dir):
        if filename.endswith(".md"):
            # Remove .md extension for basename
            basename = filename[:-3]
            files.append(basename)

    # Sort by modification time (most recent first)
    files.sort(
        key=lambda x: os.path.getmtime(_get_chat_file_path(x)),
        reverse=True,
    )

    return files
