"""Tests for the command input modal."""

from ace.tui.modals import CommandInputModal
from ace.tui.modals.command_input_modal import _CommandInput


def test_command_input_modal_init() -> None:
    """Test CommandInputModal initialization."""
    modal = CommandInputModal(project="myproject", workspace_num=3)
    assert modal._project == "myproject"
    assert modal._workspace_num == 3


def test_command_input_modal_bindings() -> None:
    """Test that CommandInputModal has escape binding."""

    # BINDINGS can contain Binding objects or tuples
    def get_key(binding: object) -> str:
        if hasattr(binding, "key"):
            return str(binding.key)  # type: ignore[attr-defined]
        return str(binding[0])  # type: ignore[index]

    assert any(get_key(b) == "escape" for b in CommandInputModal.BINDINGS)


def test_command_input_has_bindings() -> None:
    """Test that _CommandInput has readline-style bindings."""

    # BINDINGS can contain Binding objects or tuples
    def get_key(binding: object) -> str:
        if hasattr(binding, "key"):
            return str(binding.key)  # type: ignore[attr-defined]
        return str(binding[0])  # type: ignore[index]

    bindings = [get_key(b) for b in _CommandInput.BINDINGS]
    assert "ctrl+f" in bindings
    assert "ctrl+b" in bindings
    assert "ctrl+a" in bindings
    assert "ctrl+e" in bindings
