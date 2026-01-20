"""Metahook configuration loading and matching."""

import os
import re
from dataclasses import dataclass

import yaml  # type: ignore[import-untyped]


@dataclass
class MetahookConfig:
    """Represents a metahook configuration.

    A metahook intercepts failing hooks before the summarize agent runs.
    It matches based on the hook command (substring) and hook output (regex).
    """

    name: str  # e.g., "scuba"
    hook_command: str  # substring match against hook command
    output_regex: str  # regex to match against hook output


def _get_config_path() -> str:
    """Get the path to the gai config file."""
    return os.path.expanduser("~/.config/gai/gai.yml")


def _load_metahooks() -> list[MetahookConfig]:
    """Load all metahook configurations from the config file.

    Returns:
        List of MetahookConfig objects.

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

    # metahooks is optional - return empty list if not present
    if "metahooks" not in data:
        return []

    metahooks_data = data["metahooks"]
    if not isinstance(metahooks_data, list):
        raise ValueError("'metahooks' must be a list")

    metahooks: list[MetahookConfig] = []
    for item in metahooks_data:
        if not isinstance(item, dict):
            raise ValueError("Each metahook must be a dictionary")

        # Validate required fields
        required_fields = ["name", "hook_command", "output_regex"]
        for field in required_fields:
            if field not in item:
                raise ValueError(f"Metahook missing required field: {field}")

        metahooks.append(
            MetahookConfig(
                name=item["name"],
                hook_command=item["hook_command"],
                output_regex=item["output_regex"],
            )
        )

    return metahooks


def _get_all_metahooks() -> list[MetahookConfig]:
    """Get all metahook configurations.

    Returns:
        List of MetahookConfig objects, or empty list if config cannot be loaded.
    """
    try:
        return _load_metahooks()
    except (FileNotFoundError, ValueError):
        return []


def find_matching_metahook(
    hook_command: str, hook_output: str
) -> MetahookConfig | None:
    """Find the first metahook that matches the given hook command and output.

    Args:
        hook_command: The hook command that was executed.
        hook_output: The output produced by the hook.

    Returns:
        The first matching MetahookConfig, or None if no match found.
    """
    for metahook in _get_all_metahooks():
        # Check command substring match
        if metahook.hook_command not in hook_command:
            continue

        # Check output regex match
        try:
            if re.search(metahook.output_regex, hook_output, re.MULTILINE):
                return metahook
        except re.error:
            # Invalid regex - skip this metahook
            continue

    return None
