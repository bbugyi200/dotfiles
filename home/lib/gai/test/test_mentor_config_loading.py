"""Tests for _load_mentor_profiles() function including error cases."""

import pytest
from mentor_config import _load_mentor_profiles
from test_utils import mentor_config_from_yaml


def test_load_mentor_profiles_valid_config() -> None:
    """Test loading valid mentor profiles from config."""
    yaml_content = """
mentor_profiles:
  - profile_name: profile1
    mentors:
      - mentor_name: mentor1
        xprompt: Prompt 1.
      - mentor_name: mentor2
        xprompt: Prompt 2.
    file_globs:
      - "*.py"
  - profile_name: profile2
    mentors:
      - mentor_name: mentor3
        xprompt: Prompt 3.
    diff_regexes:
      - "TODO:"
"""
    with mentor_config_from_yaml(yaml_content):
        profiles = _load_mentor_profiles()

    assert len(profiles) == 2
    assert profiles[0].profile_name == "profile1"
    assert len(profiles[0].mentors) == 2
    assert profiles[0].mentors[0].mentor_name == "mentor1"
    assert profiles[0].mentors[0].xprompt == "Prompt 1."
    assert profiles[0].mentors[1].mentor_name == "mentor2"
    assert profiles[0].file_globs == ["*.py"]
    assert profiles[1].profile_name == "profile2"
    assert profiles[1].diff_regexes == ["TODO:"]


def test_load_mentor_profiles_missing_key_returns_empty() -> None:
    """Test loading when mentor_profiles key is missing returns empty list."""
    yaml_content = """
other_key:
  - value: test
"""
    with mentor_config_from_yaml(yaml_content):
        profiles = _load_mentor_profiles()

    assert profiles == []


def test_load_mentor_profiles_with_run_on_wip() -> None:
    """Test loading mentor profiles with run_on_wip field on mentors."""
    yaml_content = """
mentor_profiles:
  - profile_name: test_profile
    mentors:
      - mentor_name: quick_mentor
        xprompt: Quick review.
        run_on_wip: true
      - mentor_name: full_mentor
        xprompt: Full review.
      - mentor_name: detailed_mentor
        xprompt: Detailed review.
        run_on_wip: false
    file_globs:
      - "*.py"
"""
    with mentor_config_from_yaml(yaml_content):
        profiles = _load_mentor_profiles()

    assert len(profiles) == 1
    assert len(profiles[0].mentors) == 3
    assert profiles[0].mentors[0].mentor_name == "quick_mentor"
    assert profiles[0].mentors[0].run_on_wip is True
    assert profiles[0].mentors[1].mentor_name == "full_mentor"
    assert profiles[0].mentors[1].run_on_wip is False  # Default
    assert profiles[0].mentors[2].mentor_name == "detailed_mentor"
    assert profiles[0].mentors[2].run_on_wip is False


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
    with mentor_config_from_yaml(yaml_content):
        with pytest.raises(ValueError, match="must be a dictionary"):
            _load_mentor_profiles()


def test_load_mentor_profiles_mentor_name_derived_from_xprompt() -> None:
    """Test mentor_name is derived from xprompt when not provided."""
    yaml_content = """
mentor_profiles:
  - profile_name: profile1
    mentors:
      - xprompt: "#simple_mentor"
    file_globs:
      - "*.py"
"""
    with mentor_config_from_yaml(yaml_content):
        # xprompt without mentor_name should derive name from xprompt
        profiles = _load_mentor_profiles()
        # "#simple_mentor" -> "simple_mentor" (strips leading #)
        assert profiles[0].mentors[0].mentor_name == "simple_mentor"


def test_load_mentor_profiles_mentor_missing_xprompt() -> None:
    """Test loading raises ValueError when mentor is missing xprompt."""
    yaml_content = """
mentor_profiles:
  - profile_name: profile1
    mentors:
      - mentor_name: mentor_without_xprompt
    file_globs:
      - "*.py"
"""
    with mentor_config_from_yaml(yaml_content):
        with pytest.raises(ValueError, match="must have 'xprompt' field"):
            _load_mentor_profiles()


def test_load_mentor_profiles_config_not_dict() -> None:
    """Test loading raises ValueError when config is not a dictionary."""
    yaml_content = """
- just_a_list_item
- another_item
"""
    with mentor_config_from_yaml(yaml_content):
        with pytest.raises(ValueError, match="Config must be a dictionary"):
            _load_mentor_profiles()


