"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod

from .types import ModelTier


class LLMProvider(ABC):
    """Abstract base class for LLM backend providers.

    Providers receive an already-preprocessed prompt and return raw response
    text. All preprocessing/postprocessing is handled by the shared
    orchestration layer in ``_invoke.py``.
    """

    @abstractmethod
    def invoke(
        self,
        prompt: str,
        *,
        model_tier: ModelTier,
        suppress_output: bool = False,
    ) -> str:
        """Send a preprocessed prompt to the LLM and return the response text.

        Args:
            prompt: The preprocessed prompt to send.
            model_tier: Which model tier to use ("large" or "small").
            suppress_output: If True, suppress real-time output to console.

        Returns:
            The raw response text from the LLM.

        Raises:
            subprocess.CalledProcessError: If the underlying process fails.
        """
