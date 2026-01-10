"""Tests for the mentor_config module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from mentor_config import (
    MentorConfig,
    MentorProfileConfig,
    _load_mentor_profiles,
    get_all_mentor_profiles,
    get_mentor_from_profile,
)


def test_mentor_config_dataclass() -> None:
    """Test MentorConfig dataclass."""
    config = MentorConfig(mentor_name="test", prompt="test prompt")

    assert config.mentor_name == "test"
    assert config.prompt == "test prompt"
    assert config.run_on_wip is False  # Default value


def test_mentor_config_run_on_wip_default() -> None:
    """Test MentorConfig run_on_wip defaults to False."""
    config = MentorConfig(mentor_name="test", prompt="test prompt")
    assert config.run_on_wip is False


def test_mentor_config_run_on_wip_true() -> None:
    """Test MentorConfig with run_on_wip=True."""
    config = MentorConfig(mentor_name="test", prompt="test prompt", run_on_wip=True)
    assert config.run_on_wip is True


# Tests for MentorProfileConfig


def test_mentor_profile_config_with_file_globs() -> None:
    """Test MentorProfileConfig with file_globs."""
    mentors = [
        MentorConfig(mentor_name="mentor1", prompt="Prompt 1"),
        MentorConfig(mentor_name="mentor2", prompt="Prompt 2"),
    ]
    profile = MentorProfileConfig(
        profile_name="test_profile",
        mentors=mentors,
        file_globs=["*.py", "*.txt"],
    )

    assert profile.profile_name == "test_profile"
    assert len(profile.mentors) == 2
    assert profile.mentors[0].mentor_name == "mentor1"
    assert profile.mentors[1].mentor_name == "mentor2"
    assert profile.file_globs == ["*.py", "*.txt"]
    assert profile.diff_regexes is None
    assert profile.amend_note_regexes is None


def test_mentor_profile_config_with_diff_regexes() -> None:
    """Test MentorProfileConfig with diff_regexes."""
    mentors = [MentorConfig(mentor_name="mentor1", prompt="Prompt 1")]
    profile = MentorProfileConfig(
        profile_name="test_profile",
        mentors=mentors,
        diff_regexes=[r"TODO:", r"FIXME:"],
    )

    assert profile.profile_name == "test_profile"
    assert profile.diff_regexes == [r"TODO:", r"FIXME:"]


def test_mentor_profile_config_with_amend_note_regexes() -> None:
    """Test MentorProfileConfig with amend_note_regexes."""
    mentors = [MentorConfig(mentor_name="mentor1", prompt="Prompt 1")]
    profile = MentorProfileConfig(
        profile_name="test_profile",
        mentors=mentors,
        amend_note_regexes=[r"refactor", r"cleanup"],
    )

    assert profile.profile_name == "test_profile"
    assert profile.amend_note_regexes == [r"refactor", r"cleanup"]


def test_mentor_profile_config_with_all_criteria() -> None:
    """Test MentorProfileConfig with all matching criteria."""
    mentors = [MentorConfig(mentor_name="mentor1", prompt="Prompt 1")]
    profile = MentorProfileConfig(
        profile_name="full_profile",
        mentors=mentors,
        file_globs=["*.py"],
        diff_regexes=[r"def "],
        amend_note_regexes=[r"add"],
    )

    assert profile.file_globs == ["*.py"]
    assert profile.diff_regexes == [r"def "]
    assert profile.amend_note_regexes == [r"add"]


def test_mentor_profile_config_no_criteria_raises_error() -> None:
    """Test MentorProfileConfig raises ValueError when no criteria provided."""
    mentors = [MentorConfig(mentor_name="mentor1", prompt="Prompt 1")]
    with pytest.raises(
        ValueError, match="must have at least one of: file_globs, diff_regexes"
    ):
        MentorProfileConfig(
            profile_name="invalid_profile",
            mentors=mentors,
        )


def test_load_mentor_profiles_valid_config() -> None:
    """Test loading valid mentor profiles from config."""
    yaml_content = """
