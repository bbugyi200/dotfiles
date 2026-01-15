"""Tests for the ace TUI keybinding footer status utilities and axe state."""

from ace.changespec import get_base_status, has_ready_to_mail_suffix
from ace.tui.widgets import KeybindingFooter

# --- Status Utility Tests ---


def test_get_base_status_drafted() -> None:
    """Test get_base_status returns correct base for Drafted."""
    assert get_base_status("Drafted") == "Drafted"


def test_get_base_status_with_ready_to_mail_suffix() -> None:
    """Test get_base_status strips READY TO MAIL suffix."""
    assert get_base_status("Drafted - (!: READY TO MAIL)") == "Drafted"


def test_get_base_status_submitted() -> None:
    """Test get_base_status returns correct base for Submitted."""
    assert get_base_status("Submitted") == "Submitted"


def test_get_base_status_mailed() -> None:
    """Test get_base_status returns correct base for Mailed."""
    assert get_base_status("Mailed") == "Mailed"


def test_get_base_status_reverted() -> None:
    """Test get_base_status returns correct base for Reverted."""
    assert get_base_status("Reverted") == "Reverted"


def test_has_ready_to_mail_suffix_true() -> None:
    """Test has_ready_to_mail_suffix returns True for correct suffix."""
    assert has_ready_to_mail_suffix("Drafted - (!: READY TO MAIL)") is True


def test_has_ready_to_mail_suffix_false() -> None:
    """Test has_ready_to_mail_suffix returns False for no suffix."""
    assert has_ready_to_mail_suffix("Drafted") is False


def test_has_ready_to_mail_suffix_mailed_true() -> None:
    """Test has_ready_to_mail_suffix returns True for Mailed with suffix."""
    assert has_ready_to_mail_suffix("Mailed - (!: READY TO MAIL)") is True


# --- Axe Status Indicator Tests ---


def test_keybinding_footer_status_indicator_stopped() -> None:
    """Test status indicator shows STOPPED when axe not running."""
    footer = KeybindingFooter()
    footer._axe_running = False
    footer._axe_starting = False
    footer._axe_stopping = False

    text = footer._get_status_text()
    text_str = str(text)

    assert "STOPPED" in text_str


def test_keybinding_footer_status_indicator_running() -> None:
    """Test status indicator shows RUNNING when axe is running."""
    footer = KeybindingFooter()
    footer._axe_running = True
    footer._axe_starting = False
    footer._axe_stopping = False

    text = footer._get_status_text()
    text_str = str(text)

    assert "RUNNING" in text_str


def test_keybinding_footer_status_indicator_starting() -> None:
    """Test status indicator shows STARTING when axe is starting."""
    footer = KeybindingFooter()
    footer._axe_running = False
    footer._axe_starting = True
    footer._axe_stopping = False

    text = footer._get_status_text()
    text_str = str(text)

    assert "STARTING" in text_str


def test_keybinding_footer_status_indicator_stopping() -> None:
    """Test status indicator shows STOPPING when axe is stopping."""
    footer = KeybindingFooter()
    footer._axe_running = False
    footer._axe_starting = False
    footer._axe_stopping = True

    text = footer._get_status_text()
    text_str = str(text)

    assert "STOPPING" in text_str


def test_keybinding_footer_set_axe_running() -> None:
    """Test set_axe_running updates the state."""
    footer = KeybindingFooter()
    assert footer._axe_running is False

    footer.set_axe_running(True)
    assert footer._axe_running is True

    footer.set_axe_running(False)
    assert footer._axe_running is False


def test_keybinding_footer_set_axe_starting() -> None:
    """Test set_axe_starting updates the state."""
    footer = KeybindingFooter()
    assert footer._axe_starting is False

    footer.set_axe_starting(True)
    assert footer._axe_starting is True

    footer.set_axe_starting(False)
    assert footer._axe_starting is False


def test_keybinding_footer_set_axe_stopping() -> None:
    """Test set_axe_stopping updates the state."""
    footer = KeybindingFooter()
    assert footer._axe_stopping is False

    footer.set_axe_stopping(True)
    assert footer._axe_stopping is True

    footer.set_axe_stopping(False)
    assert footer._axe_stopping is False


def test_keybinding_footer_axe_bindings_only_copy() -> None:
    """Test that AXE tab only shows copy binding."""
    footer = KeybindingFooter()

    bindings = footer._compute_axe_bindings()

    assert len(bindings) == 1
    assert bindings[0] == ("%", "copy")
