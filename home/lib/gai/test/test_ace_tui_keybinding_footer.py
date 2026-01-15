"""Tests for the ace TUI keybinding footer and status utilities."""

from ace.changespec import (
    ChangeSpec,
    CommentEntry,
    CommitEntry,
    HookEntry,
    get_base_status,
    has_ready_to_mail_suffix,
)
from ace.tui.models.agent import Agent, AgentType
from ace.tui.widgets import KeybindingFooter


def _make_changespec(
    name: str = "test_feature",
    description: str = "Test description",
    status: str = "Drafted",
    cl: str | None = None,
    parent: str | None = None,
    file_path: str = "/tmp/test.gp",
    commits: list[CommitEntry] | None = None,
    hooks: list[HookEntry] | None = None,
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
        commits=commits,
        hooks=hooks,
        comments=comments,
    )


# --- Keybinding Footer Tests ---


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
    # Status with suffix - base status is Drafted
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


def test_keybinding_footer_mail_visible_ready_to_mail() -> None:
    """Test 'm' and 'f' bindings are visible with READY TO MAIL suffix."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted - (!: READY TO MAIL)", cl="123456")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "m" in binding_keys
    assert "f" in binding_keys


def test_keybinding_footer_mail_hidden_without_suffix() -> None:
    """Test 'm' and 'f' bindings are hidden without READY TO MAIL suffix."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted", cl="123456")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "m" not in binding_keys
    assert "f" not in binding_keys


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
    # Regular entry (not a proposal)
    commits = [CommitEntry(number=1, note="Test")]
    changespec = _make_changespec(status="Drafted", commits=commits)

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "a" not in binding_keys


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


def test_keybinding_footer_navigation_in_middle() -> None:
    """Test navigation bindings in middle of list."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    # In middle (idx=1) with 3 items - should have both 'j' and 'k'
    bindings = footer._compute_available_bindings(changespec, 1, 3)
    binding_keys = [b[0] for b in bindings]

    assert "j" in binding_keys
    assert "k" in binding_keys


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

    text = footer._get_status_text()
    text_str = str(text)

    assert "STOPPED" in text_str


def test_keybinding_footer_status_indicator_running() -> None:
    """Test status indicator shows RUNNING when axe is running."""
    footer = KeybindingFooter()
    footer._axe_running = True
    footer._axe_starting = False

    text = footer._get_status_text()
    text_str = str(text)

    assert "RUNNING" in text_str


def test_keybinding_footer_status_indicator_starting() -> None:
    """Test status indicator shows STARTING when axe is starting."""
    footer = KeybindingFooter()
    footer._axe_running = False
    footer._axe_starting = True

    text = footer._get_status_text()
    text_str = str(text)

    assert "STARTING" in text_str


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


def test_keybinding_footer_axe_bindings_only_copy() -> None:
    """Test that AXE tab only shows copy binding."""
    footer = KeybindingFooter()

    bindings = footer._compute_axe_bindings()

    assert len(bindings) == 1
    assert bindings[0] == ("%", "copy")


# --- Agent Bindings Tests ---


def _make_agent(
    status: str = "RUNNING",
    response_path: str | None = None,
) -> Agent:
    """Create a test Agent for binding tests."""
    return Agent(
        agent_type=AgentType.RUNNING,
        cl_name="test_feature",
        project_file="/tmp/test.gp",
        status=status,
        start_time=None,
        response_path=response_path,
    )


def test_keybinding_footer_agent_bindings_none_agent() -> None:
    """Test agent bindings when no agent selected."""
    footer = KeybindingFooter()

    bindings = footer._compute_agent_bindings(None, 0, 0)
    binding_keys = [b[0] for b in bindings]

    assert "<space>" in binding_keys
    assert "x" not in binding_keys  # Kill/dismiss only when agent selected


def test_keybinding_footer_agent_bindings_running_agent() -> None:
    """Test agent bindings for a running agent."""
    footer = KeybindingFooter()
    agent = _make_agent(status="RUNNING")

    bindings = footer._compute_agent_bindings(agent, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "x" in binding_keys  # Kill is available
    assert "<space>" in binding_keys


def test_keybinding_footer_agent_bindings_completed_agent_with_chat() -> None:
    """Test agent bindings for completed agent with chat file."""
    footer = KeybindingFooter()
    agent = _make_agent(status="NO CHANGES", response_path="/tmp/chat.md")

    bindings = footer._compute_agent_bindings(agent, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "x" in binding_keys  # Dismiss is available
    assert "@" in binding_keys  # Edit chat is available
    assert "%" in binding_keys  # Copy chat is available


def test_keybinding_footer_agent_bindings_diff_visible() -> None:
    """Test agent bindings when diff panel is visible."""
    footer = KeybindingFooter()
    agent = _make_agent(status="RUNNING")

    bindings = footer._compute_agent_bindings(agent, 0, 1, diff_visible=True)
    binding_keys = [b[0] for b in bindings]

    assert "l" in binding_keys  # Layout toggle is available


def test_keybinding_footer_agent_bindings_navigation_middle() -> None:
    """Test agent bindings navigation in the middle of list."""
    footer = KeybindingFooter()

    bindings = footer._compute_agent_bindings(None, 1, 3)
    binding_keys = [b[0] for b in bindings]

    assert "j" in binding_keys  # Next
    assert "k" in binding_keys  # Prev


# --- Rebase and Workflow Bindings Tests ---


def test_keybinding_footer_rebase_visible_wip() -> None:
    """Test 'b' (rebase) binding is visible for WIP status."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="WIP")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "b" in binding_keys


