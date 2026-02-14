"""LLM provider abstraction layer."""

from ._invoke import invoke_agent
from .base import LLMProvider
from .config import LLMProviderConfig, load_llm_provider_config
from .gemini import GeminiProvider, _stream_process_output
from .postprocessing import (
    log_prompt_and_response,
    run_error_postprocessing,
    run_postprocessing,
    save_prompt_to_file,
)
from .preprocessing import preprocess_prompt
from .registry import get_provider, get_registered_providers, register_provider
from .types import LLMInvocationError, LoggingContext, ModelSize, ModelTier

# Register built-in providers.
register_provider("gemini", GeminiProvider)

__all__ = [
    "GeminiProvider",
    "LLMInvocationError",
    "LLMProvider",
    "LLMProviderConfig",
    "LoggingContext",
    "ModelSize",
    "ModelTier",
    "_stream_process_output",
    "get_provider",
    "get_registered_providers",
    "invoke_agent",
    "load_llm_provider_config",
    "log_prompt_and_response",
    "preprocess_prompt",
    "register_provider",
    "run_error_postprocessing",
    "run_postprocessing",
    "save_prompt_to_file",
]
