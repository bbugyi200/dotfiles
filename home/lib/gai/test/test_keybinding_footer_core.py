"""Tests for the ace TUI keybinding footer core bindings."""

from ace.changespec import ChangeSpec, CommitEntry
from ace.tui.widgets import KeybindingFooter


def _make_changespec(
    name: str = "test_feature",
    description: str = "Test description",
    status: str = "Drafted",
    cl: str | None = None,
    parent: str | None = None,
    file_path: str = "/tmp/test.gp",
    commits: list[CommitEntry] | None = None,
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
        hooks=None,
        comments=None,
    )


# --- Reword Binding Tests ---


def test_keybinding_footer_reword_visible_drafted_with_cl() -> None:
    """Test 'w' (reword) binding is visible for Drafted status with CL."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted", cl="123456")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "w" in binding_keys


def test_keybinding_footer_reword_visible_mailed_with_cl() -> None:
    """Test 'w' (reword) binding is visible for Mailed status with CL."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Mailed", cl="123456")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "w" in binding_keys


def test_keybinding_footer_reword_hidden_submitted() -> None:
    """Test 'w' (reword) binding is hidden for Submitted status."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Submitted", cl="123456")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "w" not in binding_keys


def test_keybinding_footer_reword_hidden_no_cl() -> None:
    """Test 'w' (reword) binding is hidden when CL is not set."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted", cl=None)

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "w" not in binding_keys


def test_keybinding_footer_reword_visible_with_ready_to_mail_suffix() -> None:
    """Test 'w' (reword) binding is visible for Drafted with READY TO MAIL suffix."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted - (!: READY TO MAIL)", cl="123456")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "w" in binding_keys


def test_keybinding_footer_reword_hidden_reverted() -> None:
    """Test 'w' (reword) binding is hidden for Reverted status."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Reverted", cl="123456")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "w" not in binding_keys


# --- Diff Binding Tests ---


def test_keybinding_footer_diff_visible_with_cl() -> None:
    """Test 'd' (diff) binding is visible when CL is set."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted", cl="123456")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "d" in binding_keys


def test_keybinding_footer_diff_hidden_without_cl() -> None:
    """Test 'd' (diff) binding is hidden when CL is not set."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted", cl=None)

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "d" not in binding_keys


# --- Mail Binding Tests ---


def test_keybinding_footer_mail_visible_ready_to_mail() -> None:
    """Test 'm' binding is visible with READY TO MAIL suffix."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted - (!: READY TO MAIL)", cl="123456")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "m" in binding_keys


def test_keybinding_footer_mail_hidden_without_suffix() -> None:
    """Test 'm' binding is hidden without READY TO MAIL suffix."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted", cl="123456")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "m" not in binding_keys


# --- Accept Binding Tests ---


def test_keybinding_footer_accept_visible_with_proposals() -> None:
    """Test 'a' (accept) binding is visible when proposed entries exist."""
    footer = KeybindingFooter()
    commits = [CommitEntry(number=1, note="Test", proposal_letter="a")]
    changespec = _make_changespec(status="Drafted", commits=commits)

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "a" in binding_keys


def test_keybinding_footer_accept_hidden_without_proposals() -> None:
    """Test 'a' (accept) binding is hidden when no proposed entries."""
    footer = KeybindingFooter()
    commits = [CommitEntry(number=1, note="Test")]
    changespec = _make_changespec(status="Drafted", commits=commits)

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "a" not in binding_keys


# --- Navigation Binding Tests ---


def test_keybinding_footer_navigation_at_start() -> None:
    """Test navigation bindings at start of list."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    # At start (idx=0) with 3 items - should have 'j' but not 'k'
    bindings = footer._compute_available_bindings(changespec, 0, 3)
    binding_keys = [b[0] for b in bindings]

    assert "j" in binding_keys
    assert "k" not in binding_keys


def test_keybinding_footer_navigation_at_end() -> None:
    """Test navigation bindings at end of list."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    # At end (idx=2) with 3 items - should have 'k' but not 'j'
    bindings = footer._compute_available_bindings(changespec, 2, 3)
    binding_keys = [b[0] for b in bindings]

    assert "k" in binding_keys
    assert "j" not in binding_keys


def test_keybinding_footer_navigation_in_middle() -> None:
    """Test navigation bindings in middle of list."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    # In middle (idx=1) with 3 items - should have both 'j' and 'k'
    bindings = footer._compute_available_bindings(changespec, 1, 3)
    binding_keys = [b[0] for b in bindings]

    assert "j" in binding_keys
    assert "k" in binding_keys


# --- Format Bindings Tests ---


def test_keybinding_footer_format_bindings() -> None:
    """Test bindings are formatted correctly."""
    footer = KeybindingFooter()
    bindings = [("q", "quit"), ("j", "next")]

    text = footer._format_bindings(bindings)

    # Verify the text contains both bindings
    assert "j" in str(text)
    assert "next" in str(text)
    assert "q" in str(text)
    assert "quit" in str(text)


def test_keybinding_footer_bindings_sorted() -> None:
    """Test bindings are sorted correctly."""
    footer = KeybindingFooter()
    bindings = [("z", "last"), ("a", "first"), ("M", "mid")]

    text = footer._format_bindings(bindings)
    text_str = str(text)

    # Verify ordering: a should come before M which comes before z
    a_pos = text_str.find("a")
    m_pos = text_str.find("M")
    z_pos = text_str.find("z")

    assert a_pos < m_pos < z_pos


# --- Always-Visible Binding Tests ---


def test_keybinding_footer_quit_hidden() -> None:
    """Test 'q' (quit) binding is hidden from footer (only in help popup)."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "q" not in binding_keys


def test_keybinding_footer_always_has_status() -> None:
    """Test 's' (status) binding is always visible."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "s" in binding_keys


def test_keybinding_footer_refresh_hidden() -> None:
    """Test 'y' (refresh) binding is hidden from footer (only in help popup)."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "y" not in binding_keys


def test_keybinding_footer_always_has_view() -> None:
    """Test 'v' (view) binding is always visible."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "v" in binding_keys


def test_keybinding_footer_always_has_hooks() -> None:
    """Test 'h' (hooks) binding is always visible."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "h" in binding_keys


def test_keybinding_footer_always_has_edit_query() -> None:
    """Test '/' (edit query) binding is always visible."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "/" in binding_keys


def test_keybinding_footer_always_has_run_agent() -> None:
    """Test '<space>' (run agent) binding is always visible."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "<space>" in binding_keys
