"""Tests for the ace TUI (Textual app)."""

from unittest.mock import patch

import pytest
from ace.changespec import ChangeSpec, CommentEntry, CommitEntry, HookEntry
from ace.query import QueryParseError
from ace.tui import AceApp
from ace.tui.modals import QueryEditModal
from textual.widgets import Input


def _make_changespec(
    name: str = "test_feature",
    description: str = "Test description",
    status: str = "Drafted",
    cl: str | None = None,
    parent: str | None = None,
    file_path: str = "/tmp/test.gp",
    commits: list[CommitEntry] | None = None,
    hooks: list[HookEntry] | None = None,
    comments: list[CommentEntry] | None = None,
) -> ChangeSpec:
    """Create a mock ChangeSpec for testing."""
    return ChangeSpec(
        name=name,
        description=description,
        parent=parent,
        cl=cl,
        status=status,
        test_targets=None,
        kickstart=None,
        file_path=file_path,
        line_number=1,
        commits=commits,
        hooks=hooks,
        comments=comments,
    )


# --- Initialization Tests ---


async def test_app_initialization_default_query() -> None:
    """Test AceApp initializes with default query string."""
    mock_changespecs = [_make_changespec()]
    with patch("ace.tui.app.find_all_changespecs", return_value=mock_changespecs):
        app = AceApp()
        # Default query is '"(!: "'
        assert app.query_string == '"(!: "'
        assert app.parsed_query is not None


async def test_app_initialization_custom_query() -> None:
    """Test AceApp initializes with a custom query string."""
    mock_changespecs = [_make_changespec(name="feature_a")]
    with patch("ace.tui.app.find_all_changespecs", return_value=mock_changespecs):
        app = AceApp(query='"feature"')
        assert app.query_string == '"feature"'
        assert app.parsed_query is not None


def test_app_initialization_invalid_query() -> None:
    """Test AceApp raises QueryParseError for invalid query."""
    with pytest.raises(QueryParseError):
        AceApp(query='"unclosed')


# --- Navigation Tests ---


async def test_navigation_next_key() -> None:
    """Test 'j' key navigates to next changespec."""
    mock_changespecs = [
        _make_changespec(name="feature_a"),
        _make_changespec(name="feature_b"),
        _make_changespec(name="feature_c"),
    ]
    with patch("ace.tui.app.find_all_changespecs", return_value=mock_changespecs):
        app = AceApp(query='"feature"')
        async with app.run_test() as pilot:
            # Initial state
            assert app.current_idx == 0

            # Press 'j' to go to next
            await pilot.press("j")
            assert app.current_idx == 1

            # Press 'j' again
            await pilot.press("j")
            assert app.current_idx == 2


async def test_navigation_prev_key() -> None:
    """Test 'k' key navigates to previous changespec."""
    mock_changespecs = [
        _make_changespec(name="feature_a"),
        _make_changespec(name="feature_b"),
        _make_changespec(name="feature_c"),
    ]
    with patch("ace.tui.app.find_all_changespecs", return_value=mock_changespecs):
        app = AceApp(query='"feature"')
        async with app.run_test() as pilot:
            # Start at index 2 by pressing 'j' twice
            await pilot.press("j")
            await pilot.press("j")
            assert app.current_idx == 2

            # Press 'k' to go to previous
            await pilot.press("k")
            assert app.current_idx == 1

            # Press 'k' again
            await pilot.press("k")
            assert app.current_idx == 0


async def test_navigation_next_at_end() -> None:
    """Test 'j' key at last item cycles to first item."""
    mock_changespecs = [
        _make_changespec(name="feature_a"),
        _make_changespec(name="feature_b"),
    ]
    with patch("ace.tui.app.find_all_changespecs", return_value=mock_changespecs):
        app = AceApp(query='"feature"')
        async with app.run_test() as pilot:
            # Go to last item
            await pilot.press("j")
            assert app.current_idx == 1

            # Press 'j' at end should cycle to first item
            await pilot.press("j")
            assert app.current_idx == 0


async def test_navigation_prev_at_start() -> None:
    """Test 'k' key at first item cycles to last item."""
    mock_changespecs = [
        _make_changespec(name="feature_a"),
        _make_changespec(name="feature_b"),
    ]
    with patch("ace.tui.app.find_all_changespecs", return_value=mock_changespecs):
        app = AceApp(query='"feature"')
        async with app.run_test() as pilot:
            # Already at index 0
            assert app.current_idx == 0

            # Press 'k' at start should cycle to last item
            await pilot.press("k")
            assert app.current_idx == 1


# --- Query Edit Modal Tests ---


