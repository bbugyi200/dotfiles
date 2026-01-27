"""Tests for MentorConfig and MentorProfileConfig dataclass validation."""

import pytest
from mentor_config import MentorConfig, MentorProfileConfig


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
