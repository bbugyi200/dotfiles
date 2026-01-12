"""Tests for the mentors module - MENTORS field operations."""

import tempfile
from pathlib import Path

from ace.changespec import MentorEntry, MentorStatusLine
from ace.mentors import (
    _apply_mentors_update,
    _format_mentors_field,
    add_mentor_entry,
    clear_mentor_wip_flags,
    set_mentor_status,
)


def test_format_mentors_field_empty() -> None:
    """Test formatting empty mentors list."""
    lines = _format_mentors_field([])
    assert lines == []


def test_format_profile_with_count_unknown_profile() -> None:
    """Test formatting profile with count when profile is not in config.

    When a profile is not found in the config, it should fall back to
    just the profile name without counts.
    """
    from ace.mentors import _format_profile_with_count

    # Use a profile name that doesn't exist in the config
    result = _format_profile_with_count("nonexistent_profile_xyz", None)
    # Should return just the profile name without counts
    assert result == "nonexistent_profile_xyz"


def test_format_profile_with_count_with_status_lines() -> None:
    """Test formatting profile with count when status lines exist."""
    from ace.mentors import _format_profile_with_count

    # Create status lines that reference the profile
    status_lines = [
        MentorStatusLine(
            profile_name="test_profile",
            mentor_name="mentor1",
            status="RUNNING",
        ),
        MentorStatusLine(
            profile_name="test_profile",
            mentor_name="mentor2",
            status="PASSED",
        ),
        MentorStatusLine(
            profile_name="other_profile",
            mentor_name="mentor3",
            status="PASSED",
        ),
    ]
    # This should count 2 started mentors for test_profile
    # (profile may not exist in config, so fallback to name)
    result = _format_profile_with_count("test_profile", status_lines)
    # If profile not found, returns just the name
    assert "test_profile" in result


def test_format_mentors_field_single_entry_no_status() -> None:
    """Test formatting single entry without status lines.

    Note: Format now includes [started/total] counts per profile.
    """
    entry = MentorEntry(
        entry_id="1",
        profiles=["feature", "tests"],
        status_lines=None,
    )
    lines = _format_mentors_field([entry])
    assert lines[0] == "MENTORS:\n"
    # Check that entry header contains profile names (with or without counts)
    assert "(1)" in lines[1]
    assert "feature" in lines[1]
    assert "tests" in lines[1]


def test_format_mentors_field_with_status_lines() -> None:
    """Test formatting entry with status lines."""
    entry = MentorEntry(
        entry_id="2",
        profiles=["feature"],
        status_lines=[
            MentorStatusLine(
                profile_name="feature",
                mentor_name="complete",
                status="PASSED",
                duration="1h2m3s",
            ),
            MentorStatusLine(
                profile_name="feature",
                mentor_name="soundness",
                status="RUNNING",
                suffix="mentor_soundness-123-240601_1530",
                suffix_type="running_agent",
            ),
        ],
    )
    lines = _format_mentors_field([entry])
    assert "MENTORS:\n" in lines
    # Check entry header contains profile (with or without counts)
    assert any("(2)" in line and "feature" in line for line in lines)
    # Check status lines are present
    assert any("PASSED" in line for line in lines)
    assert any("RUNNING" in line for line in lines)


def test_format_mentors_field_running_no_timestamp_prefix() -> None:
    """Test that RUNNING status lines don't show timestamp prefix.

    The timestamp is stored in the model but should not be displayed
    for RUNNING mentors - only for PASSED/FAILED.
    """
    entry = MentorEntry(
        entry_id="1",
        profiles=["feature"],
        status_lines=[
            MentorStatusLine(
                profile_name="feature",
                mentor_name="complete",
                status="RUNNING",
                timestamp="260107_141615",
                suffix="mentor_complete-12345-260107_141615",
                suffix_type="running_agent",
            ),
            MentorStatusLine(
                profile_name="feature",
                mentor_name="soundness",
                status="PASSED",
                timestamp="260107_140027",
                duration="5m30s",
            ),
        ],
    )
    lines = _format_mentors_field([entry])
    content = "".join(lines)

    # RUNNING line should NOT have timestamp prefix
    assert "| feature:complete - RUNNING" in content
    assert "[260107_141615] feature:complete" not in content

    # PASSED line SHOULD have timestamp prefix
    assert "[260107_140027] feature:soundness - PASSED" in content


def test_format_mentors_field_with_error_suffix() -> None:
    """Test formatting with error suffix."""
    entry = MentorEntry(
        entry_id="1",
        profiles=["test"],
        status_lines=[
            MentorStatusLine(
                profile_name="test",
                mentor_name="complete",
                status="FAILED",
                suffix="Connection error",
                suffix_type="error",
            ),
        ],
    )
    lines = _format_mentors_field([entry])
    # Should contain error marker
    assert any("!:" in line for line in lines)


def test_apply_mentors_update_new_field() -> None:
    """Test applying mentors to a file without existing MENTORS field."""
    lines = [
        "NAME: test-cl\n",
        "STATUS: Drafted\n",
        "DESCRIPTION:\n",
        "  Test description\n",
    ]
    entry = MentorEntry(entry_id="1", profiles=["test"], status_lines=None)
    updated = _apply_mentors_update(lines, "test-cl", [entry])
    # Should contain MENTORS field at the end
    content = "".join(updated)
    assert "MENTORS:" in content
    assert "(1) test" in content