async def test_query_edit_modal_opens() -> None:
    """Test '/' key opens QueryEditModal."""
    mock_changespecs = [_make_changespec()]
    with patch("ace.tui.app.find_all_changespecs", return_value=mock_changespecs):
        app = AceApp(query='"test"')
        async with app.run_test() as pilot:
            # Press '/' to open modal
            await pilot.press("slash")

            # Verify modal is on screen stack
            assert len(app.screen_stack) > 1
            assert isinstance(app.screen_stack[-1], QueryEditModal)


async def test_query_edit_modal_cancel() -> None:
    """Test pressing Escape cancels query edit modal."""
    mock_changespecs = [_make_changespec()]
    with patch("ace.tui.app.find_all_changespecs", return_value=mock_changespecs):
        app = AceApp(query='"original"')
        async with app.run_test() as pilot:
            original_query = app.query_string

            # Open modal
            await pilot.press("slash")
            assert len(app.screen_stack) > 1

            # Press Escape to cancel
            await pilot.press("escape")

            # Modal should be closed and query unchanged
            assert len(app.screen_stack) == 1
            assert app.query_string == original_query


async def test_query_edit_modal_apply() -> None:
    """Test applying a new query updates query_string."""
    mock_changespecs = [
        _make_changespec(name="feature_a"),
        _make_changespec(name="other_b"),
    ]
    with patch("ace.tui.app.find_all_changespecs", return_value=mock_changespecs):
        app = AceApp(query='"feature"')
        async with app.run_test() as pilot:
            # Initial state - should have 1 changespec matching "feature"
            assert app.query_string == '"feature"'

            # Open modal
            await pilot.press("slash")
            assert isinstance(app.screen_stack[-1], QueryEditModal)

            # Get the input widget and set new query value
            modal = app.screen_stack[-1]
            input_widget = modal.query_one("#query-input", Input)
            input_widget.value = '"other"'

            # Click Apply button
            await pilot.click("#apply")

            # Query should be updated
            assert app.query_string == '"other"'


async def test_query_edit_modal_invalid_query() -> None:
    """Test invalid query shows error notification."""
    mock_changespecs = [_make_changespec()]
    with patch("ace.tui.app.find_all_changespecs", return_value=mock_changespecs):
        app = AceApp(query='"valid"')
        async with app.run_test() as pilot:
            original_query = app.query_string

            # Open modal
            await pilot.press("slash")
            modal = app.screen_stack[-1]

            # Set invalid query (unclosed quote)
            input_widget = modal.query_one("#query-input", Input)
            input_widget.value = '"unclosed'

            # Click Apply
            await pilot.click("#apply")

            # Query should remain unchanged
            assert app.query_string == original_query


# --- Keybinding Footer Tests ---


def test_keybinding_footer_reword_visible_drafted_with_cl() -> None:
    """Test 'w' (reword) binding is visible for Drafted status with CL."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted", cl="123456")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "w" in binding_keys


def test_keybinding_footer_reword_visible_mailed_with_cl() -> None:
    """Test 'w' (reword) binding is visible for Mailed status with CL."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Mailed", cl="123456")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "w" in binding_keys


def test_keybinding_footer_reword_hidden_submitted() -> None:
    """Test 'w' (reword) binding is hidden for Submitted status."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Submitted", cl="123456")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "w" not in binding_keys


def test_keybinding_footer_reword_hidden_no_cl() -> None:
    """Test 'w' (reword) binding is hidden when CL is not set."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted", cl=None)

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "w" not in binding_keys


def test_keybinding_footer_reword_visible_with_ready_to_mail_suffix() -> None:
    """Test 'w' (reword) binding is visible for Drafted with READY TO MAIL suffix."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    # Status with suffix - base status is Drafted
    changespec = _make_changespec(status="Drafted - (!: READY TO MAIL)", cl="123456")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "w" in binding_keys


def test_keybinding_footer_reword_hidden_reverted() -> None:
    """Test 'w' (reword) binding is hidden for Reverted status."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Reverted", cl="123456")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "w" not in binding_keys


def test_keybinding_footer_diff_visible_with_cl() -> None:
    """Test 'd' (diff) binding is visible when CL is set."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted", cl="123456")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "d" in binding_keys


def test_keybinding_footer_diff_hidden_without_cl() -> None:
    """Test 'd' (diff) binding is hidden when CL is not set."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted", cl=None)

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "d" not in binding_keys


def test_keybinding_footer_mail_visible_ready_to_mail() -> None:
    """Test 'm' and 'f' bindings are visible with READY TO MAIL suffix."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted - (!: READY TO MAIL)", cl="123456")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "m" in binding_keys
    assert "f" in binding_keys


def test_keybinding_footer_mail_hidden_without_suffix() -> None:
    """Test 'm' and 'f' bindings are hidden without READY TO MAIL suffix."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted", cl="123456")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "m" not in binding_keys
    assert "f" not in binding_keys


