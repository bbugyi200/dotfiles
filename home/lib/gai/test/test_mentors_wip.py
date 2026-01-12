"""Tests for the mentors module - WIP-related functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from ace.changespec import MentorEntry, MentorStatusLine
from ace.mentors import (
    _format_mentors_field,
    _format_profile_with_count,
    clear_mentor_wip_flags,
)
from mentor_config import MentorConfig, MentorProfileConfig

# Tests for WIP filtering


def test_format_profile_with_count_wip_filters_total() -> None:
    """Test that is_wip=True filters total to only run_on_wip mentors."""
    # Mock a profile with 3 mentors, only 1 has run_on_wip=True
    mock_profile = MentorProfileConfig(
        profile_name="test_profile",
        mentors=[
            MentorConfig(mentor_name="m1", prompt="p1", run_on_wip=True),
            MentorConfig(mentor_name="m2", prompt="p2", run_on_wip=False),
            MentorConfig(mentor_name="m3", prompt="p3", run_on_wip=False),
        ],
        file_globs=["*.py"],
    )

    def mock_get_profile(name: str) -> MentorProfileConfig | None:
        if name == "test_profile":
            return mock_profile
        return None

    with patch(
        "mentor_config.get_mentor_profile_by_name",
        side_effect=mock_get_profile,
    ):
        # Without WIP: total should be 3
        result_normal = _format_profile_with_count("test_profile", None, is_wip=False)
        assert result_normal == "test_profile[0/3]"

        # With WIP: total should be 1 (only run_on_wip mentor)
        result_wip = _format_profile_with_count("test_profile", None, is_wip=True)
        assert result_wip == "test_profile[0/1]"


def test_format_profile_with_count_wip_filters_started() -> None:
    """Test that is_wip=True only counts started mentors with run_on_wip."""
    # Mock a profile with 3 mentors, only 1 has run_on_wip=True
    mock_profile = MentorProfileConfig(
        profile_name="test_profile",
        mentors=[
            MentorConfig(mentor_name="quick", prompt="p1", run_on_wip=True),
            MentorConfig(mentor_name="full", prompt="p2", run_on_wip=False),
            MentorConfig(mentor_name="detailed", prompt="p3", run_on_wip=False),
        ],
        file_globs=["*.py"],
    )

    def mock_get_profile(name: str) -> MentorProfileConfig | None:
        if name == "test_profile":
            return mock_profile
        return None

    # Status lines for 2 mentors (1 with run_on_wip, 1 without)
    status_lines = [
        MentorStatusLine(
            profile_name="test_profile",
            mentor_name="quick",
            status="RUNNING",
        ),
        MentorStatusLine(
            profile_name="test_profile",
            mentor_name="full",
            status="RUNNING",
        ),
    ]

    with patch(
        "mentor_config.get_mentor_profile_by_name",
        side_effect=mock_get_profile,
    ):
        # Without WIP: should count both started mentors (2/3)
        result_normal = _format_profile_with_count(
            "test_profile", status_lines, is_wip=False
        )
        assert result_normal == "test_profile[2/3]"

        # With WIP: should only count the run_on_wip mentor (1/1)
        result_wip = _format_profile_with_count(
            "test_profile", status_lines, is_wip=True
        )
        assert result_wip == "test_profile[1/1]"


def test_format_mentors_field_wip_hides_non_wip_profiles() -> None:
    """Test that WIP entries hide profiles without run_on_wip mentors."""
    # Profile A has run_on_wip mentors, Profile B does not
    profiles = {
        "profile_a": MentorProfileConfig(
            profile_name="profile_a",
            mentors=[MentorConfig(mentor_name="m1", prompt="p1", run_on_wip=True)],
            file_globs=["*.py"],
        ),
        "profile_b": MentorProfileConfig(
            profile_name="profile_b",
            mentors=[MentorConfig(mentor_name="m2", prompt="p2", run_on_wip=False)],
            file_globs=["*.js"],
        ),
    }

    def mock_get_profile(name: str) -> MentorProfileConfig | None:
        return profiles.get(name)

    def mock_has_wip(name: str) -> bool:
        profile = profiles.get(name)
        if profile is None:
            return False
        return any(m.run_on_wip for m in profile.mentors)

    entry = MentorEntry(
        entry_id="1",
        profiles=["profile_a", "profile_b"],
        status_lines=None,
        is_wip=True,
    )

    with patch("mentor_config.profile_has_wip_mentors", side_effect=mock_has_wip):
        with patch(
            "mentor_config.get_mentor_profile_by_name",
            side_effect=mock_get_profile,
        ):
            lines = _format_mentors_field([entry])
            content = "".join(lines)

            # profile_a should be visible, profile_b should be hidden
            assert "profile_a" in content
            assert "profile_b" not in content
            # Should still have #WIP suffix
            assert "#WIP" in content


def test_format_mentors_field_wip_skips_entry_with_no_wip_profiles() -> None:
    """Test that WIP entries are skipped entirely if no profiles have WIP mentors."""
    # Profile only has non-WIP mentors
    profiles = {
        "profile_a": MentorProfileConfig(
            profile_name="profile_a",
            mentors=[MentorConfig(mentor_name="m1", prompt="p1", run_on_wip=False)],
            file_globs=["*.py"],
        ),
    }

    def mock_has_wip(name: str) -> bool:
        profile = profiles.get(name)
        if profile is None:
            return False
        return any(m.run_on_wip for m in profile.mentors)

    entry = MentorEntry(
        entry_id="1",
        profiles=["profile_a"],
        status_lines=None,
        is_wip=True,
    )

    with patch("mentor_config.profile_has_wip_mentors", side_effect=mock_has_wip):
        lines = _format_mentors_field([entry])
        # Should only have the header, no entries
        assert lines == ["MENTORS:\n"]


def test_format_mentors_field_non_wip_shows_all_profiles() -> None:
    """Test that non-WIP entries show all profiles regardless of run_on_wip."""
    # Profile A has run_on_wip mentors, Profile B does not
    profiles = {
        "profile_a": MentorProfileConfig(
            profile_name="profile_a",
            mentors=[MentorConfig(mentor_name="m1", prompt="p1", run_on_wip=True)],
            file_globs=["*.py"],
        ),
        "profile_b": MentorProfileConfig(
            profile_name="profile_b",
            mentors=[MentorConfig(mentor_name="m2", prompt="p2", run_on_wip=False)],
            file_globs=["*.js"],
        ),
    }

    def mock_get_profile(name: str) -> MentorProfileConfig | None:
        return profiles.get(name)

    entry = MentorEntry(
        entry_id="1",
        profiles=["profile_a", "profile_b"],
        status_lines=None,
        is_wip=False,  # Not WIP
    )

    with patch(
        "mentor_config.get_mentor_profile_by_name",
        side_effect=mock_get_profile,
    ):
        lines = _format_mentors_field([entry])
        content = "".join(lines)

        # Both profiles should be visible
        assert "profile_a" in content
        assert "profile_b" in content
        # No #WIP suffix
        assert "#WIP" not in content


# Tests for clear_mentor_wip_flags


def test_clear_mentor_wip_flags_clears_last_only() -> None:
    """Test that only the highest entry_id WIP entry has #WIP cleared."""
    content = """NAME: test-cl
STATUS: WIP
COMMITS:
  (1) First commit
  (2) Second commit
  (3) Third commit
MENTORS:
  (1) feature #WIP
  (2) feature #WIP
  (3) feature #WIP
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    # Mock profile functions to allow any profile
    with patch("mentor_config.profile_has_wip_mentors", return_value=True):
        with patch("mentor_config.get_mentor_profile_by_name", return_value=None):
            result = clear_mentor_wip_flags(file_path, "test-cl")
            assert result is True

    with open(file_path) as f:
        updated_content = f.read()

    # Only entry (3) should have #WIP cleared
    lines = updated_content.split("\n")
    mentors_section = [ln for ln in lines if ln.strip().startswith("(")]
    assert any("(1)" in ln and "#WIP" in ln for ln in mentors_section)
    assert any("(2)" in ln and "#WIP" in ln for ln in mentors_section)
    assert any("(3)" in ln and "#WIP" not in ln for ln in mentors_section)

    Path(file_path).unlink()


def test_clear_mentor_wip_flags_single_entry() -> None:
    """Test clearing WIP from single entry."""
    content = """NAME: test-cl
