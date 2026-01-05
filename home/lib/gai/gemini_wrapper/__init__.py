"""Gemini wrapper module for invoking Gemini agents."""

from .file_references import process_xfile_references
from .wrapper import GeminiCommandWrapper, invoke_agent

__all__ = ["GeminiCommandWrapper", "invoke_agent", "process_xfile_references"]
