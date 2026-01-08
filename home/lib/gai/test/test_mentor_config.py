"""Tests for the mentor_config module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from mentor_config import (
    MentorConfig,
    MentorProfileConfig,
    _load_mentor_profiles,
    _load_mentors,
    get_all_mentor_profiles,
    get_available_mentor_names,
    get_mentor_by_name,
    get_mentor_run_on_wip,
)


def test_load_mentors_valid_config() -> None:
    """Test loading a valid mentor config."""
    yaml_content = """
mentors:
  - name: aaa
    prompt: |
      Help me enforce AAA pattern.
  - name: bbb
    prompt: Help with BBB.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        mentors = _load_mentors()

    assert len(mentors) == 2
    assert mentors[0].name == "aaa"
    assert "AAA pattern" in mentors[0].prompt
    assert mentors[1].name == "bbb"
    assert mentors[1].prompt == "Help with BBB."

    Path(config_path).unlink()


def test_load_mentors_missing_file() -> None:
    """Test loading raises FileNotFoundError when config doesn't exist."""
    with patch("mentor_config._get_config_path", return_value="/nonexistent/path.yml"):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            _load_mentors()


def test_load_mentors_missing_mentors_key() -> None:
    """Test loading raises ValueError when mentors key is missing."""
    yaml_content = """
other_key:
  - name: foo
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        with pytest.raises(ValueError, match="must contain a 'mentors' key"):
            _load_mentors()

    Path(config_path).unlink()


def test_load_mentors_missing_name_field() -> None:
    """Test loading raises ValueError when a mentor is missing name field."""
    yaml_content = """
mentors:
  - prompt: No name provided
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        with pytest.raises(ValueError, match="must have 'name' and 'prompt' fields"):
            _load_mentors()

    Path(config_path).unlink()


def test_load_mentors_missing_prompt_field() -> None:
    """Test loading raises ValueError when a mentor is missing prompt field."""
    yaml_content = """
mentors:
  - name: test_mentor
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        with pytest.raises(ValueError, match="must have 'name' and 'prompt' fields"):
            _load_mentors()

    Path(config_path).unlink()


def test_get_mentor_by_name_found() -> None:
    """Test getting a mentor by name when it exists."""
    yaml_content = """
mentors:
  - name: test_mentor
    prompt: Test prompt.
  - name: other_mentor
    prompt: Other prompt.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        mentor = get_mentor_by_name("test_mentor")

    assert mentor is not None
    assert mentor.name == "test_mentor"
    assert mentor.prompt == "Test prompt."

    Path(config_path).unlink()


def test_get_mentor_by_name_not_found() -> None:
    """Test getting a mentor by name when it doesn't exist."""
    yaml_content = """
mentors:
  - name: existing_mentor
    prompt: Existing prompt.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        mentor = get_mentor_by_name("nonexistent_mentor")

    assert mentor is None

    Path(config_path).unlink()


def test_get_mentor_by_name_config_error() -> None:
    """Test that get_mentor_by_name returns None on config errors."""
    with patch("mentor_config._get_config_path", return_value="/nonexistent/path.yml"):
        mentor = get_mentor_by_name("any_name")

    assert mentor is None


def test_get_available_mentor_names() -> None:
    """Test getting list of available mentor names."""
    yaml_content = """
mentors:
  - name: mentor_a
    prompt: Prompt A.
  - name: mentor_b
    prompt: Prompt B.
  - name: mentor_c
    prompt: Prompt C.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        names = get_available_mentor_names()

    assert names == ["mentor_a", "mentor_b", "mentor_c"]

    Path(config_path).unlink()


def test_get_available_mentor_names_config_error() -> None:
    """Test that get_available_mentor_names returns empty list on config errors."""
    with patch("mentor_config._get_config_path", return_value="/nonexistent/path.yml"):
        names = get_available_mentor_names()

    assert names == []


def test_mentor_config_dataclass() -> None:
    """Test MentorConfig dataclass."""
    config = MentorConfig(name="test", prompt="test prompt")

    assert config.name == "test"
    assert config.prompt == "test prompt"
    assert config.run_on_wip is False  # Default value


def test_mentor_config_run_on_wip_default() -> None:
    """Test MentorConfig run_on_wip defaults to False."""
    config = MentorConfig(name="test", prompt="test prompt")
    assert config.run_on_wip is False


def test_mentor_config_run_on_wip_true() -> None:
    """Test MentorConfig with run_on_wip=True."""
    config = MentorConfig(name="test", prompt="test prompt", run_on_wip=True)
    assert config.run_on_wip is True


# Tests for MentorProfileConfig


def test_mentor_profile_config_with_file_globs() -> None:
    """Test MentorProfileConfig with file_globs."""
    profile = MentorProfileConfig(
        name="test_profile",
        mentors=["mentor1", "mentor2"],
        file_globs=["*.py", "*.txt"],
    )

    assert profile.name == "test_profile"
    assert profile.mentors == ["mentor1", "mentor2"]
    assert profile.file_globs == ["*.py", "*.txt"]
    assert profile.diff_regexes is None
    assert profile.amend_note_regexes is None


def test_mentor_profile_config_with_diff_regexes() -> None:
    """Test MentorProfileConfig with diff_regexes."""
    profile = MentorProfileConfig(
        name="test_profile",
        mentors=["mentor1"],
        diff_regexes=[r"TODO:", r"FIXME:"],
    )

    assert profile.name == "test_profile"
    assert profile.diff_regexes == [r"TODO:", r"FIXME:"]


