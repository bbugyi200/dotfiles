"""Tests for the axe info panel widget."""

from ace.tui.bgcmd import BackgroundCommandInfo
from ace.tui.widgets import AxeInfoPanel


def test_axe_info_panel_init() -> None:
    """Test AxeInfoPanel initialization."""
    panel = AxeInfoPanel()
    assert panel._is_running is False
    assert panel._countdown == 0
    assert panel._interval == 0
    assert panel._bgcmd_mode is False
    assert panel._bgcmd_slot is None
    assert panel._bgcmd_info is None
    assert panel._bgcmd_running is False


def test_axe_info_panel_state_direct_manipulation() -> None:
    """Test that AxeInfoPanel state can be manipulated directly."""
    panel = AxeInfoPanel()

    # Test bgcmd mode state
    panel._bgcmd_mode = True
    panel._bgcmd_slot = 3
    info = BackgroundCommandInfo(
        command="make test",
        project="myproject",
        workspace_num=1,
        workspace_dir="/path",
        started_at="2025-01-01T12:00:00",
    )
    panel._bgcmd_info = info
    panel._bgcmd_running = True

    assert panel._bgcmd_mode is True
    assert panel._bgcmd_slot == 3
    assert panel._bgcmd_info == info
    assert panel._bgcmd_running is True

    # Test countdown state
    panel._countdown = 5
    panel._interval = 10

    assert panel._countdown == 5
    assert panel._interval == 10


def test_axe_info_panel_bgcmd_slot_values() -> None:
    """Test various slot values for bgcmd mode."""
    panel = AxeInfoPanel()

    # Test different slot values
    for slot in range(1, 10):
        panel._bgcmd_slot = slot
        assert panel._bgcmd_slot == slot


def test_axe_info_panel_interval_values() -> None:
    """Test various interval values."""
    panel = AxeInfoPanel()

    panel._interval = 0
    assert panel._interval == 0

    panel._interval = 30
    assert panel._interval == 30

    panel._interval = 60
    assert panel._interval == 60
