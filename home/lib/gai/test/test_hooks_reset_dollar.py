"""Tests for reset_dollar_hooks() in hooks/mutations.py."""

from unittest.mock import patch

from ace.changespec import (
    ChangeSpec,
    CommitEntry,
    HookEntry,
    HookStatusLine,
)
from ace.hooks.mutations import reset_dollar_hooks

# Patch targets: lazy imports are patched at their source modules,
# while rerun_delete_hooks_by_command lives in the same module.
_PATCH_PARSE = "ace.changespec.parse_project_file"
_PATCH_KILL = "ace.hooks.processes.kill_running_processes_for_hooks"
_PATCH_RERUN = "ace.hooks.mutations.rerun_delete_hooks_by_command"


def _make_changespec(
    name: str = "test_feature",
    hooks: list[HookEntry] | None = None,
    commits: list[CommitEntry] | None = None,
) -> ChangeSpec:
    """Create a ChangeSpec for testing."""
    return ChangeSpec(
        name=name,
        description="Test",
        parent=None,
        cl=None,
        status="WIP",
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
        hooks=hooks,
        commits=commits,
    )


def _make_commit(number: int, proposal_letter: str | None = None) -> CommitEntry:
    """Create a CommitEntry for testing."""
    return CommitEntry(
        number=number,
        note="Test commit",
        proposal_letter=proposal_letter,
    )


def _make_hook(
    command: str,
    commit_entry_num: str | None = None,
    status: str | None = None,
) -> HookEntry:
    """Create a HookEntry, optionally with a status line."""
    if commit_entry_num is None:
        return HookEntry(command=command)
    return HookEntry(
        command=command,
        status_lines=[
            HookStatusLine(
                commit_entry_num=commit_entry_num,
                timestamp="260101120000",
                status=status or "PASSED",
            )
        ],
    )


def test_no_hooks_is_noop() -> None:
    """No hooks -> returns True without modifying anything."""
    cs = _make_changespec(hooks=None, commits=[_make_commit(1)])
    with patch(_PATCH_PARSE, return_value=[cs]):
        assert reset_dollar_hooks("/tmp/test.gp", "test_feature") is True


def test_no_dollar_hooks_is_noop() -> None:
    """Only non-$ hooks -> returns True without modifying anything."""
    hooks = [_make_hook("flake8 src", "1", "PASSED")]
    cs = _make_changespec(hooks=hooks, commits=[_make_commit(1)])
    with patch(_PATCH_PARSE, return_value=[cs]):
        assert reset_dollar_hooks("/tmp/test.gp", "test_feature") is True


def test_no_commits_history_is_noop() -> None:
    """No COMMITS entries -> returns True without modifying anything."""
    hooks = [_make_hook("$bb_presubmit", "1", "PASSED")]
    cs = _make_changespec(hooks=hooks, commits=None)
    with patch(_PATCH_PARSE, return_value=[cs]):
        assert reset_dollar_hooks("/tmp/test.gp", "test_feature") is True


def test_dollar_hooks_kill_and_clear() -> None:
    """$ hooks with status lines -> kills processes and clears status."""
    hooks = [
        _make_hook("$bb_presubmit", "2", "PASSED"),
        _make_hook("flake8 src", "2", "PASSED"),
        _make_hook("$bb_lint", "2", "FAILED"),
    ]
    cs = _make_changespec(hooks=hooks, commits=[_make_commit(1), _make_commit(2)])

    with (
        patch(_PATCH_PARSE, return_value=[cs]),
        patch(_PATCH_KILL, return_value=2) as mock_kill,
        patch(_PATCH_RERUN, return_value=True) as mock_rerun,
    ):
        result = reset_dollar_hooks("/tmp/test.gp", "test_feature")

    assert result is True
    # Should kill with indices 0 and 2 (the $ hooks)
    mock_kill.assert_called_once_with(hooks, {0, 2})
    # Should clear status for entry "2" (the last commit)
    mock_rerun.assert_called_once_with(
        "/tmp/test.gp",
        "test_feature",
        commands_to_rerun={"$bb_presubmit", "$bb_lint"},
        commands_to_delete=set(),
        entry_ids_to_clear={"2"},
    )


