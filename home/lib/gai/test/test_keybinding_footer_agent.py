"""Tests for the ace TUI keybinding footer agent bindings."""

from ace.tui.models.agent import Agent, AgentType
from ace.tui.widgets import KeybindingFooter


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

    bindings = footer._compute_agent_bindings(None)
    binding_keys = [b[0] for b in bindings]

    assert "r" in binding_keys  # Revive chat is available
    assert "x" not in binding_keys  # Kill/dismiss only when agent selected


def test_keybinding_footer_agent_bindings_running_agent() -> None:
    """Test agent bindings for a running agent."""
    footer = KeybindingFooter()
    agent = _make_agent(status="RUNNING")

    bindings = footer._compute_agent_bindings(agent)
    binding_keys = [b[0] for b in bindings]

    assert "x" in binding_keys  # Kill is available
    assert "r" in binding_keys  # Revive chat is available


def test_keybinding_footer_agent_bindings_completed_agent_with_chat() -> None:
    """Test agent bindings for completed agent with chat file."""
    footer = KeybindingFooter()
    agent = _make_agent(status="NO CHANGES", response_path="/tmp/chat.md")

    bindings = footer._compute_agent_bindings(agent)
    binding_keys = [b[0] for b in bindings]

    assert "x" in binding_keys  # Dismiss is available
    assert "e" in binding_keys  # Edit chat is available
    assert "%" in binding_keys  # Copy chat is available


def test_keybinding_footer_agent_bindings_diff_visible() -> None:
    """Test agent bindings when diff panel is visible."""
    footer = KeybindingFooter()
    agent = _make_agent(status="RUNNING")

    bindings = footer._compute_agent_bindings(agent, diff_visible=True)
    binding_keys = [b[0] for b in bindings]

    assert "l" in binding_keys  # Layout toggle is available
