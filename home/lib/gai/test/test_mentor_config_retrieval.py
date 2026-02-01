"""Tests for mentor profile and mentor retrieval functions, and WIP-related functions."""

from unittest.mock import patch

from mentor_config import (
    MentorConfig,
    MentorProfileConfig,
    _get_wip_mentor_count,
    get_all_mentor_profiles,
    get_mentor_from_profile,
    get_mentor_profile_by_name,
    profile_has_wip_mentors,
)
from test_utils import mentor_config_from_yaml


def test_get_all_mentor_profiles() -> None:
    """Test getting all mentor profiles."""
    yaml_content = """
mentor_profiles:
  - profile_name: profile1
    mentors:
      - mentor_name: m1
        xprompt: Prompt 1.
    file_globs:
      - "*.txt"
"""
    with mentor_config_from_yaml(yaml_content):
        profiles = get_all_mentor_profiles()

    assert len(profiles) == 1
    assert profiles[0].profile_name == "profile1"


def test_get_all_mentor_profiles_config_error() -> None:
    """Test that get_all_mentor_profiles returns empty list on config errors."""
    with patch("mentor_config._get_config_path", return_value="/nonexistent/path.yml"):
        profiles = get_all_mentor_profiles()

    assert profiles == []


def test_get_mentor_profile_by_name_found() -> None:
    """Test getting a mentor profile by name when it exists."""
    yaml_content = """
mentor_profiles:
  - profile_name: test_profile
    mentors:
      - mentor_name: mentor1
        xprompt: Prompt 1.
      - mentor_name: mentor2
        xprompt: Prompt 2.
    file_globs:
      - "*.py"
  - profile_name: other_profile
    mentors:
      - mentor_name: mentor3
        xprompt: Prompt 3.
    file_globs:
      - "*.txt"
"""
    with mentor_config_from_yaml(yaml_content):
        profile = get_mentor_profile_by_name("test_profile")

    assert profile is not None
    assert profile.profile_name == "test_profile"
    assert len(profile.mentors) == 2
    assert profile.mentors[0].mentor_name == "mentor1"
    assert profile.mentors[1].mentor_name == "mentor2"
    assert profile.file_globs == ["*.py"]


def test_get_mentor_profile_by_name_not_found() -> None:
    """Test getting a mentor profile by name when it doesn't exist."""
    yaml_content = """
mentor_profiles:
  - profile_name: existing_profile
    mentors:
      - mentor_name: mentor1
        xprompt: Prompt 1.
    file_globs:
      - "*.py"
"""
    with mentor_config_from_yaml(yaml_content):
        profile = get_mentor_profile_by_name("nonexistent_profile")

    assert profile is None


def test_get_mentor_profile_by_name_config_error() -> None:
    """Test that get_mentor_profile_by_name returns None on config errors."""
    with patch("mentor_config._get_config_path", return_value="/nonexistent/path.yml"):
        profile = get_mentor_profile_by_name("any_profile")

    assert profile is None


def test_get_mentor_from_profile_found() -> None:
    """Test getting a mentor from a profile when it exists."""
    mentors = [
        MentorConfig(mentor_name="mentor1", xprompt="Prompt 1"),
        MentorConfig(mentor_name="mentor2", xprompt="Prompt 2"),
        MentorConfig(mentor_name="mentor3", xprompt="Prompt 3", run_on_wip=True),
    ]
    profile = MentorProfileConfig(
        profile_name="test_profile",
        mentors=mentors,
        file_globs=["*.py"],
    )

    mentor = get_mentor_from_profile(profile, "mentor2")

    assert mentor is not None
    assert mentor.mentor_name == "mentor2"
    assert mentor.xprompt == "Prompt 2"
    assert mentor.run_on_wip is False


def test_get_mentor_from_profile_not_found() -> None:
    """Test getting a mentor from a profile when it doesn't exist."""
    mentors = [
        MentorConfig(mentor_name="mentor1", xprompt="Prompt 1"),
        MentorConfig(mentor_name="mentor2", xprompt="Prompt 2"),
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
            mentor_name="quick_mentor", xprompt="Quick review", run_on_wip=True
        ),
        MentorConfig(mentor_name="full_mentor", xprompt="Full review"),
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


def test__get_wip_mentor_count_no_wip_mentors() -> None:
    """Test _get_wip_mentor_count when no mentors have run_on_wip=True."""
    mentors = [
        MentorConfig(mentor_name="mentor1", xprompt="Prompt 1"),
        MentorConfig(mentor_name="mentor2", xprompt="Prompt 2"),
    ]
    profile = MentorProfileConfig(
        profile_name="test_profile",
        mentors=mentors,
        file_globs=["*.py"],
    )

    count = _get_wip_mentor_count(profile)
    assert count == 0


def test__get_wip_mentor_count_some_wip_mentors() -> None:
    """Test _get_wip_mentor_count when some mentors have run_on_wip=True."""
    mentors = [
        MentorConfig(mentor_name="quick", xprompt="Quick review", run_on_wip=True),
        MentorConfig(mentor_name="full", xprompt="Full review"),
        MentorConfig(mentor_name="deep", xprompt="Deep review", run_on_wip=True),
    ]
    profile = MentorProfileConfig(
        profile_name="test_profile",
        mentors=mentors,
        file_globs=["*.py"],
    )

    count = _get_wip_mentor_count(profile)
    assert count == 2


def test__get_wip_mentor_count_all_wip_mentors() -> None:
    """Test _get_wip_mentor_count when all mentors have run_on_wip=True."""
    mentors = [
        MentorConfig(mentor_name="quick", xprompt="Quick review", run_on_wip=True),
        MentorConfig(mentor_name="full", xprompt="Full review", run_on_wip=True),
    ]
    profile = MentorProfileConfig(
        profile_name="test_profile",
        mentors=mentors,
        file_globs=["*.py"],
    )

    count = _get_wip_mentor_count(profile)
    assert count == 2


def test_profile_has_wip_mentors_true() -> None:
    """Test profile_has_wip_mentors returns True when profile has WIP mentors."""
    yaml_content = """
mentor_profiles:
  - profile_name: test_profile
    mentors:
      - mentor_name: quick
        xprompt: Quick review.
        run_on_wip: true
      - mentor_name: full
        xprompt: Full review.
    file_globs:
      - "*.py"
"""
    with mentor_config_from_yaml(yaml_content):
        result = profile_has_wip_mentors("test_profile")

    assert result is True


def test_profile_has_wip_mentors_false() -> None:
    """Test profile_has_wip_mentors returns False when no WIP mentors."""
    yaml_content = """
mentor_profiles:
  - profile_name: test_profile
    mentors:
      - mentor_name: full
        xprompt: Full review.
      - mentor_name: detailed
        xprompt: Detailed review.
    file_globs:
      - "*.py"
"""
    with mentor_config_from_yaml(yaml_content):
        result = profile_has_wip_mentors("test_profile")

    assert result is False


def test_profile_has_wip_mentors_nonexistent_profile() -> None:
    """Test profile_has_wip_mentors returns False for nonexistent profile."""
    with patch("mentor_config._get_config_path", return_value="/nonexistent/path.yml"):
        result = profile_has_wip_mentors("nonexistent_profile")

    assert result is False
