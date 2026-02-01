"""Tests for MentorConfig prompt field functionality."""

import pytest
from mentor_config import MentorConfig, _load_mentor_profiles
from test_utils import mentor_config_from_yaml


def test_mentor_config_with_prompt() -> None:
    """Test MentorConfig with prompt field."""
    config = MentorConfig(mentor_name="aaa", prompt="#mentor/aaa")

    assert config.mentor_name == "aaa"
    assert config.prompt == "#mentor/aaa"
    assert config.run_on_wip is False


def test_mentor_config_with_prompt_and_run_on_wip() -> None:
    """Test MentorConfig with prompt and run_on_wip=True."""
    config = MentorConfig(mentor_name="test", prompt="#mentor/test", run_on_wip=True)

    assert config.prompt == "#mentor/test"
    assert config.run_on_wip is True


def test_load_mentor_profiles_without_prompt_raises() -> None:
    """Test that mentor without prompt raises ValueError."""
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
        with pytest.raises(ValueError, match="must have 'prompt' field"):
            _load_mentor_profiles()
