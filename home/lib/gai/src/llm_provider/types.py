"""Types and data classes for the LLM provider abstraction."""

from dataclasses import dataclass
from typing import Any, Literal

ModelTier = Literal["little", "big"]

# Backward-compatible alias.
ModelSize = ModelTier


class LLMInvocationError(Exception):
    """Raised by LLM providers on invocation failure."""


@dataclass
class LoggingContext:
    """Consolidates all metadata needed for logging prompts and responses."""

    agent_type: str = "agent"
    model_tier: ModelTier = "big"
    iteration: int | None = None
    workflow_tag: str | None = None
    artifacts_dir: str | None = None
    workflow: str | None = None
    timestamp: str | None = None
    suppress_output: bool = False
    is_home_mode: bool = False
    decision_counts: dict[str, Any] | None = None
