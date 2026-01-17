"""Tests for the BgCmdList widget."""

from ace.tui.bgcmd import BackgroundCommandInfo
from ace.tui.widgets import BgCmdList


def test_bgcmd_list_init() -> None:
    """Test BgCmdList initialization."""
    widget = BgCmdList()
    assert widget._items == []
    assert widget._axe_running is False
    assert widget._bgcmd_infos == {}
    assert widget._programmatic_update is False


def test_bgcmd_list_selection_changed_message() -> None:
    """Test SelectionChanged message creation."""
    msg = BgCmdList.SelectionChanged("axe")
    assert msg.item == "axe"


def test_bgcmd_list_selection_changed_slot() -> None:
    """Test SelectionChanged message with slot number."""
    msg = BgCmdList.SelectionChanged(3)
    assert msg.item == 3


def test_bgcmd_list_format_axe_option_running() -> None:
    """Test formatting axe option when running."""
    widget = BgCmdList()
    option = widget._format_axe_option(is_running=True, is_selected=False)
    assert option.id == "axe"
    # The prompt should contain the axe label
    text_str = str(option.prompt)
    assert "gai axe" in text_str


def test_bgcmd_list_format_axe_option_stopped() -> None:
    """Test formatting axe option when stopped."""
    widget = BgCmdList()
    option = widget._format_axe_option(is_running=False, is_selected=False)
    assert option.id == "axe"


def test_bgcmd_list_format_axe_option_selected() -> None:
    """Test formatting axe option when selected."""
    widget = BgCmdList()
    option = widget._format_axe_option(is_running=True, is_selected=True)
    assert option.id == "axe"


def test_bgcmd_list_format_bgcmd_option() -> None:
    """Test formatting background command option."""
    widget = BgCmdList()
    info = BackgroundCommandInfo(
        command="make test",
        project="myproject",
        workspace_num=1,
        workspace_dir="/path",
        started_at="2025-01-01T12:00:00",
    )
    option = widget._format_bgcmd_option(slot=3, info=info, is_selected=False)
    assert option.id == "3"
    text_str = str(option.prompt)
    assert "3:" in text_str
    assert "make test" in text_str


def test_bgcmd_list_format_bgcmd_option_long_command() -> None:
    """Test formatting background command option with long command."""
    widget = BgCmdList()
    info = BackgroundCommandInfo(
        command="make test-all-with-coverage-and-reports",
        project="myproject",
        workspace_num=1,
        workspace_dir="/path",
        started_at="2025-01-01T12:00:00",
    )
    option = widget._format_bgcmd_option(slot=1, info=info, is_selected=False)
    assert option.id == "1"
    text_str = str(option.prompt)
    # Command should be truncated
    assert "..." in text_str


def test_bgcmd_list_format_bgcmd_option_selected() -> None:
    """Test formatting background command option when selected."""
    widget = BgCmdList()
    info = BackgroundCommandInfo(
        command="npm run build",
        project="webapp",
        workspace_num=2,
        workspace_dir="/path",
        started_at="2025-01-01T12:00:00",
    )
    option = widget._format_bgcmd_option(slot=5, info=info, is_selected=True)
    assert option.id == "5"
