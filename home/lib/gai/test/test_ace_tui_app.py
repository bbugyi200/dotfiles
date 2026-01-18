"""Tests for the ace TUI app initialization, navigation, and modals."""

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
    with patch("ace.changespec.find_all_changespecs", return_value=mock_changespecs):
        app = AceApp()
        # Default query is '"(!: "'
        assert app.query_string == '"(!: "'
        assert app.parsed_query is not None


async def test_app_initialization_custom_query() -> None:
    """Test AceApp initializes with a custom query string."""
    mock_changespecs = [_make_changespec(name="feature_a")]
    with patch("ace.changespec.find_all_changespecs", return_value=mock_changespecs):
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
    with patch("ace.changespec.find_all_changespecs", return_value=mock_changespecs):
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
    with patch("ace.changespec.find_all_changespecs", return_value=mock_changespecs):
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
    with patch("ace.changespec.find_all_changespecs", return_value=mock_changespecs):
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
    with patch("ace.changespec.find_all_changespecs", return_value=mock_changespecs):
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
    with patch("ace.changespec.find_all_changespecs", return_value=mock_changespecs):
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
    with patch("ace.changespec.find_all_changespecs", return_value=mock_changespecs):
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
    with patch("ace.changespec.find_all_changespecs", return_value=mock_changespecs):
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
    with patch("ace.changespec.find_all_changespecs", return_value=mock_changespecs):
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


# --- Marking Auto-Navigation Tests ---


async def test_mark_navigates_to_next_spec() -> None:
    """Test marking a spec navigates to the next spec."""
    mock_changespecs = [
        _make_changespec(name="feature_a"),
        _make_changespec(name="feature_b"),
        _make_changespec(name="feature_c"),
    ]
    with patch("ace.changespec.find_all_changespecs", return_value=mock_changespecs):
        app = AceApp(query='"feature"')
        async with app.run_test() as pilot:
            # Start at index 0
            assert app.current_idx == 0
            assert len(app.marked_indices) == 0

            # Mark first spec - should navigate to second
            await pilot.press("m")
            assert 0 in app.marked_indices
            assert app.current_idx == 1


async def test_mark_wraps_around() -> None:
    """Test marking at last spec wraps around to first."""
    mock_changespecs = [
        _make_changespec(name="feature_a"),
        _make_changespec(name="feature_b"),
        _make_changespec(name="feature_c"),
    ]
    with patch("ace.changespec.find_all_changespecs", return_value=mock_changespecs):
        app = AceApp(query='"feature"')
        async with app.run_test() as pilot:
            # Navigate to last spec (index 2)
            await pilot.press("j")
            await pilot.press("j")
            assert app.current_idx == 2

            # Mark last spec - should wrap around to first (index 0)
            await pilot.press("m")
            assert 2 in app.marked_indices
            assert app.current_idx == 0


async def test_unmark_navigates_to_next_spec() -> None:
    """Test un-marking a spec navigates to the next spec."""
    mock_changespecs = [
        _make_changespec(name="feature_a"),
        _make_changespec(name="feature_b"),
        _make_changespec(name="feature_c"),
    ]
    with patch("ace.changespec.find_all_changespecs", return_value=mock_changespecs):
        app = AceApp(query='"feature"')
        async with app.run_test() as pilot:
            # Mark first spec (navigates to second)
            await pilot.press("m")
            assert app.current_idx == 1

            # Navigate back to first spec
            await pilot.press("k")
            assert app.current_idx == 0

            # Un-mark first spec - should navigate to next (index 1)
            await pilot.press("m")
            assert 0 not in app.marked_indices
            assert app.current_idx == 1


async def test_mark_single_spec_stays() -> None:
    """Test marking the only spec stays on it."""
    mock_changespecs = [_make_changespec(name="only_spec")]
    with patch("ace.changespec.find_all_changespecs", return_value=mock_changespecs):
        app = AceApp(query='"only"')
        async with app.run_test() as pilot:
            assert app.current_idx == 0

            # Mark the only spec - should stay on it
            await pilot.press("m")
            assert 0 in app.marked_indices
            assert app.current_idx == 0