def test_only_last_entry_id_cleared() -> None:
    """Only the most recent COMMITS entry ID should be cleared."""
    hooks = [_make_hook("$bb_presubmit", "1", "PASSED")]
    cs = _make_changespec(
        hooks=hooks,
        commits=[_make_commit(1), _make_commit(2), _make_commit(3)],
    )

    with (
        patch(_PATCH_PARSE, return_value=[cs]),
        patch(_PATCH_KILL, return_value=0),
        patch(_PATCH_RERUN, return_value=True) as mock_rerun,
    ):
        reset_dollar_hooks("/tmp/test.gp", "test_feature")

    # Should only clear entry "3" (the last commit), not "1" or "2"
    mock_rerun.assert_called_once()
    assert mock_rerun.call_args[1]["entry_ids_to_clear"] == {"3"}


def test_log_fn_receives_messages() -> None:
    """log_fn should receive reset and kill messages."""
    hooks = [
        _make_hook("$bb_presubmit", "1", "PASSED"),
        _make_hook("$bb_lint", "1", "FAILED"),
    ]
    cs = _make_changespec(hooks=hooks, commits=[_make_commit(1)])
    logged: list[str] = []

    with (
        patch(_PATCH_PARSE, return_value=[cs]),
        patch(_PATCH_KILL, return_value=3),
        patch(_PATCH_RERUN, return_value=True),
    ):
        reset_dollar_hooks("/tmp/test.gp", "test_feature", log_fn=logged.append)

    assert len(logged) == 2
    assert "2 $-prefixed hook(s)" in logged[0]
    assert "3 running process(es)" in logged[1]


def test_log_fn_no_kill_message_when_zero_killed() -> None:
    """log_fn should not receive kill message when nothing was killed."""
    hooks = [_make_hook("$bb_presubmit", "1", "PASSED")]
    cs = _make_changespec(hooks=hooks, commits=[_make_commit(1)])
    logged: list[str] = []

    with (
        patch(_PATCH_PARSE, return_value=[cs]),
        patch(_PATCH_KILL, return_value=0),
        patch(_PATCH_RERUN, return_value=True),
    ):
        reset_dollar_hooks("/tmp/test.gp", "test_feature", log_fn=logged.append)

    assert len(logged) == 1
    assert "Resetting" in logged[0]


def test_mix_dollar_and_non_dollar_hooks() -> None:
    """Only $ hooks should be affected; non-$ hooks should be left alone."""
    hooks = [
        _make_hook("flake8 src", "1", "PASSED"),
        _make_hook("$bb_presubmit", "1", "PASSED"),
        _make_hook("pytest tests", "1", "FAILED"),
        _make_hook("$bb_lint", "1", "PASSED"),
    ]
    cs = _make_changespec(hooks=hooks, commits=[_make_commit(1)])

    with (
        patch(_PATCH_PARSE, return_value=[cs]),
        patch(_PATCH_KILL, return_value=0) as mock_kill,
        patch(_PATCH_RERUN, return_value=True) as mock_rerun,
    ):
        reset_dollar_hooks("/tmp/test.gp", "test_feature")

    # Only indices 1 and 3 are $ hooks
    mock_kill.assert_called_once_with(hooks, {1, 3})
    # Only $ commands should be rerun
    mock_rerun.assert_called_once()
    assert mock_rerun.call_args[1]["commands_to_rerun"] == {
        "$bb_presubmit",
        "$bb_lint",
    }


def test_changespec_not_found_returns_true() -> None:
    """If the changespec name doesn't match, return True (no-op)."""
    cs = _make_changespec(
        name="other_feature",
        hooks=[_make_hook("$bb_presubmit", "1")],
        commits=[_make_commit(1)],
    )
    with patch(_PATCH_PARSE, return_value=[cs]):
        assert reset_dollar_hooks("/tmp/test.gp", "test_feature") is True
