"""Tests for the confirm kill modal."""

from ace.tui.modals.confirm_kill_modal import ConfirmKillModal


def test_confirm_kill_modal_init() -> None:
    """Test ConfirmKillModal initialization."""
    modal = ConfirmKillModal(agent_description="Test Agent")
    assert modal.agent_description == "Test Agent"


def test_confirm_kill_modal_bindings() -> None:
    """Test that ConfirmKillModal has expected bindings."""

    def get_key(binding: object) -> str:
        if hasattr(binding, "key"):
            return str(binding.key)  # type: ignore[attr-defined]
        return str(binding[0])  # type: ignore[index]

    bindings = [get_key(b) for b in ConfirmKillModal.BINDINGS]
    assert "escape" in bindings
    assert "q" in bindings
    assert "y" in bindings
    assert "n" in bindings


def test_confirm_kill_modal_long_description() -> None:
    """Test ConfirmKillModal with a long description."""
    desc = "This is a very long agent description that might span multiple lines"
    modal = ConfirmKillModal(agent_description=desc)
    assert modal.agent_description == desc


def test_confirm_kill_modal_empty_description() -> None:
    """Test ConfirmKillModal with empty description."""
    modal = ConfirmKillModal(agent_description="")
    assert modal.agent_description == ""
