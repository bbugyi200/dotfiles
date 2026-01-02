"""Tests for status colors, available statuses, and display functions."""

from io import StringIO

from ace.changespec import ChangeSpec
from ace.display import display_changespec
from ace.display_helpers import get_status_color
from ace.status import _get_available_statuses
from rich.console import Console


def testget_status_color_mailed() -> None:
    """Test that 'Mailed' status has the correct color."""
    color = get_status_color("Mailed")
    assert color == "#00D787"


def testget_status_color_unknown() -> None:
    """Test that unknown status returns default color."""
    color = get_status_color("Unknown Status")
    assert color == "#FFFFFF"


def testget_status_color_drafted() -> None:
    """Test that 'Drafted' status has the correct color."""
    color = get_status_color("Drafted")
    assert color == "#87D700"


def testget_status_color_submitted() -> None:
    """Test that 'Submitted' status has the correct color."""
    color = get_status_color("Submitted")
    assert color == "#00AF00"


def test_get_available_statuses_excludes_current() -> None:
    """Test that _get_available_statuses excludes the current status."""
    current_status = "Drafted"
    available = _get_available_statuses(current_status)
    assert current_status not in available


def test_get_available_statuses_includes_others() -> None:
    """Test that _get_available_statuses includes other valid statuses."""
    current_status = "Drafted"
    available = _get_available_statuses(current_status)
    # Should include some other statuses but not current
    assert len(available) > 0
    assert all(s != current_status for s in available)


def test_get_available_statuses_excludes_transient() -> None:
    """Test that _get_available_statuses excludes transient statuses with '...'"""
    available = _get_available_statuses("Drafted")
    # Should not include any status ending with "..."
    assert all(not s.endswith("...") for s in available)


def test_display_changespec_with_hints_returns_mappings() -> None:
    """Test that display_changespec with hints returns hint mappings."""
    # Create a minimal ChangeSpec
    changespec = ChangeSpec(
        name="test_spec",
        description="Test description",
        parent=None,
        cl=None,
        status="Drafted",
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
    )

    # Create a console that writes to a string buffer
    console = Console(file=StringIO(), force_terminal=True)

    # Call with hints enabled
    hint_mappings, hook_hint_to_idx = display_changespec(
        changespec, console, with_hints=True
    )

    # Should have at least hint 0 (the project file)
    assert 0 in hint_mappings
    assert hint_mappings[0] == "/tmp/test.gp"
    # No hooks, so hook_hint_to_idx should be empty
    assert hook_hint_to_idx == {}


def test_display_changespec_without_hints_returns_empty() -> None:
    """Test that display_changespec without hints returns empty dict."""
    # Create a minimal ChangeSpec
    changespec = ChangeSpec(
        name="test_spec",
        description="Test description",
        parent=None,
        cl=None,
        status="Drafted",
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
    )

    # Create a console that writes to a string buffer
    console = Console(file=StringIO(), force_terminal=True)

    # Call without hints (default)
    hint_mappings, hook_hint_to_idx = display_changespec(changespec, console)

    # Should be empty when hints not enabled
    assert hint_mappings == {}
    assert hook_hint_to_idx == {}
