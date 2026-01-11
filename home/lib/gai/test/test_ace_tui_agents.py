"""Tests for the ace TUI Agents tab."""

from datetime import datetime, timedelta
from unittest.mock import patch

from ace.tui.models.agent import Agent, AgentType
from ace.tui.models.agent_loader import (
    _parse_timestamp_from_suffix,
    load_all_agents,
)

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


# --- Agent Loader Tests ---


def test_parse_timestamp_from_suffix_new_format() -> None:
    """Test parsing timestamp from new format: agent-PID-timestamp."""
    suffix = "fix_hook-12345-251230_151429"
    result = _parse_timestamp_from_suffix(suffix)
    assert result is not None
    assert result.year == 2025
    assert result.month == 12
    assert result.day == 30
    assert result.hour == 15
    assert result.minute == 14
    assert result.second == 29


def test_parse_timestamp_from_suffix_legacy_format() -> None:
    """Test parsing timestamp from legacy format: agent-timestamp."""
    suffix = "fix_hook-251230_151429"
    result = _parse_timestamp_from_suffix(suffix)
    assert result is not None
    assert result.year == 2025
    assert result.month == 12
    assert result.day == 30


def test_parse_timestamp_from_suffix_bare_timestamp() -> None:
    """Test parsing bare timestamp format."""
    suffix = "251230_151429"
    result = _parse_timestamp_from_suffix(suffix)
    assert result is not None
    assert result.year == 2025
    assert result.month == 12


def test_parse_timestamp_from_suffix_crs_format() -> None:
    """Test parsing CRS format: crs-timestamp."""
    suffix = "crs-251230_151429"
    result = _parse_timestamp_from_suffix(suffix)
    assert result is not None
    assert result.year == 2025


def test_parse_timestamp_from_suffix_none() -> None:
    """Test parsing None suffix."""
    result = _parse_timestamp_from_suffix(None)
    assert result is None


def test_parse_timestamp_from_suffix_invalid() -> None:
    """Test parsing invalid suffix."""
    result = _parse_timestamp_from_suffix("invalid")
    assert result is None


def test_parse_timestamp_from_suffix_invalid_timestamp() -> None:
    """Test parsing suffix with invalid timestamp format."""
    result = _parse_timestamp_from_suffix("fix_hook-12345-invalid")
    assert result is None


def test_load_all_agents_empty() -> None:
    """Test load_all_agents with no project files."""
    with (
        patch("ace.tui.models.agent_loader._get_all_project_files", return_value=[]),
        patch("ace.tui.models.agent_loader.find_all_changespecs", return_value=[]),
    ):
        agents = load_all_agents()
        assert agents == []


def test_load_all_agents_with_running_claims() -> None:
    """Test load_all_agents with RUNNING field claims."""
    from unittest.mock import MagicMock

    mock_claim = MagicMock()
    mock_claim.workspace_num = 1
    mock_claim.workflow = "fix-tests"
    mock_claim.cl_name = "my_feature"

    with (
        patch(
            "ace.tui.models.agent_loader._get_all_project_files",
            return_value=["/tmp/test.gp"],
        ),
        patch(
            "ace.tui.models.agent_loader.get_claimed_workspaces",
            return_value=[mock_claim],
        ),
        patch("ace.tui.models.agent_loader.find_all_changespecs", return_value=[]),
    ):
        agents = load_all_agents()
        assert len(agents) == 1
        assert agents[0].agent_type == AgentType.RUNNING
        assert agents[0].cl_name == "my_feature"
        assert agents[0].workspace_num == 1
        assert agents[0].workflow == "fix-tests"


def test_load_all_agents_sorting() -> None:
    """Test that agents are sorted by start time, newest first."""
    from unittest.mock import MagicMock

    # Create mock claims with different times
    mock_claim1 = MagicMock()
    mock_claim1.workspace_num = 1
    mock_claim1.workflow = "fix-tests"
    mock_claim1.cl_name = "feature_a"

    mock_claim2 = MagicMock()
    mock_claim2.workspace_num = 2
    mock_claim2.workflow = "run"
    mock_claim2.cl_name = "feature_b"

    with (
        patch(
            "ace.tui.models.agent_loader._get_all_project_files",
            return_value=["/tmp/test.gp"],
        ),
        patch(
            "ace.tui.models.agent_loader.get_claimed_workspaces",
            return_value=[mock_claim1, mock_claim2],
        ),
        patch("ace.tui.models.agent_loader.find_all_changespecs", return_value=[]),
    ):
        agents = load_all_agents()
        assert len(agents) == 2
        # Both have no start_time, so order is preserved
        assert agents[0].cl_name == "feature_a"
        assert agents[1].cl_name == "feature_b"


