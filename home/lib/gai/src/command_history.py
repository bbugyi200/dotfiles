"""Command history storage and retrieval for background commands."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from gai_utils import generate_timestamp

_COMMAND_HISTORY_FILE = Path.home() / ".gai" / "command_history.json"

# Display settings
_COMMAND_PREVIEW_LENGTH = 50


@dataclass
class CommandEntry:
    """A single command history entry."""

    command: str  # The shell command
    project: str  # Project name
    cl_name: str | None  # CL/ChangeSpec name (None if project-only)
    timestamp: str  # When first created (YYMMDD_HHMMSS)
    last_used: str  # When last used


def _load_command_history() -> list[CommandEntry]:
    """Load command history from disk.

    Returns:
        List of CommandEntry objects, or empty list if file doesn't exist.
    """
    if not _COMMAND_HISTORY_FILE.exists():
        return []

    try:
        with open(_COMMAND_HISTORY_FILE, encoding="utf-8") as f:
            data = json.load(f)

        commands = data.get("commands", [])
        return [
            CommandEntry(
                command=c["command"],
                project=c["project"],
                cl_name=c.get("cl_name"),  # May be None
                timestamp=c["timestamp"],
                last_used=c["last_used"],
            )
            for c in commands
            if isinstance(c, dict)
            and "command" in c
            and "project" in c
            and "timestamp" in c
            and "last_used" in c
        ]
    except (OSError, json.JSONDecodeError, KeyError):
        return []


def _save_command_history(commands: list[CommandEntry]) -> bool:
    """Save command history to disk.

    Args:
        commands: List of CommandEntry objects to save.

    Returns:
        True if saved successfully, False otherwise.
    """
    try:
        _COMMAND_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {"commands": [asdict(c) for c in commands]}
        with open(_COMMAND_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except OSError:
        return False


def add_or_update_command(
    command: str,
    project: str,
    cl_name: str | None,
) -> None:
    """Add a new command or update an existing command's last_used timestamp.

    Deduplication key is (command, project, cl_name). If a matching entry exists,
    it is deleted and replaced with a new entry at the end (most recent).

    Args:
        command: The shell command.
        project: Project name.
        cl_name: Optional CL/ChangeSpec name.
    """
    commands = _load_command_history()
    current_timestamp = generate_timestamp()

    # Remove existing entry with same key (command, project, cl_name)
    commands = [
        c
        for c in commands
        if not (c.command == command and c.project == project and c.cl_name == cl_name)
    ]

    # Add new entry at the end
    new_entry = CommandEntry(
        command=command,
        project=project,
        cl_name=cl_name,
        timestamp=current_timestamp,
        last_used=current_timestamp,
    )
    commands.append(new_entry)
    _save_command_history(commands)


def _format_command_for_display(
    entry: CommandEntry,
    current_cl: str | None,
    current_project: str | None,
    max_context_len: int,
) -> str:
    """Format a command entry for display.

    Args:
        entry: The command entry to format.
        current_cl: The current CL name (for marking).
        current_project: The current project name (for secondary marking).
        max_context_len: Maximum context (project/CL) length for padding.

    Returns:
        Formatted display string.
    """
    # Determine marker based on match priority
    if entry.cl_name is not None and entry.cl_name == current_cl:
        marker = "*"
    elif entry.project == current_project:
        marker = "~"
    else:
        marker = " "

    # Build context string: "project/cl_name" or just "project"
    if entry.cl_name:
        context = f"{entry.project}/{entry.cl_name}"
    else:
        context = entry.project

    # Pad context for alignment
    context_padded = context.ljust(max_context_len)

    # Format command: truncate if needed
    preview = entry.command
    if len(preview) > _COMMAND_PREVIEW_LENGTH:
        preview = preview[:_COMMAND_PREVIEW_LENGTH] + "..."

    return f"{marker} {context_padded} | {preview}"


def get_commands_for_display(
    current_cl: str | None = None,
    current_project: str | None = None,
) -> list[tuple[str, CommandEntry]]:
    """Get commands formatted for display.

    Commands are sorted in 3 tiers:
    1. Commands matching current CL (marked with '*')
    2. Commands matching current project but different CL (marked with '~')
    3. All other commands (no marker)

    Within each tier, commands are sorted by last_used timestamp (most recent first).

    Args:
        current_cl: The current CL/ChangeSpec name. If None, no CL matching.
        current_project: The current project name. If None, no project matching.

    Returns:
        List of (display_string, CommandEntry) tuples sorted for display.
    """
    commands = _load_command_history()

    if not commands:
        return []

    # Calculate max context length for alignment
    max_context_len = max(
        len(f"{c.project}/{c.cl_name}" if c.cl_name else c.project) for c in commands
    )

    # Three-way sort: CL match (0), project match (1), other (2)
    def _sort_key(c: CommandEntry) -> int:
        if c.cl_name is not None and c.cl_name == current_cl:
            return 0
        if c.project == current_project:
            return 1
        return 2

    # Sort by last_used descending first, then stable sort by group
    commands.sort(key=lambda c: c.last_used, reverse=True)
    commands.sort(key=_sort_key)

    return [
        (
            _format_command_for_display(
                c, current_cl, current_project, max_context_len
            ),
            c,
        )
        for c in commands
    ]
