"""LLM provider configuration loading from gai.yml."""

import os
from dataclasses import dataclass

import yaml  # type: ignore[import-untyped]

_DEFAULT_PROVIDER = "gemini"


@dataclass
class LLMProviderConfig:
    """Configuration for the llm_provider section of gai.yml."""

    provider: str = _DEFAULT_PROVIDER


def _get_config_path() -> str:
    """Get the path to the gai config file."""
    return os.path.expanduser("~/.config/gai/gai.yml")


def load_llm_provider_config() -> LLMProviderConfig:
    """Load LLM provider config from gai.yml.

    Returns:
        LLMProviderConfig with values from config or defaults.
    """
    config_path = _get_config_path()

    if not os.path.exists(config_path):
        return LLMProviderConfig()

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "llm_provider" not in data:
        return LLMProviderConfig()

    section = data["llm_provider"]
    if not isinstance(section, dict):
        return LLMProviderConfig()

    return LLMProviderConfig(
        provider=section.get("provider", _DEFAULT_PROVIDER),
    )