STATUS: WIP
MENTORS:
  (1) feature #WIP
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    with patch("mentor_config.profile_has_wip_mentors", return_value=True):
        with patch("mentor_config.get_mentor_profile_by_name", return_value=None):
            result = clear_mentor_wip_flags(file_path, "test-cl")
            assert result is True

    with open(file_path) as f:
        updated_content = f.read()

    assert "#WIP" not in updated_content
    assert "(1) feature" in updated_content

    Path(file_path).unlink()


def test_clear_mentor_wip_flags_no_wip_entries() -> None:
    """Test that nothing changes when no WIP entries exist."""
    content = """NAME: test-cl
STATUS: Drafted
MENTORS:
  (1) feature
  (2) tests
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    with patch("mentor_config.get_mentor_profile_by_name", return_value=None):
        result = clear_mentor_wip_flags(file_path, "test-cl")
        assert result is True

    with open(file_path) as f:
        updated_content = f.read()

    # Should be unchanged (profiles preserved without counts)
    assert "(1) feature" in updated_content
    assert "(2) tests" in updated_content

    Path(file_path).unlink()


def test_clear_mentor_wip_flags_mixed_entries() -> None:
    """Test with a mix of WIP and non-WIP entries."""
    content = """NAME: test-cl
STATUS: WIP
MENTORS:
  (1) feature
  (2) tests #WIP
  (3) perf #WIP
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    with patch("mentor_config.profile_has_wip_mentors", return_value=True):
        with patch("mentor_config.get_mentor_profile_by_name", return_value=None):
            result = clear_mentor_wip_flags(file_path, "test-cl")
            assert result is True

    with open(file_path) as f:
        updated_content = f.read()

    # Entry (1) never had #WIP, should remain without
    # Entry (2) should keep #WIP (not the highest)
    # Entry (3) should have #WIP cleared (highest WIP entry)
    lines = updated_content.split("\n")
    mentors_lines = [ln for ln in lines if ln.strip().startswith("(")]
    assert any("(1)" in ln and "#WIP" not in ln for ln in mentors_lines)
    assert any("(2)" in ln and "#WIP" in ln for ln in mentors_lines)
    assert any("(3)" in ln and "#WIP" not in ln for ln in mentors_lines)

    Path(file_path).unlink()