def test_load_mentor_profiles_profile_not_dict() -> None:
    """Test loading raises ValueError when mentor profile is not a dictionary."""
    yaml_content = """
mentor_profiles:
  - "just_a_string_profile"
"""
    with mentor_config_from_yaml(yaml_content):
        with pytest.raises(
            ValueError, match="Each mentor profile must be a dictionary"
        ):
            _load_mentor_profiles()


def test_load_mentor_profiles_profile_missing_fields() -> None:
    """Test loading raises ValueError when profile is missing required fields."""
    yaml_content = """
mentor_profiles:
  - profile_name: test_profile
"""
    with mentor_config_from_yaml(yaml_content):
        with pytest.raises(
            ValueError, match="must have 'profile_name' and 'mentors' fields"
        ):
            _load_mentor_profiles()


def test_load_mentor_profiles_mentors_not_list() -> None:
    """Test loading raises ValueError when mentors field is not a list."""
    yaml_content = """
mentor_profiles:
  - profile_name: test_profile
    mentors: "not_a_list"
    file_globs:
      - "*.py"
"""
    with mentor_config_from_yaml(yaml_content):
        with pytest.raises(ValueError, match="'mentors' field must be a list"):
            _load_mentor_profiles()


def test_load_mentor_profiles_with_xprompt() -> None:
    """Test loading mentor profiles with xprompt field."""
    yaml_content = """
mentor_profiles:
  - profile_name: test_profile
    mentors:
      - xprompt: "#mentor/aaa"
      - xprompt: "#mentor/bbb"
        run_on_wip: true
    file_globs:
      - "*.py"
"""
    with mentor_config_from_yaml(yaml_content):
        profiles = _load_mentor_profiles()

    assert len(profiles) == 1
    assert len(profiles[0].mentors) == 2
    # mentor_name should be derived from xprompt
    assert profiles[0].mentors[0].mentor_name == "aaa"
    assert profiles[0].mentors[0].xprompt == "#mentor/aaa"
    assert profiles[0].mentors[0].run_on_wip is False
    assert profiles[0].mentors[1].mentor_name == "bbb"
    assert profiles[0].mentors[1].xprompt == "#mentor/bbb"
    assert profiles[0].mentors[1].run_on_wip is True


def test_load_mentor_profiles_xprompt_with_explicit_name() -> None:
    """Test loading mentor profiles with xprompt and explicit mentor_name."""
    yaml_content = """
mentor_profiles:
  - profile_name: test_profile
    mentors:
      - mentor_name: custom_name
        xprompt: "#mentor/aaa"
    file_globs:
      - "*.py"
"""
    with mentor_config_from_yaml(yaml_content):
        profiles = _load_mentor_profiles()

    assert profiles[0].mentors[0].mentor_name == "custom_name"
    assert profiles[0].mentors[0].xprompt == "#mentor/aaa"


def test_load_mentor_profiles_simple_xprompt_name_derivation() -> None:
    """Test that simple xprompt (no namespace) derives name correctly."""
    yaml_content = """
mentor_profiles:
  - profile_name: test_profile
    mentors:
      - xprompt: "#foo"
    file_globs:
      - "*.py"
"""
    with mentor_config_from_yaml(yaml_content):
        profiles = _load_mentor_profiles()

    # Should derive name from #foo -> foo
    assert profiles[0].mentors[0].mentor_name == "foo"
    assert profiles[0].mentors[0].xprompt == "#foo"


def test_load_mentor_profiles_multiple_xprompts() -> None:
    """Test loading mentor profiles with multiple xprompts."""
    yaml_content = """
mentor_profiles:
  - profile_name: test_profile
    mentors:
      - mentor_name: first
        xprompt: "First prompt text"
      - xprompt: "#mentor/new"
    file_globs:
      - "*.py"
"""
    with mentor_config_from_yaml(yaml_content):
        profiles = _load_mentor_profiles()

    assert len(profiles[0].mentors) == 2
    # First mentor with explicit name
    assert profiles[0].mentors[0].mentor_name == "first"
    assert profiles[0].mentors[0].xprompt == "First prompt text"
    # Second mentor with name derived from xprompt
    assert profiles[0].mentors[1].mentor_name == "new"
    assert profiles[0].mentors[1].xprompt == "#mentor/new"
