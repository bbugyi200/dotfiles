"""LLM provider registry — maps provider names to LLMProvider subclasses."""

from .base import LLMProvider

_REGISTRY: dict[str, type[LLMProvider]] = {}


def register_provider(name: str, provider_cls: type[LLMProvider]) -> None:
    """Register an LLM provider class under the given name.

    Args:
        name: Short identifier (e.g. "gemini", "claude").
        provider_cls: The LLMProvider subclass to register.
    """
    _REGISTRY[name] = provider_cls


def get_provider(name: str) -> LLMProvider:
    """Look up a registered provider by name and return an instance.

    Args:
        name: The provider identifier.

    Returns:
        A new instance of the registered LLMProvider subclass.

    Raises:
        KeyError: If no provider is registered under *name*.
    """
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(
            f"Unknown LLM provider {name!r}. Available providers: {available}"
        )
    return _REGISTRY[name]()


def get_registered_providers() -> dict[str, type[LLMProvider]]:
    """Return a copy of the current registry."""
    return dict(_REGISTRY)
