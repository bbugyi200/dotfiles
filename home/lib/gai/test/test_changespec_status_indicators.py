"""Tests for ChangeSpec status indicators in TUI widgets."""

from ace.changespec import ChangeSpec, CommitEntry, HookEntry, HookStatusLine
from ace.tui.widgets.ancestors_children_panel import _get_simple_status_indicator
from ace.tui.widgets.changespec_list import _get_status_indicator


def _make_changespec(
    name: str = "test_feature",
    status: str = "WIP",
    commits: list[CommitEntry] | None = None,
    hooks: list[HookEntry] | None = None,
) -> ChangeSpec:
    """Create a mock ChangeSpec for testing."""
    return ChangeSpec(
        name=name,
        description="Test description",
        parent=None,
        cl=None,
        status=status,
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
        commits=commits,
        hooks=hooks,
        comments=None,
    )


# --- WIP Status Indicator Tests ---


def test_get_status_indicator_wip_returns_w() -> None:
    """Test that WIP status returns 'W' indicator."""
    changespec = _make_changespec(status="WIP")
    indicator, _ = _get_status_indicator(changespec)
    assert indicator == "W"


def test_get_status_indicator_wip_color_is_gold() -> None:
    """Test that WIP status uses gold color."""
    changespec = _make_changespec(status="WIP")
    _, color = _get_status_indicator(changespec)
    assert color == "#FFD700"


def test_get_simple_status_indicator_wip_returns_w() -> None:
    """Test that WIP status returns 'W' in simple indicator."""
    indicator, _ = _get_simple_status_indicator("WIP")
    assert indicator == "W"


def test_get_simple_status_indicator_wip_color_is_gold() -> None:
    """Test that WIP status uses gold color in simple indicator."""
    _, color = _get_simple_status_indicator("WIP")
    assert color == "#FFD700"


def test_get_simple_status_indicator_unknown_returns_w() -> None:
    """Test that unknown status returns 'W' indicator (treated as WIP)."""
    indicator, _ = _get_simple_status_indicator("Unknown Status")
    assert indicator == "W"


# --- WIP with Running Agent/Process Prefix Tests ---


def test_get_status_indicator_wip_with_running_agent() -> None:
    """Test WIP with running agent shows @W."""
    changespec = _make_changespec(
        status="WIP",
        hooks=[
            HookEntry(
                command="test_hook",
                status_lines=[
                    HookStatusLine(
                        commit_entry_num="1",
                        timestamp="250118_120000",
                        status="RUNNING",
                        suffix_type="running_agent",
                    )
                ],
            )
        ],
    )
    indicator, color = _get_status_indicator(changespec)
    assert indicator == "@W"
    assert color == "#FFAF00"  # Orange for running agent


def test_get_status_indicator_wip_with_running_process() -> None:
    """Test WIP with running process shows $W."""
    changespec = _make_changespec(
        status="WIP",
        hooks=[
            HookEntry(
                command="test_hook",
                status_lines=[
                    HookStatusLine(
                        commit_entry_num="1",
                        timestamp="250118_120000",
                        status="RUNNING",
                        suffix_type="running_process",
                    )
                ],
            )
        ],
    )
    indicator, color = _get_status_indicator(changespec)
    assert indicator == "$W"
    assert color == "#FFD700"  # Yellow for running process


def test_get_status_indicator_wip_with_error() -> None:
    """Test WIP with error shows !W."""
    changespec = _make_changespec(
        status="WIP",
        hooks=[
            HookEntry(
                command="test_hook",
                status_lines=[
                    HookStatusLine(
                        commit_entry_num="1",
                        timestamp="250118_120000",
                        status="FAILED",
                        suffix_type="error",
                    )
                ],
            )
        ],
    )
    indicator, color = _get_status_indicator(changespec)
    assert indicator == "!W"
    assert color == "#FF5F5F"  # Red for error


# --- Other Status Indicators (non-WIP) ---


def test_get_status_indicator_drafted() -> None:
    """Test Drafted status returns 'D' with green color."""
    changespec = _make_changespec(status="Drafted")
    indicator, color = _get_status_indicator(changespec)
    assert indicator == "D"
    assert color == "#87D700"


def test_get_status_indicator_mailed() -> None:
    """Test Mailed status returns 'M' with cyan-green color."""
    changespec = _make_changespec(status="Mailed")
    indicator, color = _get_status_indicator(changespec)
    assert indicator == "M"
    assert color == "#00D787"


def test_get_status_indicator_submitted() -> None:
    """Test Submitted status returns 'S' with dark green color."""
    changespec = _make_changespec(status="Submitted")
    indicator, color = _get_status_indicator(changespec)
    assert indicator == "S"
    assert color == "#00AF00"


def test_get_status_indicator_reverted() -> None:
    """Test Reverted status returns 'X' with gray color."""
    changespec = _make_changespec(status="Reverted")
    indicator, color = _get_status_indicator(changespec)
    assert indicator == "X"
    assert color == "#808080"


def test_get_simple_status_indicator_drafted() -> None:
    """Test Drafted status in simple indicator."""
    indicator, color = _get_simple_status_indicator("Drafted")
    assert indicator == "D"
    assert color == "#87D700"


def test_get_simple_status_indicator_mailed() -> None:
    """Test Mailed status in simple indicator."""
    indicator, color = _get_simple_status_indicator("Mailed")
    assert indicator == "M"
    assert color == "#00D787"


def test_get_simple_status_indicator_submitted() -> None:
    """Test Submitted status in simple indicator."""
    indicator, color = _get_simple_status_indicator("Submitted")
    assert indicator == "S"
    assert color == "#00AF00"


def test_get_simple_status_indicator_reverted() -> None:
    """Test Reverted status in simple indicator."""
    indicator, color = _get_simple_status_indicator("Reverted")
    assert indicator == "X"
    assert color == "#808080"