def test_keybinding_footer_accept_visible_with_proposals() -> None:
    """Test 'a' (accept) binding is visible when proposed entries exist."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    commits = [CommitEntry(number=1, note="Test", proposal_letter="a")]
    changespec = _make_changespec(status="Drafted", commits=commits)

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "a" in binding_keys


def test_keybinding_footer_accept_hidden_without_proposals() -> None:
    """Test 'a' (accept) binding is hidden when no proposed entries."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    # Regular entry (not a proposal)
    commits = [CommitEntry(number=1, note="Test")]
    changespec = _make_changespec(status="Drafted", commits=commits)

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "a" not in binding_keys


def test_keybinding_footer_navigation_at_start() -> None:
    """Test navigation bindings at start of list."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    # At start (idx=0) with 3 items - should have 'j' but not 'k'
    bindings = footer._compute_available_bindings(changespec, 0, 3)
    binding_keys = [b[0] for b in bindings]

    assert "j" in binding_keys
    assert "k" not in binding_keys


def test_keybinding_footer_navigation_at_end() -> None:
    """Test navigation bindings at end of list."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    # At end (idx=2) with 3 items - should have 'k' but not 'j'
    bindings = footer._compute_available_bindings(changespec, 2, 3)
    binding_keys = [b[0] for b in bindings]

    assert "k" in binding_keys
    assert "j" not in binding_keys


def test_keybinding_footer_format_bindings() -> None:
    """Test bindings are formatted correctly."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    bindings = [("q", "quit"), ("j", "next")]

    text = footer._format_bindings(bindings)

    # Verify the text contains both bindings
    assert "j" in str(text)
    assert "next" in str(text)
    assert "q" in str(text)
    assert "quit" in str(text)


def test_keybinding_footer_navigation_in_middle() -> None:
    """Test navigation bindings in middle of list."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    # In middle (idx=1) with 3 items - should have both 'j' and 'k'
    bindings = footer._compute_available_bindings(changespec, 1, 3)
    binding_keys = [b[0] for b in bindings]

    assert "j" in binding_keys
    assert "k" in binding_keys


def test_keybinding_footer_always_has_quit() -> None:
    """Test 'q' (quit) binding is always visible."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "q" in binding_keys


def test_keybinding_footer_always_has_status() -> None:
    """Test 's' (status) binding is always visible."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "s" in binding_keys


def test_keybinding_footer_always_has_refresh() -> None:
    """Test 'y' (refresh) binding is always visible."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "y" in binding_keys


def test_keybinding_footer_always_has_view() -> None:
    """Test 'v' (view) binding is always visible."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "v" in binding_keys


def test_keybinding_footer_always_has_hooks() -> None:
    """Test 'h' (hooks) binding is always visible."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "h" in binding_keys


def test_keybinding_footer_always_has_edit_query() -> None:
    """Test '/' (edit query) binding is always visible."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "/" in binding_keys


