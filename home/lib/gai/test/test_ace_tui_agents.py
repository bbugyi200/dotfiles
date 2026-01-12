"""Tests for the ace TUI Agents tab."""

from datetime import datetime, timedelta
from unittest.mock import patch

from ace.tui.models.agent import Agent, AgentType
from ace.tui.models.agent_loader import (
    _extract_timestamp_from_workflow,
    _extract_timestamp_str_from_suffix,
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


# --- Timestamp Extraction Helper Tests ---


def test_extract_timestamp_str_from_suffix_new_format() -> None:
    """Test extracting timestamp from new format: agent-PID-timestamp."""
    result = _extract_timestamp_str_from_suffix("mentor_complete-1855023-260112_134051")
    assert result == "260112_134051"


def test_extract_timestamp_str_from_suffix_fix_hook() -> None:
    """Test extracting timestamp from fix-hook suffix."""
    result = _extract_timestamp_str_from_suffix("fix_hook-12345-251230_151429")
    assert result == "251230_151429"


def test_extract_timestamp_str_from_suffix_crs() -> None:
    """Test extracting timestamp from CRS suffix."""
    result = _extract_timestamp_str_from_suffix("crs-12345-251230_151429")
    assert result == "251230_151429"


def test_extract_timestamp_str_from_suffix_none() -> None:
    """Test extracting timestamp from None suffix."""
    result = _extract_timestamp_str_from_suffix(None)
    assert result is None


def test_extract_timestamp_str_from_suffix_no_dash() -> None:
    """Test extracting timestamp from suffix without dashes."""
    result = _extract_timestamp_str_from_suffix("nodashes")
    assert result is None


def test_extract_timestamp_str_from_suffix_invalid_format() -> None:
    """Test extracting timestamp from suffix with invalid format."""
    result = _extract_timestamp_str_from_suffix("fix_hook-12345-invalid")
    assert result is None


def test_extract_timestamp_from_workflow_mentor() -> None:
    """Test extracting timestamp from loop(mentor) workflow."""
    result = _extract_timestamp_from_workflow("loop(mentor)-complete-260112_134051")
    assert result == "260112_134051"


def test_extract_timestamp_from_workflow_fix_hook() -> None:
    """Test extracting timestamp from loop(fix-hook) workflow."""
    result = _extract_timestamp_from_workflow("loop(fix-hook)-251230_151429")
    assert result == "251230_151429"


def test_extract_timestamp_from_workflow_crs() -> None:
    """Test extracting timestamp from loop(crs) workflow."""
    result = _extract_timestamp_from_workflow("loop(crs)-critique-251230_151429")
    assert result == "251230_151429"


def test_extract_timestamp_from_workflow_ace_run() -> None:
    """Test extracting timestamp from ace(run) workflow."""
    result = _extract_timestamp_from_workflow("ace(run)-260112_134051")
    assert result == "260112_134051"


def test_extract_timestamp_from_workflow_none() -> None:
    """Test extracting timestamp from None workflow."""
    result = _extract_timestamp_from_workflow(None)
    assert result is None


def test_extract_timestamp_from_workflow_no_dash() -> None:
    """Test extracting timestamp from workflow without dashes."""
    result = _extract_timestamp_from_workflow("nodashes")
    assert result is None


def test_extract_timestamp_from_workflow_no_timestamp() -> None:
    """Test extracting timestamp from workflow without timestamp."""
    result = _extract_timestamp_from_workflow("loop(crs)-critique")
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
        patch(
            "ace.tui.models.agent_loader.is_process_running",
            return_value=True,
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
        patch(
            "ace.tui.models.agent_loader.is_process_running",
            return_value=True,
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
        patch(
            "ace.tui.models.agent_loader.is_process_running",
            return_value=True,
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


def test_load_all_agents_filters_hook_processes() -> None:
    """Test that RUNNING entries with loop(hooks) workflow are filtered out."""
    from unittest.mock import MagicMock

    # Mock a RUNNING claim with loop(hooks)-1 workflow (hook process, not agent)
    mock_claim = MagicMock()
    mock_claim.workspace_num = 100
    mock_claim.workflow = "loop(hooks)-1"
    mock_claim.cl_name = "my_feature"
    mock_claim.pid = 12345
    mock_claim.artifacts_timestamp = None

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
        # Hook process should be filtered out
        assert len(agents) == 0


def test_load_all_agents_includes_loop_fix_hook() -> None:
    """Test that RUNNING entries with loop(fix-hook) workflow are included."""
    from unittest.mock import MagicMock

    # Mock a RUNNING claim with loop(fix-hook)-timestamp workflow
    mock_claim = MagicMock()
    mock_claim.workspace_num = 100
    mock_claim.workflow = "loop(fix-hook)-251230_151429"
    mock_claim.cl_name = "my_feature"
    mock_claim.pid = None  # No PID to skip process check
    mock_claim.artifacts_timestamp = "20251230151429"

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
        # Agent workflow should be included
        assert len(agents) == 1
        assert agents[0].agent_type == AgentType.RUNNING
        assert agents[0].workflow == "loop(fix-hook)-251230_151429"


def test_load_all_agents_deduplicates_by_timestamp() -> None:
    """Test that agents with same timestamp from different sources are deduplicated.

    This is the real-world scenario: loop process (RUNNING) has a different PID than
    the subprocess (ChangeSpec), but they share the same timestamp.
    """
    from unittest.mock import MagicMock

    from ace.changespec import ChangeSpec, HookEntry, HookStatusLine

    # Create RUNNING entry with loop process PID 11111 and timestamp in workflow
    mock_claim = MagicMock()
    mock_claim.workspace_num = 100
    mock_claim.workflow = "loop(fix-hook)-251230_151429"  # Timestamp here
    mock_claim.cl_name = "my_feature"
    mock_claim.pid = 11111  # Loop process PID
    mock_claim.artifacts_timestamp = "20251230151429"

    # Create HOOKS entry with different subprocess PID 22222 but same timestamp
    mock_status_line = HookStatusLine(
        commit_entry_num="1",
        timestamp="251230_151429",
        status="RUNNING",
        suffix="fix_hook-22222-251230_151429",  # Different PID, same timestamp
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
            return_value=["/tmp/test.gp"],
        ),
        patch(
            "ace.tui.models.agent_loader.get_claimed_workspaces",
            return_value=[mock_claim],
        ),
        patch(
            "ace.tui.models.agent_loader.find_all_changespecs",
            return_value=[mock_cs],
        ),
        patch(
            "ace.tui.models.agent_loader.is_process_running",
            return_value=True,
        ),
    ):
        agents = load_all_agents()
        # Should have only one agent (deduplicated by timestamp)
        assert len(agents) == 1
        # Should prefer FIX_HOOK (more specific) over RUNNING
        assert agents[0].agent_type == AgentType.FIX_HOOK
        assert agents[0].pid == 22222  # Subprocess PID


def test_load_all_agents_dedup_preserves_workspace_num() -> None:
    """Test that workspace_num from RUNNING entry is preserved after dedup.

    When deduplicating by timestamp, the workspace_num from the RUNNING entry
    should be copied to the matched ChangeSpec entry.
    """
    from unittest.mock import MagicMock

    from ace.changespec import ChangeSpec, HookEntry, HookStatusLine

    # Create RUNNING entry with loop PID 11111 and workspace_num=5
    mock_claim = MagicMock()
    mock_claim.workspace_num = 5
    mock_claim.workflow = "loop(fix-hook)-251230_151429"  # Timestamp here
    mock_claim.cl_name = "my_feature"
    mock_claim.pid = 11111  # Loop process PID
    mock_claim.artifacts_timestamp = "20251230151429"

    # Create HOOKS entry with different subprocess PID 22222, no workspace_num
    mock_status_line = HookStatusLine(
        commit_entry_num="1",
        timestamp="251230_151429",
        status="RUNNING",
        suffix="fix_hook-22222-251230_151429",  # Different PID, same timestamp
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
            return_value=["/tmp/test.gp"],
        ),
        patch(
            "ace.tui.models.agent_loader.get_claimed_workspaces",
            return_value=[mock_claim],
        ),
        patch(
            "ace.tui.models.agent_loader.find_all_changespecs",
            return_value=[mock_cs],
        ),
        patch(
            "ace.tui.models.agent_loader.is_process_running",
            return_value=True,
        ),
    ):
        agents = load_all_agents()
        assert len(agents) == 1
        # Should have FIX_HOOK type with workspace_num copied from RUNNING entry
        assert agents[0].agent_type == AgentType.FIX_HOOK
        assert agents[0].workspace_num == 5


def test_load_all_agents_dedup_mentor_by_timestamp() -> None:
    """Test deduplication of mentor agents by timestamp."""
    from unittest.mock import MagicMock

    from ace.changespec import ChangeSpec, MentorEntry, MentorStatusLine

    # Create RUNNING entry with loop(mentor) workflow and timestamp
    mock_claim = MagicMock()
    mock_claim.workspace_num = 3
    mock_claim.workflow = "loop(mentor)-complete-260112_134051"  # Timestamp here
    mock_claim.cl_name = "foobar_boom"
    mock_claim.pid = 1527683  # Loop process PID
    mock_claim.artifacts_timestamp = "20260112134051"

    # Create MENTORS entry with different subprocess PID but same timestamp
    mock_status_line = MentorStatusLine(
        profile_name="profile1",
        mentor_name="mentor1",
        status="RUNNING",
        suffix="mentor_complete-1855023-260112_134051",  # Different PID, same timestamp
        suffix_type="running_agent",
    )

    mock_mentor = MentorEntry(
        entry_id="1", profiles=["profile1"], status_lines=[mock_status_line]
    )

    mock_cs = ChangeSpec(
        name="foobar_boom",
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
            return_value=["/tmp/test.gp"],
        ),
        patch(
            "ace.tui.models.agent_loader.get_claimed_workspaces",
            return_value=[mock_claim],
        ),
        patch(
            "ace.tui.models.agent_loader.find_all_changespecs",
            return_value=[mock_cs],
        ),
        patch(
            "ace.tui.models.agent_loader.is_process_running",
            return_value=True,
        ),
    ):
        agents = load_all_agents()
        # Should have only one agent (deduplicated by timestamp)
        assert len(agents) == 1
        # Should prefer MENTOR (more specific) over RUNNING
        assert agents[0].agent_type == AgentType.MENTOR
        assert agents[0].pid == 1855023  # Subprocess PID
        assert agents[0].workspace_num == 3  # Copied from RUNNING entry


# --- Kill Agent Tests ---


def test_kill_process_group_success() -> None:
    """Test _kill_process_group sends SIGTERM successfully."""
    from ace.tui.actions.agents import AgentsMixin

    class MockApp(AgentsMixin):
        def __init__(self) -> None:
            self._notifications: list[tuple[str, str]] = []

        def notify(self, msg: str, severity: str = "information") -> None:
            self._notifications.append((msg, severity))

    app = MockApp()

    with patch("ace.tui.actions.agents.os.killpg") as mock_killpg:
        result = app._kill_process_group(12345)
        mock_killpg.assert_called_once_with(12345, 15)  # signal.SIGTERM = 15
        assert result is True


def test_kill_process_group_process_already_dead() -> None:
    """Test _kill_process_group handles ProcessLookupError."""
    from ace.tui.actions.agents import AgentsMixin

    class MockApp(AgentsMixin):
        def __init__(self) -> None:
            self._notifications: list[tuple[str, str]] = []

        def notify(self, msg: str, severity: str = "information") -> None:
            self._notifications.append((msg, severity))

    app = MockApp()

    with patch("ace.tui.actions.agents.os.killpg", side_effect=ProcessLookupError):
        result = app._kill_process_group(12345)
        assert result is True  # Still considered success


def test_kill_process_group_permission_error() -> None:
    """Test _kill_process_group handles PermissionError."""
    from ace.tui.actions.agents import AgentsMixin

    class MockApp(AgentsMixin):
        def __init__(self) -> None:
            self._notifications: list[tuple[str, str]] = []

        def notify(self, msg: str, severity: str = "information") -> None:
            self._notifications.append((msg, severity))

    app = MockApp()

    with patch("ace.tui.actions.agents.os.killpg", side_effect=PermissionError):
        result = app._kill_process_group(12345)
        assert result is False  # Permission error is a failure
        assert len(app._notifications) == 1
        assert "Permission denied" in app._notifications[0][0]
        assert app._notifications[0][1] == "error"


def test_kill_running_agent_releases_workspace() -> None:
    """Test _kill_running_agent kills process and releases workspace."""
    from ace.tui.actions.agents import AgentsMixin

    class MockApp(AgentsMixin):
        def __init__(self) -> None:
            self._notifications: list[tuple[str, str]] = []

        def notify(self, msg: str, severity: str = "information") -> None:
            self._notifications.append((msg, severity))

    app = MockApp()

    agent = Agent(
        agent_type=AgentType.RUNNING,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=None,
        workspace_num=5,
        workflow="fix-tests",
        pid=12345,
    )

    with (
        patch("ace.tui.actions.agents.os.killpg") as mock_killpg,
        patch("running_field.release_workspace") as mock_release,
    ):
        app._kill_running_agent(agent)

        mock_killpg.assert_called_once_with(12345, 15)
        mock_release.assert_called_once_with(
            "/tmp/test.gp", 5, "fix-tests", "my_feature"
        )
        assert len(app._notifications) == 1
        assert "Killed agent" in app._notifications[0][0]


def test_kill_hook_agent_marks_as_killed() -> None:
    """Test _kill_hook_agent kills process and marks hook as killed."""
    from ace.changespec import ChangeSpec, HookEntry, HookStatusLine
    from ace.tui.actions.agents import AgentsMixin

    class MockApp(AgentsMixin):
        def __init__(self) -> None:
            self._notifications: list[tuple[str, str]] = []

        def notify(self, msg: str, severity: str = "information") -> None:
            self._notifications.append((msg, severity))

    app = MockApp()

    agent = Agent(
        agent_type=AgentType.FIX_HOOK,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=None,
        hook_command="bb_test",
        pid=12345,
        raw_suffix="fix_hook-12345-251230_151429",
    )

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
        patch("ace.tui.actions.agents.os.killpg") as mock_killpg,
        patch("ace.changespec.parse_project_file", return_value=[mock_cs]),
        patch("ace.hooks.processes.mark_hook_agents_as_killed") as mock_mark,
        patch("ace.hooks.update_changespec_hooks_field") as mock_update,
    ):
        mock_mark.return_value = [mock_hook]
        app._kill_hook_agent(agent)

        mock_killpg.assert_called_once_with(12345, 15)
        mock_mark.assert_called_once()
        mock_update.assert_called_once()
        assert len(app._notifications) == 1
        assert "Killed hook agent" in app._notifications[0][0]


