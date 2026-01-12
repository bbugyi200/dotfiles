"""Mentor configuration loading and validation."""

import os
from dataclasses import dataclass

import yaml  # type: ignore[import-untyped]


@dataclass
class MentorConfig:
    """Represents a mentor configuration."""

    mentor_name: str
    prompt: str
    run_on_wip: bool = False  # If True, mentor runs even on WIP status


@dataclass
class MentorProfileConfig:
    """Represents a mentor profile configuration.

    A mentor profile defines which mentors to run based on matching criteria.
    At least one of file_globs, diff_regexes, or amend_note_regexes must be provided.
    """

    profile_name: str
    mentors: list[MentorConfig]  # Inline mentor definitions
    file_globs: list[str] | None = None  # Glob patterns to match changed file paths
    diff_regexes: list[str] | None = None  # Regex patterns to match diff content
    amend_note_regexes: list[str] | None = None  # Regex patterns to match commit notes

    def __post_init__(self) -> None:
        """Validate that at least one matching criterion is provided."""
        if not (self.file_globs or self.diff_regexes or self.amend_note_regexes):
            raise ValueError(
                f"MentorProfile '{self.profile_name}' must have at least one of: "
                "file_globs, diff_regexes, or amend_note_regexes"
            )


def _get_config_path() -> str:
    """Get the path to the gai config file."""
    return os.path.expanduser("~/.config/gai/gai.yml")


def _load_mentor_profiles() -> list[MentorProfileConfig]:
    """Load all mentor profile configurations from the config file.

    Returns:
        List of MentorProfileConfig objects.

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

    # mentor_profiles is optional - return empty list if not present
    if "mentor_profiles" not in data:
        return []

    profiles = []
    for item in data["mentor_profiles"]:
        if not isinstance(item, dict):
            raise ValueError("Each mentor profile must be a dictionary")
        if "profile_name" not in item or "mentors" not in item:
            raise ValueError(
                "Each mentor profile must have 'profile_name' and 'mentors' fields"
            )
        if not isinstance(item["mentors"], list):
            raise ValueError("'mentors' field must be a list")

        # Parse mentors as MentorConfig objects
        mentors = []
        for mentor_item in item["mentors"]:
            if not isinstance(mentor_item, dict):
                raise ValueError(
                    f"Each mentor in profile '{item['profile_name']}' must be a dictionary"
                )
            if "mentor_name" not in mentor_item or "prompt" not in mentor_item:
                raise ValueError(
                    f"Each mentor in profile '{item['profile_name']}' must have "
                    "'mentor_name' and 'prompt' fields"
                )
            mentors.append(
                MentorConfig(
                    mentor_name=mentor_item["mentor_name"],
                    prompt=mentor_item["prompt"],
                    run_on_wip=mentor_item.get("run_on_wip", False),
                )
            )

        profiles.append(
            MentorProfileConfig(
                profile_name=item["profile_name"],
                mentors=mentors,
                file_globs=item.get("file_globs"),
                diff_regexes=item.get("diff_regexes"),
                amend_note_regexes=item.get("amend_note_regexes"),
            )
        )

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
        if profile.profile_name == name:
            return profile
    return None


def get_mentor_from_profile(
    profile: MentorProfileConfig, mentor_name: str
) -> MentorConfig | None:
    """Get a mentor by name from a specific profile.

    Args:
        profile: The profile to search in.
        mentor_name: The name of the mentor to find.

    Returns:
        The MentorConfig if found, None otherwise.
    """
    for mentor in profile.mentors:
        if mentor.mentor_name == mentor_name:
            return mentor
    return None


def _get_wip_mentor_count(profile: MentorProfileConfig) -> int:
    """Count mentors in a profile that have run_on_wip=True.

    Args:
        profile: The profile configuration.

    Returns:
        Number of mentors with run_on_wip=True.
    """
    return sum(1 for m in profile.mentors if m.run_on_wip)


def profile_has_wip_mentors(profile_name: str) -> bool:
    """Check if a profile has any mentors with run_on_wip=True.

    Args:
        profile_name: The name of the profile.

    Returns:
        True if the profile has at least one mentor with run_on_wip=True.
    """
    profile = get_mentor_profile_by_name(profile_name)
    if profile is None:
        return False
    return _get_wip_mentor_count(profile) > 0
