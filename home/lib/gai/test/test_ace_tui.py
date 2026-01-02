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
    """Test 'j' key at last item doesn't change index."""
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

            # Press 'j' at end should not change index
            await pilot.press("j")
            assert app.current_idx == 1


async def test_navigation_prev_at_start() -> None:
    """Test 'k' key at first item doesn't change index."""
    mock_changespecs = [
        _make_changespec(name="feature_a"),
        _make_changespec(name="feature_b"),
    ]
    with patch("ace.tui.app.find_all_changespecs", return_value=mock_changespecs):
        app = AceApp(query='"feature"')
        async with app.run_test() as pilot:
            # Already at index 0
            assert app.current_idx == 0

            # Press 'k' at start should not change index
            await pilot.press("k")
            assert app.current_idx == 0


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