def test_kill_mentor_agent_marks_as_killed() -> None:
    """Test _kill_mentor_agent kills process and marks mentor as killed."""
    from ace.changespec import ChangeSpec, MentorEntry, MentorStatusLine
    from ace.tui.actions.agents import AgentsMixin

    class MockApp(AgentsMixin):
        def __init__(self) -> None:
            self._notifications: list[tuple[str, str]] = []

        def notify(self, msg: str, severity: str = "information") -> None:
            self._notifications.append((msg, severity))

    app = MockApp()

    agent = Agent(
        agent_type=AgentType.MENTOR,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=None,
        mentor_profile="profile1",
        mentor_name="mentor1",
        pid=12345,
        raw_suffix="mentor_complete-12345-251230_151429",
    )

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
        patch("ace.tui.actions.agents.os.killpg") as mock_killpg,
        patch("ace.changespec.parse_project_file", return_value=[mock_cs]),
        patch("ace.hooks.processes.mark_mentor_agents_as_killed") as mock_mark,
        patch("ace.mentors.update_changespec_mentors_field") as mock_update,
    ):
        mock_mark.return_value = [mock_mentor]
        app._kill_mentor_agent(agent)

        mock_killpg.assert_called_once_with(12345, 15)
        mock_mark.assert_called_once()
        mock_update.assert_called_once()
        assert len(app._notifications) == 1
        assert "Killed mentor agent" in app._notifications[0][0]


