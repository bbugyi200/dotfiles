"""Tests for the mentor_config module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from mentor_config import (
    MentorConfig,
    _load_mentors,
    get_available_mentor_names,
    get_mentor_by_name,
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
