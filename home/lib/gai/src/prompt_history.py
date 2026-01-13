"""Prompt history storage and retrieval for gai run commands."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from gai_utils import generate_timestamp
from shared_utils import run_shell_command

_PROMPT_HISTORY_FILE = Path.home() / ".gai" / "prompt_history.json"

# Display settings for fzf
_PROMPT_PREVIEW_LENGTH = 60


@dataclass
class PromptEntry:
    """A single prompt history entry."""

    text: str
    branch_or_workspace: str
    timestamp: str
    last_used: str
    workspace: str = ""  # Workspace name, default empty for backward compatibility


def _get_current_branch_or_workspace() -> str:
    """Get the current branch or workspace name.

    Returns:
        The branch or workspace name, or "unknown" if it cannot be determined.
    """
    result = run_shell_command("branch_or_workspace_name", capture_output=True)
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def _get_workspace_name() -> str:
    """Get the current workspace name.

    Returns:
        The workspace name, or "unknown" if it cannot be determined.
    """
    result = run_shell_command("workspace_name", capture_output=True)
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def _load_prompt_history() -> list[PromptEntry]:
    """Load prompt history from disk.

    Returns:
        List of PromptEntry objects, or empty list if file doesn't exist.
    """
    if not _PROMPT_HISTORY_FILE.exists():
        return []

    try:
        with open(_PROMPT_HISTORY_FILE, encoding="utf-8") as f:
            data = json.load(f)

        prompts = data.get("prompts", [])
        return [
            PromptEntry(
                text=p["text"],
                branch_or_workspace=p["branch_or_workspace"],
                timestamp=p["timestamp"],
                last_used=p["last_used"],
                workspace=p.get("workspace", ""),  # Default empty for old entries
            )
            for p in prompts
            if isinstance(p, dict)
            and "text" in p
            and "branch_or_workspace" in p
            and "timestamp" in p
            and "last_used" in p
        ]
    except (OSError, json.JSONDecodeError, KeyError):
        return []


def _save_prompt_history(prompts: list[PromptEntry]) -> bool:
    """Save prompt history to disk.

    Args:
        prompts: List of PromptEntry objects to save.

    Returns:
        True if saved successfully, False otherwise.
    """
    try:
        _PROMPT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {"prompts": [asdict(p) for p in prompts]}
        with open(_PROMPT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except OSError:
        return False


def add_or_update_prompt(text: str, *, project_name: str | None = None) -> None:
    """Add a new prompt or update an existing prompt's last_used timestamp.

    If a prompt with the same text already exists, updates its last_used timestamp.
    Otherwise, adds a new entry.

    Args:
        text: The prompt text to add or update.
        project_name: Optional project name to use for the workspace field.
            If provided, uses this instead of detecting via shell command.
    """
    prompts = _load_prompt_history()
    current_timestamp = generate_timestamp()
    current_branch = _get_current_branch_or_workspace()
    current_workspace = project_name if project_name else _get_workspace_name()

    # Check if prompt already exists (by exact text match)
    for prompt in prompts:
        if prompt.text == text:
            # Update existing prompt's last_used timestamp
            prompt.last_used = current_timestamp
            _save_prompt_history(prompts)
            return

    # Add new prompt
    new_entry = PromptEntry(
        text=text,
        branch_or_workspace=current_branch,
        timestamp=current_timestamp,
        last_used=current_timestamp,
        workspace=current_workspace,
    )
    prompts.append(new_entry)
    _save_prompt_history(prompts)


def _format_prompt_for_display(
    entry: PromptEntry,
    current_branch: str,
    current_workspace: str,
    max_branch_len: int,
) -> str:
    """Format a prompt entry for fzf display.

    Args:
        entry: The prompt entry to format.
        current_branch: The current branch/workspace name (for marking).
        current_workspace: The current workspace name (for secondary marking).
        max_branch_len: Maximum branch name length for padding.

    Returns:
        Formatted display string.
    """
    # Mark current branch with asterisk, workspace with tilde
    if entry.branch_or_workspace == current_branch:
        marker = "*"
    elif entry.workspace == current_workspace:
        marker = "~"
    else:
        marker = " "

    # Pad branch name for alignment
    branch = entry.branch_or_workspace.ljust(max_branch_len)

    # Format prompt text: replace newlines with spaces, truncate if needed
    preview = entry.text.replace("\n", " ").replace("\r", " ")
    if len(preview) > _PROMPT_PREVIEW_LENGTH:
        preview = preview[:_PROMPT_PREVIEW_LENGTH] + "..."

    return f"{marker} {branch} | {preview}"


def get_prompts_for_fzf(
    current_branch: str | None = None,
    current_workspace: str | None = None,
) -> list[tuple[str, PromptEntry]]:
    """Get prompts formatted for fzf display.

    Prompts from the current branch are marked with '*' and sorted to the top.
    Prompts from the current workspace (but different branch) are marked with '~'
    and sorted second. All prompts are sorted by last_used timestamp within groups.

    Args:
        current_branch: The current branch/workspace name. If None, will be detected.
        current_workspace: The current workspace name. If None, will be detected.

    Returns:
        List of (display_string, PromptEntry) tuples sorted for fzf display.
    """
    if current_branch is None:
        current_branch = _get_current_branch_or_workspace()
    if current_workspace is None:
        current_workspace = _get_workspace_name()

    prompts = _load_prompt_history()

    if not prompts:
        return []

    # Calculate max branch name length for alignment
    max_branch_len = max(len(p.branch_or_workspace) for p in prompts)

    # Three-way sort: branch match (0), workspace match (1), other (2)
    def _sort_key(p: PromptEntry) -> int:
        if p.branch_or_workspace == current_branch:
            return 0
        if p.workspace == current_workspace:
            return 1
        return 2

    # Sort by last_used descending first, then stable sort by group
    prompts.sort(key=lambda p: p.last_used, reverse=True)
    prompts.sort(key=_sort_key)

    return [
        (
            _format_prompt_for_display(
                p, current_branch, current_workspace, max_branch_len
            ),
            p,
        )
        for p in prompts
    ]
