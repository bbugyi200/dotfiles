"""Mentor configuration loading and validation."""

import os
from dataclasses import dataclass

import yaml  # type: ignore[import-untyped]


@dataclass
class MentorConfig:
    """Represents a mentor configuration."""

    name: str
    prompt: str


def _get_config_path() -> str:
    """Get the path to the gai config file."""
    return os.path.expanduser("~/.config/gai/gai.yml")


def _load_mentors() -> list[MentorConfig]:
    """Load all mentor configurations from the config file.

    Returns:
        List of MentorConfig objects.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config file is malformed.
    """
    config_path = _get_config_path()

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "mentors" not in data:
        raise ValueError("Config must contain a 'mentors' key")

    mentors = []
    for item in data["mentors"]:
        if not isinstance(item, dict):
            raise ValueError("Each mentor must be a dictionary")
        if "name" not in item or "prompt" not in item:
            raise ValueError("Each mentor must have 'name' and 'prompt' fields")
        mentors.append(MentorConfig(name=item["name"], prompt=item["prompt"]))

    return mentors


def get_mentor_by_name(mentor_name: str) -> MentorConfig | None:
    """Get a mentor configuration by name.

    Args:
        mentor_name: The name of the mentor to find.

    Returns:
        The MentorConfig if found, None otherwise.
    """
    try:
        mentors = _load_mentors()
        for mentor in mentors:
            if mentor.name == mentor_name:
                return mentor
        return None
    except (FileNotFoundError, ValueError):
        return None


def get_available_mentor_names() -> list[str]:
    """Get a list of all available mentor names.

    Returns:
        List of mentor names, or empty list if config cannot be loaded.
    """
    try:
        mentors = _load_mentors()
        return [mentor.name for mentor in mentors]
    except (FileNotFoundError, ValueError):
        return []
