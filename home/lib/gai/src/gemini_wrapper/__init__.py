"""Gemini wrapper module for invoking Gemini agents."""

from .file_references import (
    format_with_prettier,
    process_command_substitution,
    process_xcmd_references,
    validate_file_references,
)
from .snippet_processor import process_snippet_references
from .wrapper import GeminiCommandWrapper, invoke_agent

__all__ = [
    "GeminiCommandWrapper",
    "format_with_prettier",
    "invoke_agent",
    "process_command_substitution",
    "process_snippet_references",
    "process_xcmd_references",
    "validate_file_references",
]