def test_mentor_profile_config_with_amend_note_regexes() -> None:
    """Test MentorProfileConfig with amend_note_regexes."""
    profile = MentorProfileConfig(
        name="test_profile",
        mentors=["mentor1"],
        amend_note_regexes=[r"refactor", r"cleanup"],
    )

    assert profile.name == "test_profile"
    assert profile.amend_note_regexes == [r"refactor", r"cleanup"]


def test_mentor_profile_config_with_all_criteria() -> None:
    """Test MentorProfileConfig with all matching criteria."""
    profile = MentorProfileConfig(
        name="full_profile",
        mentors=["mentor1"],
        file_globs=["*.py"],
        diff_regexes=[r"def "],
        amend_note_regexes=[r"add"],
    )

    assert profile.file_globs == ["*.py"]
    assert profile.diff_regexes == [r"def "]
    assert profile.amend_note_regexes == [r"add"]


def test_mentor_profile_config_no_criteria_raises_error() -> None:
    """Test MentorProfileConfig raises ValueError when no criteria provided."""
    with pytest.raises(
        ValueError, match="must have at least one of: file_globs, diff_regexes"
    ):
        MentorProfileConfig(
            name="invalid_profile",
            mentors=["mentor1"],
        )


def test_load_mentor_profiles_valid_config() -> None:
    """Test loading valid mentor profiles from config."""
    yaml_content = """
mentors:
  - name: aaa
    prompt: Test prompt.

mentor_profiles:
  - name: profile1
    mentors:
      - mentor1
      - mentor2
    file_globs:
      - "*.py"
  - name: profile2
    mentors:
      - mentor3
    diff_regexes:
      - "TODO:"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        profiles = _load_mentor_profiles()

    assert len(profiles) == 2
    assert profiles[0].name == "profile1"
    assert profiles[0].mentors == ["mentor1", "mentor2"]
    assert profiles[0].file_globs == ["*.py"]
    assert profiles[1].name == "profile2"
    assert profiles[1].diff_regexes == ["TODO:"]

    Path(config_path).unlink()


def test_load_mentor_profiles_missing_key_returns_empty() -> None:
    """Test loading when mentor_profiles key is missing returns empty list."""
    yaml_content = """
mentors:
  - name: aaa
    prompt: Test prompt.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        profiles = _load_mentor_profiles()

    assert profiles == []

    Path(config_path).unlink()


def test_get_all_mentor_profiles() -> None:
    """Test getting all mentor profiles."""
    yaml_content = """
mentors:
  - name: aaa
    prompt: Test.

mentor_profiles:
  - name: profile1
    mentors:
      - m1
    file_globs:
      - "*.txt"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        profiles = get_all_mentor_profiles()

    assert len(profiles) == 1
    assert profiles[0].name == "profile1"

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
mentors:
  - name: aaa
    prompt: Test.

mentor_profiles:
  - name: test_profile
    mentors:
      - mentor1
      - mentor2
    file_globs:
      - "*.py"
  - name: other_profile
    mentors:
      - mentor3
    file_globs:
      - "*.txt"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        profile = get_mentor_profile_by_name("test_profile")

    assert profile is not None
    assert profile.name == "test_profile"
    assert profile.mentors == ["mentor1", "mentor2"]
    assert profile.file_globs == ["*.py"]

    Path(config_path).unlink()


def test_get_mentor_profile_by_name_not_found() -> None:
    """Test getting a mentor profile by name when it doesn't exist."""
    from mentor_config import get_mentor_profile_by_name

    yaml_content = """
mentors:
  - name: aaa
    prompt: Test.

mentor_profiles:
  - name: existing_profile
    mentors:
      - mentor1
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


# Tests for run_on_wip field


def test_load_mentors_with_run_on_wip() -> None:
    """Test loading mentors with run_on_wip field."""
    yaml_content = """
mentors:
  - name: quick_review
    prompt: Quick review.
    run_on_wip: true
  - name: full_review
    prompt: Full review.
  - name: detailed_review
    prompt: Detailed review.
    run_on_wip: false
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        mentors = _load_mentors()

    assert len(mentors) == 3
    assert mentors[0].name == "quick_review"
    assert mentors[0].run_on_wip is True
    assert mentors[1].name == "full_review"
    assert mentors[1].run_on_wip is False  # Default
    assert mentors[2].name == "detailed_review"
    assert mentors[2].run_on_wip is False

    Path(config_path).unlink()


def test_get_mentor_run_on_wip_true() -> None:
    """Test get_mentor_run_on_wip returns True for mentors with run_on_wip=True."""
    yaml_content = """
mentors:
  - name: wip_mentor
    prompt: WIP mentor.
    run_on_wip: true
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        result = get_mentor_run_on_wip("wip_mentor")

    assert result is True

    Path(config_path).unlink()


def test_get_mentor_run_on_wip_false() -> None:
    """Test get_mentor_run_on_wip returns False for mentors without run_on_wip."""
    yaml_content = """
mentors:
  - name: regular_mentor
    prompt: Regular mentor.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        result = get_mentor_run_on_wip("regular_mentor")

    assert result is False

    Path(config_path).unlink()


def test_get_mentor_run_on_wip_nonexistent() -> None:
    """Test get_mentor_run_on_wip returns False for nonexistent mentors."""
    yaml_content = """
mentors:
  - name: existing_mentor
    prompt: Existing mentor.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("mentor_config._get_config_path", return_value=config_path):
        result = get_mentor_run_on_wip("nonexistent_mentor")

    assert result is False

    Path(config_path).unlink()