def test_clear_mentor_wip_flags_proposal_entries() -> None:
    """Test with proposal entries (e.g., 2a, 2b)."""
    content = """NAME: test-cl
STATUS: WIP
MENTORS:
  (1) feature #WIP
  (2) feature #WIP
  (2a) feature #WIP
  (2b) feature #WIP
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    with patch("mentor_config.profile_has_wip_mentors", return_value=True):
        with patch("mentor_config.get_mentor_profile_by_name", return_value=None):
            result = clear_mentor_wip_flags(file_path, "test-cl")
            assert result is True

    with open(file_path) as f:
        updated_content = f.read()

    # Entry (2b) is the highest (2, "b") > (2, "a") > (2, "") > (1, "")
    # So (2b) should have #WIP cleared, others should keep it
    lines = updated_content.split("\n")
    mentors_lines = [ln for ln in lines if ln.strip().startswith("(")]
    assert any("(1)" in ln and "#WIP" in ln for ln in mentors_lines)
    assert any("(2) " in ln and "#WIP" in ln for ln in mentors_lines)
    assert any("(2a)" in ln and "#WIP" in ln for ln in mentors_lines)
    assert any("(2b)" in ln and "#WIP" not in ln for ln in mentors_lines)

    Path(file_path).unlink()


def test_clear_mentor_wip_flags_wrong_changespec() -> None:
    """Test that other ChangeSpecs are not affected."""
    content = """NAME: other-cl
STATUS: WIP
MENTORS:
  (1) feature #WIP

NAME: test-cl
STATUS: WIP
MENTORS:
  (1) feature #WIP
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    with patch("mentor_config.profile_has_wip_mentors", return_value=True):
        with patch("mentor_config.get_mentor_profile_by_name", return_value=None):
            result = clear_mentor_wip_flags(file_path, "test-cl")
            assert result is True

    with open(file_path) as f:
        updated_content = f.read()

    # other-cl should still have #WIP
    # test-cl should have #WIP cleared
    # Split by NAME: to check each section
    other_cl_start = updated_content.find("NAME: other-cl")
    test_cl_start = updated_content.find("NAME: test-cl")
    other_cl_section = updated_content[other_cl_start:test_cl_start]
    test_cl_section = updated_content[test_cl_start:]

    assert "#WIP" in other_cl_section
    assert "#WIP" not in test_cl_section

    Path(file_path).unlink()


def test_clear_mentor_wip_flags_no_mentors() -> None:
    """Test that function returns True when no mentors exist."""
    content = """NAME: test-cl
STATUS: Drafted
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    result = clear_mentor_wip_flags(file_path, "test-cl")
    assert result is True

    Path(file_path).unlink()


def test_clear_mentor_wip_flags_changespec_not_found() -> None:
    """Test that function returns True when changespec not found."""
    content = """NAME: other-cl
STATUS: Drafted
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    result = clear_mentor_wip_flags(file_path, "nonexistent-cl")
    assert result is True

    Path(file_path).unlink()
