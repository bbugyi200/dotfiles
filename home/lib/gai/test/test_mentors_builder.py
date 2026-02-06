"""Tests for the MENTORS section builder hint support."""

import os
from unittest.mock import patch

from ace.changespec import ChangeSpec, CommitEntry, MentorEntry, MentorStatusLine
from ace.tui.widgets.hint_tracker import HintTracker
from ace.tui.widgets.mentors_builder import build_mentors_section
from rich.text import Text


def _make_changespec(
    name: str = "test_feature",
    commits: list[CommitEntry] | None = None,
    mentors: list[MentorEntry] | None = None,
) -> ChangeSpec:
    """Create a minimal ChangeSpec for testing."""
    return ChangeSpec(
        name=name,
        description="Test description",
        parent=None,
        cl=None,
        status="Drafted",
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
        commits=commits,
        mentors=mentors,
    )


def _make_hint_tracker(counter: int = 0) -> HintTracker:
    """Create a fresh HintTracker for testing."""
    return HintTracker(
        counter=counter,
        mappings={},
        hook_hint_to_idx={},
        hint_to_entry_id={},
        mentor_hint_to_info={},
    )


@patch(
    "ace.display_helpers.format_profile_with_count",
    return_value="prof[1/1]",
)
@patch("mentor_config.profile_has_wip_mentors", return_value=True)
def test_error_file_path_suffix_gets_hint(_mock_wip: object, _mock_fmt: object) -> None:
    """Error suffix that is a file path gets a hint number when with_hints=True."""
    error_path = "~/.gai/mentors/fixit_wells-260206_100530.txt"
    msl = MentorStatusLine(
        profile_name="prof",
        mentor_name="fixit_wells",
        status="FAILED",
        timestamp="260206_100530",
        duration="0h1m30s",
        suffix=error_path,
        suffix_type="error",
    )
    mentor_entry = MentorEntry(
        entry_id="3",
        profiles=["prof"],
        status_lines=[msl],
    )
    changespec = _make_changespec(
        commits=[CommitEntry(number=3, note="current")],
        mentors=[mentor_entry],
    )

    text = Text()
    tracker = build_mentors_section(
        text,
        changespec,
        mentors_collapsed=False,
        with_hints=True,
        hint_tracker=_make_hint_tracker(counter=5),
    )

    # The chat path hint (for FAILED status) should be hint 5
    # The error file path hint should be hint 6
    assert 6 in tracker.mappings
    expected_path = os.path.expanduser(error_path)
    assert tracker.mappings[6] == expected_path
    assert tracker.counter == 7

    # Verify the hint number appears in the rendered text
    plain = text.plain
    assert "[6]" in plain
    assert error_path in plain


@patch(
    "ace.display_helpers.format_profile_with_count",
    return_value="prof[1/1]",
)
@patch("mentor_config.profile_has_wip_mentors", return_value=True)
def test_error_non_path_suffix_no_hint(_mock_wip: object, _mock_fmt: object) -> None:
    """Error suffix that is NOT a file path does not get a hint."""
    msl = MentorStatusLine(
        profile_name="prof",
        mentor_name="fixit_wells",
        status="FAILED",
        timestamp="260206_100530",
        duration="0h1m30s",
        suffix="Connection error",
        suffix_type="error",
    )
    mentor_entry = MentorEntry(
        entry_id="3",
        profiles=["prof"],
        status_lines=[msl],
    )
    changespec = _make_changespec(
        commits=[CommitEntry(number=3, note="current")],
        mentors=[mentor_entry],
    )

    text = Text()
    tracker = build_mentors_section(
        text,
        changespec,
        mentors_collapsed=False,
        with_hints=True,
        hint_tracker=_make_hint_tracker(counter=5),
    )

    # Hint 5 is for the chat path (FAILED status line), no extra hint for the error suffix
    assert tracker.counter == 6
    # The error text should appear but without a hint number for it
    plain = text.plain
    assert "Connection error" in plain


@patch(
    "ace.display_helpers.format_profile_with_count",
    return_value="prof[1/1]",
)
@patch("mentor_config.profile_has_wip_mentors", return_value=True)
def test_error_file_path_no_hint_without_with_hints(
    _mock_wip: object, _mock_fmt: object
) -> None:
    """Error file path suffix does NOT get a hint when with_hints=False."""
    error_path = "~/.gai/mentors/fixit_wells-260206_100530.txt"
    msl = MentorStatusLine(
        profile_name="prof",
        mentor_name="fixit_wells",
        status="FAILED",
        timestamp="260206_100530",
        duration="0h1m30s",
        suffix=error_path,
        suffix_type="error",
    )
    mentor_entry = MentorEntry(
        entry_id="3",
        profiles=["prof"],
        status_lines=[msl],
    )
    changespec = _make_changespec(
        commits=[CommitEntry(number=3, note="current")],
        mentors=[mentor_entry],
    )

    text = Text()
    tracker = build_mentors_section(
        text,
        changespec,
        mentors_collapsed=False,
        with_hints=False,
        hint_tracker=_make_hint_tracker(counter=0),
    )

    # No hints should be generated when with_hints=False
    assert tracker.counter == 0
    assert len(tracker.mappings) == 0


@patch(
    "ace.display_helpers.format_profile_with_count",
    return_value="prof[1/1]",
)
@patch("mentor_config.profile_has_wip_mentors", return_value=True)
def test_error_absolute_path_suffix_gets_hint(
    _mock_wip: object, _mock_fmt: object
) -> None:
    """Error suffix with absolute path (starting with /) gets a hint."""
    error_path = "/home/user/.gai/mentors/fixit_wells-260206_100530.txt"
    msl = MentorStatusLine(
        profile_name="prof",
        mentor_name="fixit_wells",
        status="FAILED",
        timestamp="260206_100530",
        duration="0h1m30s",
        suffix=error_path,
        suffix_type="error",
    )
    mentor_entry = MentorEntry(
        entry_id="3",
        profiles=["prof"],
        status_lines=[msl],
    )
    changespec = _make_changespec(
        commits=[CommitEntry(number=3, note="current")],
        mentors=[mentor_entry],
    )

    text = Text()
    tracker = build_mentors_section(
        text,
        changespec,
        mentors_collapsed=False,
        with_hints=True,
        hint_tracker=_make_hint_tracker(counter=0),
    )

    # Hint 0 is the chat path, hint 1 is the error file path
    assert 1 in tracker.mappings
    assert tracker.mappings[1] == error_path
    assert tracker.counter == 2
