"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod

from .types import ModelSize


class LLMProvider(ABC):
    """Abstract base class that all LLM providers must implement."""

    @abstractmethod
    def invoke_llm(
        self,
        query: str,
        *,
        model_size: ModelSize,
        suppress_output: bool = False,
    ) -> str:
        """Invoke the LLM with a preprocessed query.

        Args:
            query: The preprocessed prompt text.
            model_size: Which model tier to use ("little" or "big").
            suppress_output: If True, suppress streaming output to console.

        Returns:
            The raw response text from the LLM.

        Raises:
            LLMInvocationError: If the LLM invocation fails.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name string."""
