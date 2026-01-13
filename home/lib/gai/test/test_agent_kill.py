"""Tests for kill agent functionality."""

from unittest.mock import patch

from ace.tui.models.agent import Agent, AgentType

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
        workflow="crs",
        pid=12345,
    )

    with (
        patch("ace.tui.actions.agents.os.killpg") as mock_killpg,
        patch("running_field.release_workspace") as mock_release,
    ):
        app._kill_running_agent(agent)

        mock_killpg.assert_called_once_with(12345, 15)
        mock_release.assert_called_once_with("/tmp/test.gp", 5, "crs", "my_feature")
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
