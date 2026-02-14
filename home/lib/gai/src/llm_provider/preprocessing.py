"""Prompt preprocessing pipeline.

Extracts the preprocessing steps from the old GeminiCommandWrapper.invoke()
into a standalone function. The preprocessing functions themselves remain in
their original modules (xprompt, gemini_wrapper.file_references).
"""

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


def preprocess_prompt(prompt: str, *, is_home_mode: bool = False) -> str:
    """Apply the full preprocessing pipeline to a raw prompt.

    Steps:
        1. Expand ``#name`` xprompt references.
        2. Expand ``$(cmd)`` command substitutions.
        3. Expand ``@path`` file references (copy absolute/tilde paths).
        4. Render Jinja2 templates (after all expansions).
        5. Format with prettier for consistent markdown.
        6. Strip HTML/markdown comments.

    Args:
        prompt: The raw prompt text.
        is_home_mode: If True, skip file copying for ``@`` file references.

    Returns:
        The fully preprocessed prompt.
    """
    # 1. Process xprompt references (#name patterns)
    prompt = process_xprompt_references(prompt)

    # 2. Process command substitution ($(cmd) patterns)
    prompt = process_command_substitution(prompt)

    # 3. Process file references (@path patterns)
    prompt = process_file_references(prompt, is_home_mode=is_home_mode)

    # 4. Process Jinja2 templates AFTER all expansions
    if is_jinja2_template(prompt):
        prompt = render_toplevel_jinja2(prompt)

    # 5. Format with prettier for consistent markdown
    prompt = format_with_prettier(prompt)

    # 6. Strip HTML/markdown comments
    prompt = strip_html_comments(prompt)

    return prompt