def test_keybinding_footer_always_has_run_query() -> None:
    """Test 'R' (run query) binding is always visible."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "R" in binding_keys


def test_keybinding_footer_bindings_sorted() -> None:
    """Test bindings are sorted correctly."""
    from ace.tui.widgets import KeybindingFooter

    footer = KeybindingFooter()
    bindings = [("z", "last"), ("a", "first"), ("M", "mid")]

    text = footer._format_bindings(bindings)
    text_str = str(text)

    # Verify ordering: a should come before M which comes before z
    a_pos = text_str.find("a")
    m_pos = text_str.find("M")
    z_pos = text_str.find("z")

    assert a_pos < m_pos < z_pos


def test_get_base_status_drafted() -> None:
    """Test get_base_status returns correct base for Drafted."""
    from ace.changespec import get_base_status

    assert get_base_status("Drafted") == "Drafted"


def test_get_base_status_with_ready_to_mail_suffix() -> None:
    """Test get_base_status strips READY TO MAIL suffix."""
    from ace.changespec import get_base_status

    assert get_base_status("Drafted - (!: READY TO MAIL)") == "Drafted"


def test_get_base_status_submitted() -> None:
    """Test get_base_status returns correct base for Submitted."""
    from ace.changespec import get_base_status

    assert get_base_status("Submitted") == "Submitted"


def test_get_base_status_mailed() -> None:
    """Test get_base_status returns correct base for Mailed."""
    from ace.changespec import get_base_status

    assert get_base_status("Mailed") == "Mailed"


def test_get_base_status_reverted() -> None:
    """Test get_base_status returns correct base for Reverted."""
    from ace.changespec import get_base_status

    assert get_base_status("Reverted") == "Reverted"


def test_has_ready_to_mail_suffix_true() -> None:
    """Test has_ready_to_mail_suffix returns True for correct suffix."""
    from ace.changespec import has_ready_to_mail_suffix

    assert has_ready_to_mail_suffix("Drafted - (!: READY TO MAIL)") is True


def test_has_ready_to_mail_suffix_false() -> None:
    """Test has_ready_to_mail_suffix returns False for no suffix."""
    from ace.changespec import has_ready_to_mail_suffix

    assert has_ready_to_mail_suffix("Drafted") is False


def test_has_ready_to_mail_suffix_mailed_true() -> None:
    """Test has_ready_to_mail_suffix returns True for Mailed with suffix."""
    from ace.changespec import has_ready_to_mail_suffix

    assert has_ready_to_mail_suffix("Mailed - (!: READY TO MAIL)") is True


# --- _should_show_commits_drawers Tests ---


def test_should_show_commits_drawers_expanded() -> None:
    """All entries show drawers when expanded (commits_collapsed=False)."""
    from ace.tui.widgets.section_builders import _should_show_commits_drawers

    entry = CommitEntry(number=5, note="test")
    changespec = _make_changespec(
        commits=[
            CommitEntry(number=1, note="first"),
            CommitEntry(number=5, note="test"),
        ]
    )

    assert _should_show_commits_drawers(entry, changespec, commits_collapsed=False)


def test_should_show_commits_drawers_collapsed_entry_1_hidden() -> None:
    """Entry 1 hides drawers when collapsed."""
    from ace.tui.widgets.section_builders import _should_show_commits_drawers

    entry = CommitEntry(number=1, note="first")
    changespec = _make_changespec(
        commits=[
            CommitEntry(number=1, note="first"),
            CommitEntry(number=2, note="second"),
        ]
    )

    assert not _should_show_commits_drawers(entry, changespec, commits_collapsed=True)


def test_should_show_commits_drawers_collapsed_intermediate_hidden() -> None:
    """Intermediate entries hide drawers when collapsed."""
    from ace.tui.widgets.section_builders import _should_show_commits_drawers

    entry = CommitEntry(number=3, note="intermediate")
    changespec = _make_changespec(
        commits=[
            CommitEntry(number=1, note="first"),
            CommitEntry(number=3, note="intermediate"),
            CommitEntry(number=5, note="current"),
        ]
    )

    assert not _should_show_commits_drawers(entry, changespec, commits_collapsed=True)


def test_should_show_commits_drawers_collapsed_current_hidden() -> None:
    """Current (highest numeric) entry hides drawers when collapsed."""
    from ace.tui.widgets.section_builders import _should_show_commits_drawers

    entry = CommitEntry(number=8, note="current")
    changespec = _make_changespec(
        commits=[
            CommitEntry(number=1, note="first"),
            CommitEntry(number=8, note="current"),
        ]
    )

    assert not _should_show_commits_drawers(entry, changespec, commits_collapsed=True)


def test_should_show_commits_drawers_collapsed_proposal_for_max_shown() -> None:
    """Proposal entries for max ID show drawers when collapsed."""
    from ace.tui.widgets.section_builders import _should_show_commits_drawers

    entry = CommitEntry(number=8, note="proposal", proposal_letter="a")
    changespec = _make_changespec(
        commits=[
            CommitEntry(number=1, note="first"),
            CommitEntry(number=8, note="current"),
            CommitEntry(number=8, note="proposal", proposal_letter="a"),
        ]
    )

    assert _should_show_commits_drawers(entry, changespec, commits_collapsed=True)


def test_should_show_commits_drawers_collapsed_old_proposal_hidden() -> None:
    """Old proposal entries (not for max ID) hide drawers when collapsed."""
    from ace.tui.widgets.section_builders import _should_show_commits_drawers

    entry = CommitEntry(number=2, note="old proposal", proposal_letter="a")
    changespec = _make_changespec(
        commits=[
            CommitEntry(number=1, note="first"),
            CommitEntry(number=2, note="second"),
            CommitEntry(number=2, note="old proposal", proposal_letter="a"),
            CommitEntry(number=5, note="current"),
        ]
    )

    assert not _should_show_commits_drawers(entry, changespec, commits_collapsed=True)


def test_should_show_commits_drawers_collapsed_multiple_proposals_shown() -> None:
    """Multiple proposals for max ID all show drawers when collapsed."""
    from ace.tui.widgets.section_builders import _should_show_commits_drawers

    changespec = _make_changespec(
        commits=[
            CommitEntry(number=1, note="first"),
            CommitEntry(number=3, note="current"),
            CommitEntry(number=3, note="proposal a", proposal_letter="a"),
            CommitEntry(number=3, note="proposal b", proposal_letter="b"),
        ]
    )

    entry_a = CommitEntry(number=3, note="proposal a", proposal_letter="a")
    entry_b = CommitEntry(number=3, note="proposal b", proposal_letter="b")

    assert _should_show_commits_drawers(entry_a, changespec, commits_collapsed=True)
    assert _should_show_commits_drawers(entry_b, changespec, commits_collapsed=True)