def test_keybinding_footer_rebase_visible_drafted() -> None:
    """Test 'b' (rebase) binding is visible for Drafted status."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "b" in binding_keys


def test_keybinding_footer_rebase_visible_mailed() -> None:
    """Test 'b' (rebase) binding is visible for Mailed status."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Mailed")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "b" in binding_keys


def test_keybinding_footer_rebase_hidden_submitted() -> None:
    """Test 'b' (rebase) binding is hidden for Submitted status."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Submitted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "b" not in binding_keys


def test_keybinding_footer_get_status_text_stopped() -> None:
    """Test _get_status_text returns STOPPED status."""
    footer = KeybindingFooter()
    footer._axe_running = False
    footer._axe_starting = False

    text = footer._get_status_text()

    assert "STOPPED" in str(text)


def test_keybinding_footer_get_status_text_running() -> None:
    """Test _get_status_text returns RUNNING status."""
    footer = KeybindingFooter()
    footer._axe_running = True
    footer._axe_starting = False

    text = footer._get_status_text()

    assert "RUNNING" in str(text)


def test_keybinding_footer_get_status_text_starting() -> None:
    """Test _get_status_text returns STARTING status."""
    footer = KeybindingFooter()
    footer._axe_running = False
    footer._axe_starting = True

    text = footer._get_status_text()

    assert "STARTING" in str(text)


def test_keybinding_footer_workflow_binding_single() -> None:
    """Test 'r' (run) binding shows workflow name when one workflow available."""
    footer = KeybindingFooter()
    # Create a changespec with a fix-hook comment to trigger workflow
    comment = CommentEntry(
        reviewer="fix-hook",
        file_path="test.py",
    )
    changespec = _make_changespec(status="Drafted", comments=[comment])

    # Mock the get_available_workflows to return one workflow
    from unittest.mock import patch

    with patch("ace.tui.widgets.keybinding_footer.get_available_workflows") as mock:
        mock.return_value = ["fix"]
        bindings = footer._compute_available_bindings(changespec, 0, 1)

    binding_dict = dict(bindings)
    assert "r" in binding_dict
    assert "fix" in binding_dict["r"]


def test_keybinding_footer_workflow_binding_multiple() -> None:
    """Test 'r' (run) binding shows count when multiple workflows available."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    from unittest.mock import patch

    with patch("ace.tui.widgets.keybinding_footer.get_available_workflows") as mock:
        mock.return_value = ["fix", "crs"]
        bindings = footer._compute_available_bindings(changespec, 0, 1)

    binding_dict = dict(bindings)
    assert "r" in binding_dict
    assert "2 workflows" in binding_dict["r"]


def test_keybinding_footer_workflow_binding_none() -> None:
    """Test 'r' (run) binding is hidden when no workflows available."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    from unittest.mock import patch

    with patch("ace.tui.widgets.keybinding_footer.get_available_workflows") as mock:
        mock.return_value = []
        bindings = footer._compute_available_bindings(changespec, 0, 1)

    binding_keys = [b[0] for b in bindings]
    assert "r" not in binding_keys


def test_keybinding_footer_edit_spec_always_visible() -> None:
    """Test '@' (edit spec) binding is always visible."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "@" in binding_keys


def test_keybinding_footer_copy_always_visible() -> None:
    """Test '%' (copy) binding is always visible."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "%" in binding_keys


def test_keybinding_footer_fold_always_visible() -> None:
    """Test 'z' (fold) binding is always visible."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "z" in binding_keys


def test_keybinding_footer_ready_visible_drafted_no_suffix() -> None:
    """Test '!' (ready) binding is visible for Drafted without READY TO MAIL suffix."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "!" in binding_keys


def test_keybinding_footer_ready_hidden_with_suffix() -> None:
    """Test '!' (ready) binding is hidden when already has READY TO MAIL suffix."""
    footer = KeybindingFooter()
    changespec = _make_changespec(status="Drafted - (!: READY TO MAIL)")

    bindings = footer._compute_available_bindings(changespec, 0, 1)
    binding_keys = [b[0] for b in bindings]

    assert "!" not in binding_keys
