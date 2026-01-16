"""Tests for the ace TUI keybinding footer workflow and rebase bindings."""

from unittest.mock import patch

from ace.changespec import ChangeSpec, CommentEntry
from ace.tui.widgets import KeybindingFooter


def _make_changespec(
    name: str = "test_feature",
    description: str = "Test description",
    status: str = "Drafted",
    cl: str | None = None,
    parent: str | None = None,
    file_path: str = "/tmp/test.gp",
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
        commits=None,
        hooks=None,
        comments=comments,
    )


# --- Rebase Binding Tests ---


def test_keybinding_footer_rebase_visible_wip() -> None:
    """Test 'b' (rebase) binding is visible for WIP status."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="WIP")

    bindings = footer._compute_available_bindings(changespec)
    binding_keys = [b[0] for b in bindings]

    assert "b" in binding_keys


def test_keybinding_footer_rebase_visible_drafted() -> None:
    """Test 'b' (rebase) binding is visible for Drafted status."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec)
    binding_keys = [b[0] for b in bindings]

    assert "b" in binding_keys


def test_keybinding_footer_rebase_visible_mailed() -> None:
    """Test 'b' (rebase) binding is visible for Mailed status."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Mailed")

    bindings = footer._compute_available_bindings(changespec)
    binding_keys = [b[0] for b in bindings]

    assert "b" in binding_keys


def test_keybinding_footer_rebase_hidden_submitted() -> None:
    """Test 'b' (rebase) binding is hidden for Submitted status."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Submitted")

    bindings = footer._compute_available_bindings(changespec)
    binding_keys = [b[0] for b in bindings]

    assert "b" not in binding_keys


# --- Workflow Binding Tests ---


def test_keybinding_footer_workflow_binding_single() -> None:
    """Test 'r' (run) binding shows workflow name when one workflow available."""
    footer = KeybindingFooter()
    # Create a changespec with a fix-hook comment to trigger workflow
    comment = CommentEntry(
        reviewer="fix-hook",
        file_path="test.py",
    )
    changespec = _make_changespec(status="Drafted", comments=[comment])

    with patch("ace.tui.widgets.keybinding_footer.get_available_workflows") as mock:
        mock.return_value = ["fix"]
        bindings = footer._compute_available_bindings(changespec)

    binding_dict = dict(bindings)
    assert "r" in binding_dict
    assert "fix" in binding_dict["r"]


def test_keybinding_footer_workflow_binding_multiple() -> None:
    """Test 'r' (run) binding shows count when multiple workflows available."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    with patch("ace.tui.widgets.keybinding_footer.get_available_workflows") as mock:
        mock.return_value = ["fix", "crs"]
        bindings = footer._compute_available_bindings(changespec)

    binding_dict = dict(bindings)
    assert "r" in binding_dict
    assert "2 workflows" in binding_dict["r"]


def test_keybinding_footer_workflow_binding_none() -> None:
    """Test 'r' (run) binding is hidden when no workflows available."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    with patch("ace.tui.widgets.keybinding_footer.get_available_workflows") as mock:
        mock.return_value = []
        bindings = footer._compute_available_bindings(changespec)

    binding_keys = [b[0] for b in bindings]
    assert "r" not in binding_keys


# --- Edit, Copy, Fold Binding Tests ---


def test_keybinding_footer_edit_spec_always_visible() -> None:
    """Test '@' (edit spec) binding is always visible."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec)
    binding_keys = [b[0] for b in bindings]

    assert "@" in binding_keys


def test_keybinding_footer_copy_always_visible() -> None:
    """Test '%' (copy) binding is always visible."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec)
    binding_keys = [b[0] for b in bindings]

    assert "%" in binding_keys


def test_keybinding_footer_fold_always_visible() -> None:
    """Test 'z' (fold) binding is always visible."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec)
    binding_keys = [b[0] for b in bindings]

    assert "z" in binding_keys


# --- Ready Binding Tests ---


def test_keybinding_footer_ready_visible_drafted_no_suffix() -> None:
    """Test '!' (ready) binding is visible for Drafted without READY TO MAIL suffix."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec)
    binding_keys = [b[0] for b in bindings]

    assert "!" in binding_keys


def test_keybinding_footer_ready_hidden_with_suffix() -> None:
    """Test '!' (ready) binding is hidden when already has READY TO MAIL suffix."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted - (!: READY TO MAIL)")

    bindings = footer._compute_available_bindings(changespec)
    binding_keys = [b[0] for b in bindings]

    assert "!" not in binding_keys