mentor_profiles:
  - profile_name: profile1
    mentors:
      - mentor_name: mentor1
        prompt: Prompt 1.
      - mentor_name: mentor2
        prompt: Prompt 2.
    file_globs:
      - "*.py"
  - profile_name: profile2
    mentors:
      - mentor_name: mentor3
        prompt: Prompt 3.
    diff_regexes:
      - "TODO:"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        profiles = _load_mentor_profiles()

    assert len(profiles) == 2
    assert profiles[0].profile_name == "profile1"
    assert len(profiles[0].mentors) == 2
    assert profiles[0].mentors[0].mentor_name == "mentor1"
    assert profiles[0].mentors[0].prompt == "Prompt 1."
    assert profiles[0].mentors[1].mentor_name == "mentor2"
    assert profiles[0].file_globs == ["*.py"]
    assert profiles[1].profile_name == "profile2"
    assert profiles[1].diff_regexes == ["TODO:"]

    Path(config_path).unlink()


def test_load_mentor_profiles_missing_key_returns_empty() -> None:
    """Test loading when mentor_profiles key is missing returns empty list."""
    yaml_content = """
other_key:
  - value: test
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        profiles = _load_mentor_profiles()

    assert profiles == []

    Path(config_path).unlink()


def test_load_mentor_profiles_with_run_on_wip() -> None:
    """Test loading mentor profiles with run_on_wip field on mentors."""
    yaml_content = """
mentor_profiles:
  - profile_name: test_profile
    mentors:
      - mentor_name: quick_mentor
        prompt: Quick review.
        run_on_wip: true
      - mentor_name: full_mentor
        prompt: Full review.
      - mentor_name: detailed_mentor
        prompt: Detailed review.
        run_on_wip: false
    file_globs:
      - "*.py"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        profiles = _load_mentor_profiles()

    assert len(profiles) == 1
    assert len(profiles[0].mentors) == 3
    assert profiles[0].mentors[0].mentor_name == "quick_mentor"
    assert profiles[0].mentors[0].run_on_wip is True
    assert profiles[0].mentors[1].mentor_name == "full_mentor"
    assert profiles[0].mentors[1].run_on_wip is False  # Default
    assert profiles[0].mentors[2].mentor_name == "detailed_mentor"
    assert profiles[0].mentors[2].run_on_wip is False

    Path(config_path).unlink()


def test_load_mentor_profiles_invalid_mentor_not_dict() -> None:
    """Test loading raises ValueError when mentor is not a dictionary."""
    yaml_content = """
mentor_profiles:
  - profile_name: profile1
    mentors:
      - "just_a_string"
    file_globs:
      - "*.py"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        with pytest.raises(ValueError, match="must be a dictionary"):
            _load_mentor_profiles()

    Path(config_path).unlink()


def test_load_mentor_profiles_mentor_missing_name() -> None:
    """Test loading raises ValueError when mentor is missing name field."""
    yaml_content = """
mentor_profiles:
  - profile_name: profile1
    mentors:
      - prompt: No name provided
    file_globs:
      - "*.py"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        with pytest.raises(
            ValueError, match="must have 'mentor_name' and 'prompt' fields"
        ):
            _load_mentor_profiles()

    Path(config_path).unlink()


def test_load_mentor_profiles_mentor_missing_prompt() -> None:
    """Test loading raises ValueError when mentor is missing prompt field."""
    yaml_content = """
mentor_profiles:
  - profile_name: profile1
    mentors:
      - mentor_name: mentor_without_prompt
    file_globs:
      - "*.py"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        with pytest.raises(
            ValueError, match="must have 'mentor_name' and 'prompt' fields"
        ):
            _load_mentor_profiles()

    Path(config_path).unlink()


def test_get_all_mentor_profiles() -> None:
    """Test getting all mentor profiles."""
    yaml_content = """
mentor_profiles:
  - profile_name: profile1
    mentors:
      - mentor_name: m1
        prompt: Prompt 1.
    file_globs:
      - "*.txt"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        profiles = get_all_mentor_profiles()

    assert len(profiles) == 1
    assert profiles[0].profile_name == "profile1"

    Path(config_path).unlink()


