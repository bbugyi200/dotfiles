"""Gemini wrapper module for invoking Gemini agents."""

from .file_references import process_xfile_references, validate_file_references
from .snippet_processor import process_snippet_references
from .wrapper import GeminiCommandWrapper, invoke_agent

__all__ = [
    "GeminiCommandWrapper",
    "invoke_agent",
    "process_snippet_references",
    "process_xfile_references",
    "validate_file_references",
]
