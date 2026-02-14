"""Preprocessing pipeline for LLM prompts."""

from gemini_wrapper.file_references import (
    format_with_prettier,
    process_command_substitution,
    process_file_references,
    strip_html_comments,
)
from xprompt import (
    is_jinja2_template,
    process_xprompt_references,
    render_toplevel_jinja2,
)


def preprocess_prompt(query: str, *, is_home_mode: bool = False) -> str:
    """Run the standard 6-step preprocessing pipeline on a prompt.

    Steps:
        1. Expand xprompt #name references
        2. Expand $(cmd) command substitutions
        3. Process @file references (copy absolute paths to context dir)
        4. Render Jinja2 templates (if detected)
        5. Format with prettier for consistent markdown
        6. Strip HTML/markdown comments

    Args:
        query: The raw prompt text.
        is_home_mode: If True, skip file copying for @ file references.

    Returns:
        The fully preprocessed prompt text.
    """
    query = process_xprompt_references(query)
    query = process_command_substitution(query)
    query = process_file_references(query, is_home_mode=is_home_mode)
    if is_jinja2_template(query):
        query = render_toplevel_jinja2(query)
    query = format_with_prettier(query)
    query = strip_html_comments(query)
    return query