def test_apply_mentors_update_replace_existing() -> None:
    """Test replacing existing MENTORS field."""
    lines = [
        "NAME: test-cl\n",
        "STATUS: Drafted\n",
        "MENTORS:\n",
        "  (1) old_profile\n",
    ]
    entry = MentorEntry(entry_id="2", profiles=["new_profile"], status_lines=None)
    updated = _apply_mentors_update(lines, "test-cl", [entry])
    content = "".join(updated)
    assert "(2) new_profile" in content
    assert "old_profile" not in content


def test_add_mentor_entry_new() -> None:
    """Test adding a new mentor entry to a file."""
    content = """NAME: test-cl
STATUS: Drafted
DESCRIPTION:
  Test description
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    result = add_mentor_entry(file_path, "test-cl", "1", ["feature"])

    assert result is True

    # Read and verify
    with open(file_path) as f:
        updated_content = f.read()

    assert "MENTORS:" in updated_content
    assert "(1) feature" in updated_content

    Path(file_path).unlink()


def test_add_mentor_entry_merge_profiles() -> None:
    """Test adding profiles to existing mentor entry."""
    content = """NAME: test-cl
STATUS: Drafted
MENTORS:
  (1) feature
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    result = add_mentor_entry(file_path, "test-cl", "1", ["tests"])

    assert result is True

    # Read and verify profiles are merged
    with open(file_path) as f:
        updated_content = f.read()

    # Should have both profiles
    assert "feature" in updated_content
    assert "tests" in updated_content

    Path(file_path).unlink()


def test_set_mentor_status_new() -> None:
    """Test setting mentor status for new mentor."""
    content = """NAME: test-cl
STATUS: Drafted
MENTORS:
  (1) feature
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    result = set_mentor_status(
        file_path,
        "test-cl",
        "1",
        "feature",
        "complete",
        status="RUNNING",
        suffix="mentor_complete-123",
        suffix_type="running_agent",
    )

    assert result is True

    with open(file_path) as f:
        updated_content = f.read()

    assert "feature:complete" in updated_content
    assert "RUNNING" in updated_content

    Path(file_path).unlink()


def test_set_mentor_status_update_existing() -> None:
    """Test updating existing mentor status."""
    content = """NAME: test-cl
STATUS: Drafted
MENTORS:
  (1) feature
      | feature:complete - RUNNING - (@: mentor_complete-123)
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    result = set_mentor_status(
        file_path,
        "test-cl",
        "1",
        "feature",
        "complete",
        status="PASSED",
        duration="1h2m3s",
    )

    assert result is True

    with open(file_path) as f:
        updated_content = f.read()

    assert "PASSED" in updated_content
    assert "1h2m3s" in updated_content

    Path(file_path).unlink()


def test_format_mentors_field_multiple_entries() -> None:
    """Test formatting multiple mentor entries."""
    entries = [
        MentorEntry(entry_id="1", profiles=["feature"], status_lines=None),
        MentorEntry(entry_id="2", profiles=["tests", "perf"], status_lines=None),
    ]
    lines = _format_mentors_field(entries)
    content = "".join(lines)
    # Check that entries are present (with or without counts)
    assert "(1)" in content and "feature" in content
    assert "(2)" in content and "tests" in content and "perf" in content


def test_format_mentors_field_with_plain_suffix() -> None:
    """Test formatting with plain suffix (no type)."""
    entry = MentorEntry(
        entry_id="1",
        profiles=["test"],
        status_lines=[
            MentorStatusLine(
                profile_name="test",
                mentor_name="complete",
                status="PASSED",
                suffix="some_suffix",
                suffix_type=None,  # Plain suffix
            ),
        ],
    )
    lines = _format_mentors_field([entry])
    content = "".join(lines)
    assert "some_suffix" in content


def test_apply_mentors_update_wrong_changespec() -> None:
    """Test that update doesn't affect other changespecs."""
    lines = [
        "NAME: other-cl\n",
        "STATUS: Drafted\n",
        "---\n",
        "NAME: test-cl\n",
        "STATUS: Mailed\n",
    ]
    entry = MentorEntry(entry_id="1", profiles=["feature"], status_lines=None)
    updated = _apply_mentors_update(lines, "test-cl", [entry])
    content = "".join(updated)
    # MENTORS should be added to test-cl, not other-cl
    assert content.count("MENTORS:") == 1


def test_set_mentor_status_creates_entry_if_missing() -> None:
    """Test that set_mentor_status creates entry if it doesn't exist."""
    content = """NAME: test-cl
STATUS: Drafted
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    result = set_mentor_status(
        file_path,
        "test-cl",
        "1",
        "feature",
        "complete",
        status="RUNNING",
    )

    assert result is True

    with open(file_path) as f:
        updated_content = f.read()

    assert "MENTORS:" in updated_content
    assert "feature:complete" in updated_content
    assert "RUNNING" in updated_content

    Path(file_path).unlink()


# Tests for WIP filtering


def test_format_profile_with_count_wip_filters_total() -> None:
    """Test that is_wip=True filters total to only run_on_wip mentors."""
    from unittest.mock import patch

    from ace.mentors import _format_profile_with_count
    from mentor_config import MentorConfig, MentorProfileConfig

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
    from unittest.mock import patch

    from ace.mentors import _format_profile_with_count
    from mentor_config import MentorConfig, MentorProfileConfig

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
    from unittest.mock import patch

    from mentor_config import MentorConfig, MentorProfileConfig

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
    from unittest.mock import patch

    from mentor_config import MentorConfig, MentorProfileConfig

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
    from unittest.mock import patch

    from mentor_config import MentorConfig, MentorProfileConfig

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
    from unittest.mock import patch

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
    from unittest.mock import patch

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
    from unittest.mock import patch

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
    from unittest.mock import patch

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
    from unittest.mock import patch

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
    from unittest.mock import patch

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