def test_load_all_agents_with_hook_agents() -> None:
    """Test load_all_agents with hook agents from ChangeSpec."""
    from ace.changespec import ChangeSpec, HookEntry, HookStatusLine

    mock_status_line = HookStatusLine(
        commit_entry_num="1",
        timestamp="251230_151429",
        status="RUNNING",
        suffix="fix_hook-12345-251230_151429",
        suffix_type="running_agent",
    )

    mock_hook = HookEntry(command="bb_test", status_lines=[mock_status_line])

    mock_cs = ChangeSpec(
        name="my_feature",
        description="Test",
        parent=None,
        cl="12345",
        status="Drafted",
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
        hooks=[mock_hook],
    )

    with (
        patch(
            "ace.tui.models.agent_loader._get_all_project_files",
            return_value=[],
        ),
        patch(
            "ace.tui.models.agent_loader.find_all_changespecs",
            return_value=[mock_cs],
        ),
    ):
        agents = load_all_agents()
        assert len(agents) == 1
        assert agents[0].agent_type == AgentType.FIX_HOOK
        assert agents[0].cl_name == "my_feature"
        assert agents[0].hook_command == "bb_test"


def test_load_all_agents_with_summarize_agents() -> None:
    """Test load_all_agents identifies summarize agents correctly."""
    from ace.changespec import ChangeSpec, HookEntry, HookStatusLine

    mock_status_line = HookStatusLine(
        commit_entry_num="1",
        timestamp="251230_151429",
        status="RUNNING",
        suffix="summarize_hook-12345-251230_151429",
        suffix_type="running_agent",
    )

    mock_hook = HookEntry(command="bb_test", status_lines=[mock_status_line])

    mock_cs = ChangeSpec(
        name="my_feature",
        description="Test",
        parent=None,
        cl="12345",
        status="Drafted",
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
        hooks=[mock_hook],
    )

    with (
        patch(
            "ace.tui.models.agent_loader._get_all_project_files",
            return_value=[],
        ),
        patch(
            "ace.tui.models.agent_loader.find_all_changespecs",
            return_value=[mock_cs],
        ),
    ):
        agents = load_all_agents()
        assert len(agents) == 1
        assert agents[0].agent_type == AgentType.SUMMARIZE


def test_load_all_agents_with_mentor_agents() -> None:
    """Test load_all_agents with mentor agents from ChangeSpec."""
    from ace.changespec import ChangeSpec, MentorEntry, MentorStatusLine

    mock_status_line = MentorStatusLine(
        profile_name="profile1",
        mentor_name="mentor1",
        status="RUNNING",
        suffix="mentor_complete-12345-251230_151429",
        suffix_type="running_agent",
    )

    mock_mentor = MentorEntry(
        entry_id="1", profiles=["profile1"], status_lines=[mock_status_line]
    )

    mock_cs = ChangeSpec(
        name="my_feature",
        description="Test",
        parent=None,
        cl="12345",
        status="Drafted",
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
        mentors=[mock_mentor],
    )

    with (
        patch(
            "ace.tui.models.agent_loader._get_all_project_files",
            return_value=[],
        ),
        patch(
            "ace.tui.models.agent_loader.find_all_changespecs",
            return_value=[mock_cs],
        ),
    ):
        agents = load_all_agents()
        assert len(agents) == 1
        assert agents[0].agent_type == AgentType.MENTOR
        assert agents[0].mentor_profile == "profile1"
        assert agents[0].mentor_name == "mentor1"


def test_load_all_agents_with_crs_agents() -> None:
    """Test load_all_agents with CRS agents from ChangeSpec."""
    from ace.changespec import ChangeSpec, CommentEntry

    mock_comment = CommentEntry(
        reviewer="critique",
        file_path="~/.gai/comments/test.json",
        suffix="crs-251230_151429",
        suffix_type="running_agent",
    )

    mock_cs = ChangeSpec(
        name="my_feature",
        description="Test",
        parent=None,
        cl="12345",
        status="Drafted",
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
        comments=[mock_comment],
    )

    with (
        patch(
            "ace.tui.models.agent_loader._get_all_project_files",
            return_value=[],
        ),
        patch(
            "ace.tui.models.agent_loader.find_all_changespecs",
            return_value=[mock_cs],
        ),
    ):
        agents = load_all_agents()
        assert len(agents) == 1
        assert agents[0].agent_type == AgentType.CRS
        assert agents[0].reviewer == "critique"