def test_get_all_mentor_profiles_config_error() -> None:
    """Test that get_all_mentor_profiles returns empty list on config errors."""
    with patch("mentor_config._get_config_path", return_value="/nonexistent/path.yml"):
        profiles = get_all_mentor_profiles()

    assert profiles == []


def test_get_mentor_profile_by_name_found() -> None:
    """Test getting a mentor profile by name when it exists."""
    from mentor_config import get_mentor_profile_by_name

    yaml_content = """
mentor_profiles:
  - profile_name: test_profile
    mentors:
      - mentor_name: mentor1
        prompt: Prompt 1.
      - mentor_name: mentor2
        prompt: Prompt 2.
    file_globs:
      - "*.py"
  - profile_name: other_profile
    mentors:
      - mentor_name: mentor3
        prompt: Prompt 3.
    file_globs:
      - "*.txt"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        profile = get_mentor_profile_by_name("test_profile")

    assert profile is not None
    assert profile.profile_name == "test_profile"
    assert len(profile.mentors) == 2
    assert profile.mentors[0].mentor_name == "mentor1"
    assert profile.mentors[1].mentor_name == "mentor2"
    assert profile.file_globs == ["*.py"]

    Path(config_path).unlink()


def test_get_mentor_profile_by_name_not_found() -> None:
    """Test getting a mentor profile by name when it doesn't exist."""
    from mentor_config import get_mentor_profile_by_name

    yaml_content = """
mentor_profiles:
  - profile_name: existing_profile
    mentors:
      - mentor_name: mentor1
        prompt: Prompt 1.
    file_globs:
      - "*.py"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        profile = get_mentor_profile_by_name("nonexistent_profile")

    assert profile is None

    Path(config_path).unlink()


def test_get_mentor_profile_by_name_config_error() -> None:
    """Test that get_mentor_profile_by_name returns None on config errors."""
    from mentor_config import get_mentor_profile_by_name

    with patch("mentor_config._get_config_path", return_value="/nonexistent/path.yml"):
        profile = get_mentor_profile_by_name("any_profile")

    assert profile is None


# Tests for get_mentor_from_profile


def test_get_mentor_from_profile_found() -> None:
    """Test getting a mentor from a profile when it exists."""
    mentors = [
        MentorConfig(mentor_name="mentor1", prompt="Prompt 1"),
        MentorConfig(mentor_name="mentor2", prompt="Prompt 2"),
        MentorConfig(mentor_name="mentor3", prompt="Prompt 3", run_on_wip=True),
    ]
    profile = MentorProfileConfig(
        profile_name="test_profile",
        mentors=mentors,
        file_globs=["*.py"],
    )

    mentor = get_mentor_from_profile(profile, "mentor2")

    assert mentor is not None
    assert mentor.mentor_name == "mentor2"
    assert mentor.prompt == "Prompt 2"
    assert mentor.run_on_wip is False


def test_get_mentor_from_profile_not_found() -> None:
    """Test getting a mentor from a profile when it doesn't exist."""
    mentors = [
        MentorConfig(mentor_name="mentor1", prompt="Prompt 1"),
        MentorConfig(mentor_name="mentor2", prompt="Prompt 2"),
    ]
    profile = MentorProfileConfig(
        profile_name="test_profile",
        mentors=mentors,
        file_globs=["*.py"],
    )

    mentor = get_mentor_from_profile(profile, "nonexistent")

    assert mentor is None


def test_get_mentor_from_profile_with_run_on_wip() -> None:
    """Test getting a mentor with run_on_wip=True from a profile."""
    mentors = [
        MentorConfig(
            mentor_name="quick_mentor", prompt="Quick review", run_on_wip=True
        ),
        MentorConfig(mentor_name="full_mentor", prompt="Full review"),
    ]
    profile = MentorProfileConfig(
        profile_name="test_profile",
        mentors=mentors,
        file_globs=["*.py"],
    )

    mentor = get_mentor_from_profile(profile, "quick_mentor")

    assert mentor is not None
    assert mentor.mentor_name == "quick_mentor"
    assert mentor.run_on_wip is True
