"""Snippet configuration loading and validation."""

import os

import yaml  # type: ignore[import-untyped]


def _get_config_path() -> str:
    """Get the path to the gai config file."""
    return os.path.expanduser("~/.config/gai/gai.yml")


def _load_snippets() -> dict[str, str]:
    """Load all snippet configurations from the config file.

    Returns:
        Dictionary mapping snippet name to content.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config file is malformed.
    """
    config_path = _get_config_path()

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Config must be a dictionary")

    # snippets is optional - return empty dict if not present
    if "snippets" not in data:
        return {}

    snippets_data = data["snippets"]
    if not isinstance(snippets_data, dict):
        raise ValueError("'snippets' must be a dictionary mapping names to content")

    # Validate and convert snippets
    snippets: dict[str, str] = {}
    for name, content in snippets_data.items():
        if not isinstance(name, str):
            raise ValueError(f"Snippet name must be a string, got: {type(name)}")
        if not isinstance(content, str):
            raise ValueError(
                f"Snippet '{name}' content must be a string, got: {type(content)}"
            )
        snippets[name] = content

    return snippets


def get_all_snippets() -> dict[str, str]:
    """Get all snippet configurations.

    Returns:
        Dictionary mapping snippet name to content,
        or empty dict if config cannot be loaded.
    """
    try:
        return _load_snippets()
    except (FileNotFoundError, ValueError):
        return {}
