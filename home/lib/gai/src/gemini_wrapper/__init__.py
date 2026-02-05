"""Gemini wrapper module for invoking Gemini agents."""

from xprompt import (
    is_jinja2_template,
    process_xprompt_references,
    render_toplevel_jinja2,
)

from .file_references import (
    format_with_prettier,
    process_command_substitution,
    strip_html_comments,
    validate_file_references,
)
from .wrapper import GeminiCommandWrapper, invoke_agent

__all__ = [
    "GeminiCommandWrapper",
    "format_with_prettier",
    "invoke_agent",
    "is_jinja2_template",
    "process_command_substitution",
    "process_xprompt_references",
    "render_toplevel_jinja2",
    "strip_html_comments",
    "validate_file_references",
]
