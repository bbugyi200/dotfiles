"""Tests for MentorConfig xprompt field functionality."""

import pytest
from mentor_config import MentorConfig, _load_mentor_profiles
from test_utils import mentor_config_from_yaml


def test_mentor_config_with_xprompt() -> None:
    """Test MentorConfig with xprompt field."""
    config = MentorConfig(mentor_name="aaa", xprompt="#mentor/aaa")

    assert config.mentor_name == "aaa"
    assert config.prompt is None
    assert config.xprompt == "#mentor/aaa"
    assert config.run_on_wip is False


def test_mentor_config_with_xprompt_and_run_on_wip() -> None:
    """Test MentorConfig with xprompt and run_on_wip=True."""
    config = MentorConfig(mentor_name="test", xprompt="#mentor/test", run_on_wip=True)

    assert config.xprompt == "#mentor/test"
    assert config.run_on_wip is True


def test_mentor_config_both_prompt_and_xprompt_raises() -> None:
    """Test that MentorConfig with both prompt and xprompt raises ValueError."""
    with pytest.raises(ValueError, match="cannot have both"):
        MentorConfig(mentor_name="test", prompt="test prompt", xprompt="#mentor/test")


def test_mentor_config_neither_prompt_nor_xprompt_raises() -> None:
    """Test that MentorConfig with neither prompt nor xprompt raises ValueError."""
    with pytest.raises(ValueError, match="must have 'prompt' or 'xprompt'"):
        MentorConfig(mentor_name="test")


def test_load_mentor_profiles_both_prompt_and_xprompt_raises() -> None:
    """Test that mentor with both prompt and xprompt raises ValueError."""
    yaml_content = """
mentor_profiles:
  - profile_name: test_profile
    mentors:
      - mentor_name: invalid
        prompt: "Some prompt"
        xprompt: "#mentor/test"
    file_globs:
      - "*.py"
"""
    with mentor_config_from_yaml(yaml_content):
        with pytest.raises(ValueError, match="cannot have both"):
            _load_mentor_profiles()


def test_load_mentor_profiles_neither_prompt_nor_xprompt_raises() -> None:
    """Test that mentor with neither prompt nor xprompt raises ValueError."""
    yaml_content = """
mentor_profiles:
  - profile_name: test_profile
    mentors:
      - mentor_name: invalid
        run_on_wip: true
    file_globs:
      - "*.py"
"""
    with mentor_config_from_yaml(yaml_content):
        with pytest.raises(ValueError, match="must have 'prompt' or 'xprompt'"):
            _load_mentor_profiles()


def test_load_mentor_profiles_prompt_without_name_raises() -> None:
    """Test that legacy prompt format without mentor_name raises ValueError."""
    yaml_content = """
mentor_profiles:
  - profile_name: test_profile
    mentors:
      - prompt: "Some prompt without name"
    file_globs:
      - "*.py"
"""
    with mentor_config_from_yaml(yaml_content):
        with pytest.raises(ValueError, match="must have 'mentor_name' field"):
            _load_mentor_profiles()