def test_kill_crs_agent_marks_as_killed() -> None:
    """Test _kill_crs_agent kills process and marks comment as killed."""
    from ace.changespec import ChangeSpec, CommentEntry
    from ace.tui.actions.agents import AgentsMixin

    class MockApp(AgentsMixin):
        def __init__(self) -> None:
            self._notifications: list[tuple[str, str]] = []

        def notify(self, msg: str, severity: str = "information") -> None:
            self._notifications.append((msg, severity))

    app = MockApp()

    agent = Agent(
        agent_type=AgentType.CRS,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=None,
        reviewer="critique",
        pid=12345,
        raw_suffix="crs-12345-251230_151429",
    )

    mock_comment = CommentEntry(
        reviewer="critique",
        file_path="~/.gai/comments/test.json",
        suffix="crs-12345-251230_151429",
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
        patch("ace.tui.actions.agents.os.killpg") as mock_killpg,
        patch("ace.changespec.parse_project_file", return_value=[mock_cs]),
        patch("ace.comments.operations.mark_comment_agents_as_killed") as mock_mark,
        patch("ace.comments.update_changespec_comments_field") as mock_update,
    ):
        mock_mark.return_value = [mock_comment]
        app._kill_crs_agent(agent)

        mock_killpg.assert_called_once_with(12345, 15)
        mock_mark.assert_called_once()
        mock_update.assert_called_once()
        assert len(app._notifications) == 1
        assert "Killed CRS agent" in app._notifications[0][0]


def test_kill_agent_with_no_pid() -> None:
    """Test that agent with no PID shows warning and does nothing."""
    from ace.tui.actions.agents import AgentsMixin

    class MockApp(AgentsMixin):
        def __init__(self) -> None:
            self._notifications: list[tuple[str, str]] = []

        def notify(self, msg: str, severity: str = "information") -> None:
            self._notifications.append((msg, severity))

    app = MockApp()

    agent = Agent(
        agent_type=AgentType.FIX_HOOK,
        cl_name="my_feature",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=None,
        pid=None,  # No PID
    )

    with patch("ace.tui.actions.agents.os.killpg") as mock_killpg:
        app._kill_hook_agent(agent)
        mock_killpg.assert_not_called()
