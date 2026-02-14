"""LLM Provider abstraction layer.

Provides a pluggable interface for LLM backends (Gemini, Claude, etc.)
with shared preprocessing, postprocessing, and orchestration.
"""

from ._invoke import invoke_agent
from .base import LLMProvider
from .gemini import stream_process_output
from .postprocessing import log_prompt_and_response, save_prompt_to_file
from .registry import get_provider, register_provider
from .types import LoggingContext, ModelTier

__all__ = [
    "LLMProvider",
    "LoggingContext",
    "ModelTier",
    "get_provider",
    "invoke_agent",
    "log_prompt_and_response",
    "register_provider",
    "save_prompt_to_file",
    "stream_process_output",
]
