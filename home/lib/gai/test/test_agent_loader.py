"""Tests for the load_all_agents function."""

from unittest.mock import MagicMock, patch

from ace.tui.models.agent import AgentType
from ace.tui.models.agent_loader import _get_status_priority, load_all_agents


def test_load_all_agents_empty() -> None:
    """Test load_all_agents with no project files."""
    with (
        patch("ace.tui.models.agent_loader.get_all_project_files", return_value=[]),
        patch("ace.tui.models.agent_loader.find_all_changespecs", return_value=[]),
    ):
        agents = load_all_agents()
        assert agents == []


def test_load_all_agents_with_running_claims() -> None:
    """Test load_all_agents with RUNNING field claims."""
    mock_claim = MagicMock()
    mock_claim.workspace_num = 1
    mock_claim.workflow = "crs"
    mock_claim.cl_name = "my_feature"

    with (
        patch(
            "ace.tui.models.agent_loader.get_all_project_files",
            return_value=["/tmp/test.gp"],
        ),
        patch(
            "ace.tui.models._loaders.get_claimed_workspaces",
            return_value=[mock_claim],
        ),
        patch("ace.tui.models.agent_loader.find_all_changespecs", return_value=[]),
    ):
        agents = load_all_agents()
        assert len(agents) == 1
        assert agents[0].agent_type == AgentType.RUNNING
        assert agents[0].cl_name == "my_feature"
        assert agents[0].workspace_num == 1
        assert agents[0].workflow == "crs"


