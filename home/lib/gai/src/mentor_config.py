"""Mentor configuration loading and validation."""

import os
from dataclasses import dataclass

import yaml  # type: ignore[import-untyped]


@dataclass
class MentorConfig:
    """Represents a mentor configuration."""

    name: str
    prompt: str


@dataclass
class MentorProfileConfig:
    """Represents a mentor profile configuration.

    A mentor profile defines which mentors to run based on matching criteria.
    If no filter criteria (file_globs, diff_regexes, amend_note_regexes) are provided,
    the profile matches ALL non-proposal commits.
    """

    name: str
    mentors: list[str]  # Names must match entries in the mentors: field
    file_globs: list[str] | None = None  # Glob patterns to match changed file paths
    diff_regexes: list[str] | None = None  # Regex patterns to match diff content
    amend_note_regexes: list[str] | None = None  # Regex patterns to match commit notes


def _get_config_path() -> str:
    """Get the path to the gai config file."""
    return os.path.expanduser("~/.config/gai/gai.yml")


def _parse_mentors_from_data(data: dict) -> list[MentorConfig]:
    """Parse mentors from already-loaded YAML data.

    Args:
        data: The loaded YAML config dictionary.

    Returns:
        List of MentorConfig objects.

    Raises:
        ValueError: If config is malformed.
    """
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


def _validate_mentor_config(
    mentors: list[MentorConfig],
    profiles: list[MentorProfileConfig],
) -> None:
    """Validate cross-references between mentors and mentor_profiles.

    Args:
        mentors: List of loaded MentorConfig objects.
        profiles: List of loaded MentorProfileConfig objects.

    Raises:
        ValueError: If validation fails (unreferenced mentors, duplicate references).
    """
    # Collect all mentor names defined in mentors: section
    defined_mentor_names = {m.name for m in mentors}

    # Track which mentor is referenced by which profiles
    mentor_to_profiles: dict[str, list[str]] = {}
    for profile in profiles:
        for mentor_name in profile.mentors:
            if mentor_name not in mentor_to_profiles:
                mentor_to_profiles[mentor_name] = []
            mentor_to_profiles[mentor_name].append(profile.name)

    # Check for duplicate references (mentor referenced by multiple profiles)
    duplicates: list[str] = []
    for mentor_name, profile_names in mentor_to_profiles.items():
        if len(profile_names) > 1:
            duplicates.append(
                f"'{mentor_name}' referenced by: {', '.join(profile_names)}"
            )
    if duplicates:
        raise ValueError(
            f"Mentor(s) referenced by multiple profiles: {'; '.join(duplicates)}. "
            "Each mentor may only be referenced by one mentor_profiles entry."
        )

    # Check for unreferenced mentors
    referenced_mentor_names = set(mentor_to_profiles.keys())
    unreferenced = defined_mentor_names - referenced_mentor_names
    if unreferenced:
        raise ValueError(
            f"Unreferenced mentor(s) in config: {', '.join(sorted(unreferenced))}. "
            "Each mentor must be referenced by at least one mentor_profiles entry."
        )


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

    return _parse_mentors_from_data(data)


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


def _load_mentor_profiles() -> list[MentorProfileConfig]:
    """Load all mentor profile configurations from the config file.

    Returns:
        List of MentorProfileConfig objects.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config file is malformed or validation fails.
    """
    config_path = _get_config_path()

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Config must be a dictionary")

    # Load mentors for cross-validation
    mentors = _parse_mentors_from_data(data)

    # Parse mentor_profiles if present
    profiles: list[MentorProfileConfig] = []
    if "mentor_profiles" in data:
        for item in data["mentor_profiles"]:
            if not isinstance(item, dict):
                raise ValueError("Each mentor profile must be a dictionary")
            if "name" not in item or "mentors" not in item:
                raise ValueError(
                    "Each mentor profile must have 'name' and 'mentors' fields"
                )
            if not isinstance(item["mentors"], list):
                raise ValueError("'mentors' field must be a list")

            profiles.append(
                MentorProfileConfig(
                    name=item["name"],
                    mentors=item["mentors"],
                    file_globs=item.get("file_globs"),
                    diff_regexes=item.get("diff_regexes"),
                    amend_note_regexes=item.get("amend_note_regexes"),
                )
            )

    # Validate cross-references between mentors and profiles
    _validate_mentor_config(mentors, profiles)

    return profiles


def get_all_mentor_profiles() -> list[MentorProfileConfig]:
    """Get all mentor profile configurations.

    Returns:
        List of MentorProfileConfig objects, or empty list if config cannot be loaded.
    """
    try:
        return _load_mentor_profiles()
    except (FileNotFoundError, ValueError):
        return []


def get_mentor_profile_by_name(name: str) -> MentorProfileConfig | None:
    """Get a mentor profile configuration by name.

    Args:
        name: The name of the profile to find.

    Returns:
        The MentorProfileConfig if found, None otherwise.
    """
    for profile in get_all_mentor_profiles():
        if profile.name == name:
            return profile
    return None
