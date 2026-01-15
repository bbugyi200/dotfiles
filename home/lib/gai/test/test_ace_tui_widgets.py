"""Tests for the ace TUI widgets (section builders and TabBar)."""

from unittest.mock import patch

from ace.changespec import ChangeSpec, CommentEntry, CommitEntry, HookEntry
from ace.tui import AceApp
from ace.tui.widgets import TabBar
from ace.tui.widgets.section_builders import _should_show_commits_drawers


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


# --- _should_show_commits_drawers Tests ---


def test_should_show_commits_drawers_expanded() -> None:
    """All entries show drawers when expanded (commits_collapsed=False)."""
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


# --- TabBar Widget Tests ---


def test_tab_bar_initial_state() -> None:
    """Test that TabBar initializes with changespecs tab active."""
    tab_bar = TabBar()
    assert tab_bar._current_tab == "changespecs"


def test_tab_bar_update_tab_to_agents() -> None:
    """Test that update_tab changes the current tab to agents."""
    tab_bar = TabBar()
    tab_bar.update_tab("agents")
    assert tab_bar._current_tab == "agents"


def test_tab_bar_update_tab_to_changespecs() -> None:
    """Test that update_tab changes the current tab to changespecs."""
    tab_bar = TabBar()
    tab_bar.update_tab("agents")
    tab_bar.update_tab("changespecs")
    assert tab_bar._current_tab == "changespecs"


async def test_tab_bar_integration_tab_key() -> None:
    """Test that pressing TAB key cycles through all tabs."""
    mock_changespecs = [_make_changespec()]
    with patch("ace.changespec.find_all_changespecs", return_value=mock_changespecs):
        app = AceApp()
        async with app.run_test() as pilot:
            # Initial state - changespecs tab
            assert app.current_tab == "changespecs"
            tab_bar = app.query_one("#tab-bar", TabBar)
            assert tab_bar._current_tab == "changespecs"

            # Press TAB to switch to agents
            await pilot.press("tab")
            assert app.current_tab == "agents"
            assert tab_bar._current_tab == "agents"

            # Press TAB to switch to axe
            await pilot.press("tab")
            assert app.current_tab == "axe"
            assert tab_bar._current_tab == "axe"

            # Press TAB to cycle back to changespecs
            await pilot.press("tab")
            assert app.current_tab == "changespecs"
            assert tab_bar._current_tab == "changespecs"
