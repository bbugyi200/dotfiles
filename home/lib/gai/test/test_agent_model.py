"""Tests for the Agent model and AgentType enum."""

from datetime import datetime, timedelta

from ace.tui.models.agent import Agent, AgentType

# --- Agent Model Tests ---


def test_agent_display_type() -> None:
    """Test Agent.display_type property."""
    agent = Agent(
        agent_type=AgentType.FIX_HOOK,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=None,
    )
    assert agent.display_type == "fix-hook"


def test_agent_display_type_running() -> None:
    """Test Agent.display_type for RUNNING type."""
    agent = Agent(
        agent_type=AgentType.RUNNING,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=None,
        workspace_num=1,
        workflow="fix-tests",
    )
    assert agent.display_type == "run"


def test_agent_display_type_mentor() -> None:
    """Test Agent.display_type for MENTOR type."""
    agent = Agent(
        agent_type=AgentType.MENTOR,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=None,
    )
    assert agent.display_type == "mentor"


def test_agent_display_type_crs() -> None:
    """Test Agent.display_type for CRS type."""
    agent = Agent(
        agent_type=AgentType.CRS,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=None,
    )
    assert agent.display_type == "crs"


def test_agent_display_type_summarize() -> None:
    """Test Agent.display_type for SUMMARIZE type."""
    agent = Agent(
        agent_type=AgentType.SUMMARIZE,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=None,
    )
    assert agent.display_type == "summarize"


def test_agent_display_label() -> None:
    """Test Agent.display_label property."""
    agent = Agent(
        agent_type=AgentType.FIX_HOOK,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=None,
    )
    assert agent.display_label == "[fix-hook] my_feature"


def test_agent_start_time_display_with_time() -> None:
    """Test Agent.start_time_display with a valid time."""
    start = datetime(2025, 1, 10, 14, 30, 45)
    agent = Agent(
        agent_type=AgentType.FIX_HOOK,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=start,
    )
    assert agent.start_time_display == "2025-01-10 14:30:45"


def test_agent_start_time_display_without_time() -> None:
    """Test Agent.start_time_display when time is None."""
    agent = Agent(
        agent_type=AgentType.FIX_HOOK,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=None,
    )
    assert agent.start_time_display == "Unknown"


def test_agent_start_time_short_with_time() -> None:
    """Test Agent.start_time_short with a valid time."""
    start = datetime(2025, 1, 10, 14, 30, 45)
    agent = Agent(
        agent_type=AgentType.FIX_HOOK,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=start,
    )
    assert agent.start_time_short == "14:30"


def test_agent_start_time_short_without_time() -> None:
    """Test Agent.start_time_short when time is None."""
    agent = Agent(
        agent_type=AgentType.FIX_HOOK,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=None,
    )
    assert agent.start_time_short == "?"


def test_agent_duration_display_without_time() -> None:
    """Test Agent.duration_display when time is None."""
    agent = Agent(
        agent_type=AgentType.FIX_HOOK,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=None,
    )
    assert agent.duration_display == "?"


def test_agent_duration_display_seconds() -> None:
    """Test Agent.duration_display for seconds only."""
    start = datetime.now() - timedelta(seconds=45)
    agent = Agent(
        agent_type=AgentType.FIX_HOOK,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=start,
    )
    # Should be approximately 45s
    assert "s" in agent.duration_display
    assert "m" not in agent.duration_display


def test_agent_duration_display_minutes() -> None:
    """Test Agent.duration_display for minutes."""
    start = datetime.now() - timedelta(minutes=5, seconds=30)
    agent = Agent(
        agent_type=AgentType.FIX_HOOK,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=start,
    )
    # Should be approximately 5m30s
    assert "m" in agent.duration_display
    assert "h" not in agent.duration_display


def test_agent_duration_display_hours() -> None:
    """Test Agent.duration_display for hours."""
    start = datetime.now() - timedelta(hours=2, minutes=15)
    agent = Agent(
        agent_type=AgentType.FIX_HOOK,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=start,
    )
    # Should be approximately 2h15m
    assert "h" in agent.duration_display


# --- AgentType Enum Tests ---


def test_agent_type_values() -> None:
    """Test AgentType enum values."""
    assert AgentType.RUNNING.value == "run"
    assert AgentType.FIX_HOOK.value == "fix-hook"
    assert AgentType.SUMMARIZE.value == "summarize"
    assert AgentType.MENTOR.value == "mentor"
    assert AgentType.CRS.value == "crs"


def test_agent_optional_fields() -> None:
    """Test Agent with all optional fields."""
    start = datetime.now()
    agent = Agent(
        agent_type=AgentType.FIX_HOOK,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=start,
        workspace_num=5,
        workflow="fix-tests",
        hook_command="bb_test",
        commit_entry_id="1",
        mentor_profile="profile1",
        mentor_name="mentor1",
        reviewer="critique",
        pid=12345,
        raw_suffix="fix_hook-12345-251230_151429",
    )
    assert agent.workspace_num == 5
    assert agent.workflow == "fix-tests"
    assert agent.hook_command == "bb_test"
    assert agent.commit_entry_id == "1"
    assert agent.mentor_profile == "profile1"
    assert agent.mentor_name == "mentor1"
    assert agent.reviewer == "critique"
    assert agent.pid == 12345
    assert agent.raw_suffix == "fix_hook-12345-251230_151429"
