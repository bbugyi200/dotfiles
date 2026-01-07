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
class _PromptEntry:
    """A single prompt history entry."""

    text: str
    branch_or_workspace: str
    timestamp: str
    last_used: str


def _get_current_branch_or_workspace() -> str:
    """Get the current branch or workspace name.

    Returns:
        The branch or workspace name, or "unknown" if it cannot be determined.
    """
    result = run_shell_command("branch_or_workspace_name", capture_output=True)
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def _load_prompt_history() -> list[_PromptEntry]:
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
            _PromptEntry(
                text=p["text"],
                branch_or_workspace=p["branch_or_workspace"],
                timestamp=p["timestamp"],
                last_used=p["last_used"],
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


def _save_prompt_history(prompts: list[_PromptEntry]) -> bool:
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


def add_or_update_prompt(text: str) -> None:
    """Add a new prompt or update an existing prompt's last_used timestamp.

    If a prompt with the same text already exists, updates its last_used timestamp.
    Otherwise, adds a new entry.

    Args:
        text: The prompt text to add or update.
    """
    prompts = _load_prompt_history()
    current_timestamp = generate_timestamp()
    current_branch = _get_current_branch_or_workspace()

    # Check if prompt already exists (by exact text match)
    for prompt in prompts:
        if prompt.text == text:
            # Update existing prompt's last_used timestamp
            prompt.last_used = current_timestamp
            _save_prompt_history(prompts)
            return

    # Add new prompt
    new_entry = _PromptEntry(
        text=text,
        branch_or_workspace=current_branch,
        timestamp=current_timestamp,
        last_used=current_timestamp,
    )
    prompts.append(new_entry)
    _save_prompt_history(prompts)


def _format_prompt_for_display(
    entry: _PromptEntry,
    current_branch: str,
    max_branch_len: int,
) -> str:
    """Format a prompt entry for fzf display.

    Args:
        entry: The prompt entry to format.
        current_branch: The current branch/workspace name (for marking).
        max_branch_len: Maximum branch name length for padding.

    Returns:
        Formatted display string.
    """
    # Mark current branch with asterisk
    marker = "*" if entry.branch_or_workspace == current_branch else " "

    # Pad branch name for alignment
    branch = entry.branch_or_workspace.ljust(max_branch_len)

    # Format prompt text: replace newlines with spaces, truncate if needed
    preview = entry.text.replace("\n", " ").replace("\r", " ")
    if len(preview) > _PROMPT_PREVIEW_LENGTH:
        preview = preview[:_PROMPT_PREVIEW_LENGTH] + "..."

    return f"{marker} {branch} | {preview}"


def get_prompts_for_fzf(
    current_branch: str | None = None,
) -> list[tuple[str, _PromptEntry]]:
    """Get prompts formatted for fzf display.

    Prompts from the current branch are marked with '*' and sorted to the top.
    All prompts are sorted by last_used timestamp (most recent first).

    Args:
        current_branch: The current branch/workspace name. If None, will be detected.

    Returns:
        List of (display_string, PromptEntry) tuples sorted for fzf display.
    """
    if current_branch is None:
        current_branch = _get_current_branch_or_workspace()

    prompts = _load_prompt_history()

    if not prompts:
        return []

    # Calculate max branch name length for alignment
    max_branch_len = max(len(p.branch_or_workspace) for p in prompts)

    # Sort by last_used descending first, then stable sort by branch match
    prompts.sort(key=lambda p: p.last_used, reverse=True)
    prompts.sort(key=lambda p: 0 if p.branch_or_workspace == current_branch else 1)

    return [
        (_format_prompt_for_display(p, current_branch, max_branch_len), p)
        for p in prompts
    ]