def test_load_all_agents_sorting() -> None:
    """Test that agents are sorted by start time, newest first."""
    # Create mock claims with different times
    mock_claim1 = MagicMock()
    mock_claim1.workspace_num = 1
    mock_claim1.workflow = "crs"
    mock_claim1.cl_name = "feature_a"

    mock_claim2 = MagicMock()
    mock_claim2.workspace_num = 2
    mock_claim2.workflow = "run"
    mock_claim2.cl_name = "feature_b"

    with (
        patch(
            "ace.tui.models.agent_loader.get_all_project_files",
            return_value=["/tmp/test.gp"],
        ),
        patch(
            "ace.tui.models._loaders.get_claimed_workspaces",
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
            "ace.tui.models.agent_loader.get_all_project_files",
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
            "ace.tui.models.agent_loader.get_all_project_files",
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
        timestamp="251231_120000",
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
            "ace.tui.models.agent_loader.get_all_project_files",
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
            "ace.tui.models.agent_loader.get_all_project_files",
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
    """Test that RUNNING entries with axe(hooks) workflow are filtered out."""
    # Mock a RUNNING claim with axe(hooks)-1 workflow (hook process, not agent)
    mock_claim = MagicMock()
    mock_claim.workspace_num = 100
    mock_claim.workflow = "axe(hooks)-1"
    mock_claim.cl_name = "my_feature"
    mock_claim.pid = 12345
    mock_claim.artifacts_timestamp = None

    with (
        patch(
            "ace.tui.models.agent_loader.get_all_project_files",
            return_value=["/tmp/test.gp"],
        ),
        patch(
            "ace.tui.models._loaders.get_claimed_workspaces",
            return_value=[mock_claim],
        ),
        patch("ace.tui.models.agent_loader.find_all_changespecs", return_value=[]),
    ):
        agents = load_all_agents()
        # Hook process should be filtered out
        assert len(agents) == 0


def test_load_all_agents_includes_axe_fix_hook() -> None:
    """Test that RUNNING entries with axe(fix-hook) workflow are included."""
    # Mock a RUNNING claim with axe(fix-hook)-timestamp workflow
    mock_claim = MagicMock()
    mock_claim.workspace_num = 100
    mock_claim.workflow = "axe(fix-hook)-251230_151429"
    mock_claim.cl_name = "my_feature"
    mock_claim.pid = None  # No PID to skip process check
    mock_claim.artifacts_timestamp = "20251230151429"

    with (
        patch(
            "ace.tui.models.agent_loader.get_all_project_files",
            return_value=["/tmp/test.gp"],
        ),
        patch(
            "ace.tui.models._loaders.get_claimed_workspaces",
            return_value=[mock_claim],
        ),
        patch("ace.tui.models.agent_loader.find_all_changespecs", return_value=[]),
    ):
        agents = load_all_agents()
        # Agent workflow should be included
        assert len(agents) == 1
        assert agents[0].agent_type == AgentType.RUNNING
        assert agents[0].workflow == "axe(fix-hook)-251230_151429"


def test_load_all_agents_deduplicates_by_timestamp() -> None:
    """Test that agents with same timestamp from different sources are deduplicated.

    This is the real-world scenario: axe process (RUNNING) has a different PID than
    the subprocess (ChangeSpec), but they share the same timestamp.
    """
    from ace.changespec import ChangeSpec, HookEntry, HookStatusLine

    # Create RUNNING entry with axe process PID 11111 and timestamp in workflow
    mock_claim = MagicMock()
    mock_claim.workspace_num = 100
    mock_claim.workflow = "axe(fix-hook)-251230_151429"  # Timestamp here
    mock_claim.cl_name = "my_feature"
    mock_claim.pid = 11111  # Axe process PID
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
            "ace.tui.models.agent_loader.get_all_project_files",
            return_value=["/tmp/test.gp"],
        ),
        patch(
            "ace.tui.models._loaders.get_claimed_workspaces",
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
    from ace.changespec import ChangeSpec, HookEntry, HookStatusLine

    # Create RUNNING entry with axe PID 11111 and workspace_num=5
    mock_claim = MagicMock()
    mock_claim.workspace_num = 5
    mock_claim.workflow = "axe(fix-hook)-251230_151429"  # Timestamp here
    mock_claim.cl_name = "my_feature"
    mock_claim.pid = 11111  # Axe process PID
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
            "ace.tui.models.agent_loader.get_all_project_files",
            return_value=["/tmp/test.gp"],
        ),
        patch(
            "ace.tui.models._loaders.get_claimed_workspaces",
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
    from ace.changespec import ChangeSpec, MentorEntry, MentorStatusLine

    # Create RUNNING entry with axe(mentor) workflow and timestamp
    mock_claim = MagicMock()
    mock_claim.workspace_num = 3
    mock_claim.workflow = "axe(mentor)-complete-260112_134051"  # Timestamp here
    mock_claim.cl_name = "foobar_boom"
    mock_claim.pid = 1527683  # Axe process PID
    mock_claim.artifacts_timestamp = "20260112134051"

    # Create MENTORS entry with different subprocess PID but same timestamp
    mock_status_line = MentorStatusLine(
        timestamp="251231_120000",
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
            "ace.tui.models.agent_loader.get_all_project_files",
            return_value=["/tmp/test.gp"],
        ),
        patch(
            "ace.tui.models._loaders.get_claimed_workspaces",
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


def test_workflow_steps_sorted_completed_before_running() -> None:
    """Test that workflow steps sort completed/failed before running/waiting."""
    # Test status priorities
    assert _get_status_priority("COMPLETED") == 0
    assert _get_status_priority("FAILED") == 0
    assert _get_status_priority("RUNNING") == 1
    assert _get_status_priority("WAITING INPUT") == 1
    assert _get_status_priority("UNKNOWN") == 1  # Unknown defaults to active


def test_workflow_dead_pid_marked_as_failed() -> None:
    """Test that a workflow with dead PID is marked as FAILED."""
    import json
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create workflow_state.json with running status and a PID
        project_dir = Path(tmpdir) / "myproject"
        workflow_dir = project_dir / "artifacts" / "workflow-deploy" / "20260101120000"
        workflow_dir.mkdir(parents=True)

        state = {
            "workflow_name": "deploy",
            "status": "running",
            "pid": 99999,
            "context": {"cl_name": "test_cl"},
            "steps": [],
        }
        (workflow_dir / "workflow_state.json").write_text(json.dumps(state))

        with (
            patch(
                "ace.tui.models._loaders.Path.home",
                return_value=Path(tmpdir).parent,
            ),
            patch(
                "ace.tui.models._loaders.is_process_running",
                return_value=False,
            ),
        ):
            # Point projects_dir to our tmpdir
            from ace.tui.models._loaders import load_workflow_states

            # We need to patch the projects_dir path
            with patch(
                "ace.tui.models._loaders.Path.home",
                return_value=Path(tmpdir),
            ):
                # Create the expected directory structure: ~/.gai/projects/<name>
                gai_projects = Path(tmpdir) / ".gai" / "projects" / "myproject"
                gai_artifacts = (
                    gai_projects / "artifacts" / "workflow-deploy" / "20260101120000"
                )
                gai_artifacts.mkdir(parents=True)
                gai_projects_gp = gai_projects / "myproject.gp"
                gai_projects_gp.touch()

                state_file = gai_artifacts / "workflow_state.json"
                state_file.write_text(json.dumps(state))

                entries = load_workflow_states()

        assert len(entries) == 1
        assert entries[0].status == "FAILED"


def test_workflow_alive_pid_stays_running() -> None:
    """Test that a workflow with alive PID stays RUNNING."""
    import json
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        gai_projects = Path(tmpdir) / ".gai" / "projects" / "myproject"
        gai_artifacts = (
            gai_projects / "artifacts" / "workflow-deploy" / "20260101120000"
        )
        gai_artifacts.mkdir(parents=True)
        (gai_projects / "myproject.gp").touch()

        state = {
            "workflow_name": "deploy",
            "status": "running",
            "pid": 99999,
            "context": {"cl_name": "test_cl"},
            "steps": [],
        }
        (gai_artifacts / "workflow_state.json").write_text(json.dumps(state))

        with (
            patch(
                "ace.tui.models._loaders.Path.home",
                return_value=Path(tmpdir),
            ),
            patch(
                "ace.tui.models._loaders.is_process_running",
                return_value=True,
            ),
        ):
            from ace.tui.models._loaders import load_workflow_states

            entries = load_workflow_states()

        assert len(entries) == 1
        assert entries[0].status == "RUNNING"


def test_workflow_waiting_hitl_dead_pid_marked_as_failed() -> None:
    """Test that a WAITING INPUT workflow with dead PID is marked as FAILED."""
    import json
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        gai_projects = Path(tmpdir) / ".gai" / "projects" / "myproject"
        gai_artifacts = (
            gai_projects / "artifacts" / "workflow-deploy" / "20260101120000"
        )
        gai_artifacts.mkdir(parents=True)
        (gai_projects / "myproject.gp").touch()

        state = {
            "workflow_name": "deploy",
            "status": "waiting_hitl",
            "pid": 99999,
            "context": {"cl_name": "test_cl"},
            "steps": [],
        }
        (gai_artifacts / "workflow_state.json").write_text(json.dumps(state))

        with (
            patch(
                "ace.tui.models._loaders.Path.home",
                return_value=Path(tmpdir),
            ),
            patch(
                "ace.tui.models._loaders.is_process_running",
                return_value=False,
            ),
        ):
            from ace.tui.models._loaders import load_workflow_states

            entries = load_workflow_states()

        assert len(entries) == 1
        assert entries[0].status == "FAILED"


def test_workflow_dedup_propagates_failed_status() -> None:
    """Test that dedup propagates FAILED status from workflow_state.json."""
    from ace.tui.models.agent import Agent, AgentType

    # Simulate RUNNING field entry (status=RUNNING, no PID)
    running_field_agent = Agent(
        agent_type=AgentType.WORKFLOW,
        cl_name="test_cl",
        project_file="/tmp/test.gp",
        status="RUNNING",
        start_time=None,
        workflow="deploy",
        raw_suffix="20260101120000",
        workspace_num=5,
    )

    # Simulate workflow_state.json entry (status=FAILED, with PID)
    workflow_state_agent = Agent(
        agent_type=AgentType.WORKFLOW,
        cl_name="test_cl",
        project_file="/tmp/test.gp",
        status="FAILED",
        start_time=None,
        workflow="deploy",
        raw_suffix="20260101120000",
        pid=121415,
    )

    with (
        patch(
            "ace.tui.models.agent_loader.get_all_project_files",
            return_value=[],
        ),
        patch(
            "ace.tui.models.agent_loader.find_all_changespecs",
            return_value=[],
        ),
        patch(
            "ace.tui.models.agent_loader.load_agents_from_running_field",
            return_value=[running_field_agent],
        ),
        patch(
            "ace.tui.models.agent_loader.load_done_agents",
            return_value=[],
        ),
        patch(
            "ace.tui.models.agent_loader.load_running_home_agents",
            return_value=[],
        ),
        patch(
            "ace.tui.models.agent_loader.load_workflow_agents",
            return_value=[workflow_state_agent],
        ),
        patch(
            "ace.tui.models.agent_loader.load_workflow_agent_steps",
            return_value=[],
        ),
    ):
        result = load_all_agents()

    # Should be deduplicated to one agent
    assert len(result) == 1
    # Status should be FAILED (propagated from workflow_state.json)
    assert result[0].status == "FAILED"
    # Workspace num should be preserved from RUNNING field entry
    assert result[0].workspace_num == 5
    # PID should be propagated from workflow_state.json
    assert result[0].pid == 121415
