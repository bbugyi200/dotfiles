"""Editor utilities for prompt editing."""

import os
import subprocess
import tempfile


def _get_editor() -> str:
    """Get the editor to use for prompts.

    Returns:
        The editor command to use. Checks $EDITOR first, then falls back to
        nvim if available, otherwise vim.
    """
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

    return "vim"


def open_editor_for_prompt() -> str | None:
    """Open the user's editor with a blank file for writing a prompt.

    Returns:
        The prompt content, or None if the user didn't write anything
        or the editor failed.
    """
    fd, temp_path = tempfile.mkstemp(suffix=".md", prefix="gai_prompt_")
    os.close(fd)

    editor = _get_editor()

    try:
        result = subprocess.run([editor, temp_path], check=False)
        if result.returncode != 0:
            print("Editor exited with non-zero status.")
            os.unlink(temp_path)
            return None

        with open(temp_path, encoding="utf-8") as f:
            content = f.read().strip()

        os.unlink(temp_path)

        if not content:
            return None

        return content

    except Exception as e:
        print(f"Failed to open editor: {e}")
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        return None


def _open_editor_with_content(initial_content: str) -> str | None:
    """Open the user's editor with pre-filled content for editing.

    Args:
        initial_content: The content to pre-fill in the editor.

    Returns:
        The edited content, or None if the user left it empty or the editor failed.
    """
    fd, temp_path = tempfile.mkstemp(suffix=".md", prefix="gai_prompt_")

    # Write initial content to temp file
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(initial_content)

    editor = _get_editor()

    try:
        result = subprocess.run([editor, temp_path], check=False)
        if result.returncode != 0:
            print("Editor exited with non-zero status.")
            os.unlink(temp_path)
            return None

        with open(temp_path, encoding="utf-8") as f:
            content = f.read().strip()

        os.unlink(temp_path)

        if not content:
            return None

        return content

    except Exception as e:
        print(f"Failed to open editor: {e}")
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        return None


def show_prompt_history_picker() -> str | None:
    """Show fzf picker for prompt history, open editor, return edited prompt.

    Returns:
        The edited prompt content, or None if cancelled or no history.
    """
    return _show_prompt_history_picker_for_branch(sort_by=None)


def _show_prompt_history_picker_for_branch(
    sort_by: str | None = None,
    workspace: str | None = None,
) -> str | None:
    """Show fzf picker for prompt history, sorted by branch, open editor.

    Args:
        sort_by: Optional branch/CL name to prioritize in sorting.
            If None, uses current branch detection.
        workspace: Optional workspace/project name for secondary sorting.
            If None, uses current workspace detection.

    Returns:
        The edited prompt content, or None if cancelled or no history.
    """
    from prompt_history import get_prompts_for_fzf

    # Pass sort_by as current_branch and workspace for sorting
    items = get_prompts_for_fzf(current_branch=sort_by, current_workspace=workspace)

    if not items:
        print("No prompt history found. Run 'gai run \"your prompt\"' first.")
        return None

    # Check if fzf is available
    fzf_check = subprocess.run(
        ["which", "fzf"], capture_output=True, text=True, check=False
    )
    if fzf_check.returncode != 0:
        print("Error: fzf is not installed. Please install fzf to use prompt history.")
        return None

    # Build display lines for fzf
    display_lines = "\n".join(display for display, _ in items)

    # Run fzf with header showing sorting context
    if sort_by and workspace:
        header = f"* = {sort_by}, ~ = {workspace}"
    elif sort_by:
        header = f"* = {sort_by}"
    else:
        header = "* = current branch/workspace"
    cmd = [
        "fzf",
        "--prompt",
        "Select prompt> ",
        "--header",
        header,
    ]

    result = subprocess.run(
        cmd,
        input=display_lines,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        # User cancelled (Escape or Ctrl-C)
        return None

    selected_display = result.stdout.strip()
    if not selected_display:
        return None

    # Find the matching entry (strip display to handle padding whitespace)
    selected_entry = None
    for display, entry in items:
        if display.strip() == selected_display:
            selected_entry = entry
            break

    if selected_entry is None:
        return None

    # Open editor with selected prompt pre-filled
    return _open_editor_with_content(selected_entry.text)
