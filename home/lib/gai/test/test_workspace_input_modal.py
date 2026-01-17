"""Tests for the workspace input modal."""

from ace.tui.modals import WorkspaceInputModal
from ace.tui.modals.workspace_input_modal import _WorkspaceInput


def test_workspace_input_modal_init_default() -> None:
    """Test WorkspaceInputModal initialization with default value."""
    modal = WorkspaceInputModal()
    assert modal._default_workspace == 1


def test_workspace_input_modal_init_custom() -> None:
    """Test WorkspaceInputModal initialization with custom default."""
    modal = WorkspaceInputModal(default_workspace=5)
    assert modal._default_workspace == 5


def test_workspace_input_modal_bindings() -> None:
    """Test that WorkspaceInputModal has escape binding."""

    # BINDINGS can contain Binding objects or tuples
    def get_key(binding: object) -> str:
        if hasattr(binding, "key"):
            return str(binding.key)  # type: ignore[attr-defined]
        return str(binding[0])  # type: ignore[index]

    assert any(get_key(b) == "escape" for b in WorkspaceInputModal.BINDINGS)


def test_workspace_input_has_bindings() -> None:
    """Test that _WorkspaceInput has ctrl+f and ctrl+b bindings."""

    # BINDINGS can contain Binding objects or tuples
    def get_key(binding: object) -> str:
        if hasattr(binding, "key"):
            return str(binding.key)  # type: ignore[attr-defined]
        return str(binding[0])  # type: ignore[index]

    bindings = [get_key(b) for b in _WorkspaceInput.BINDINGS]
    assert "ctrl+f" in bindings
    assert "ctrl+b" in bindings
