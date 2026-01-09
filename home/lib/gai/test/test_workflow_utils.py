"""Tests for gai.workflow_utils module."""

from unittest.mock import MagicMock, patch

from workflow_utils import (
    _get_changed_test_targets,
    add_test_hooks_if_available,
    get_initial_hooks_for_changespec,
)


def test__get_changed_test_targets_success() -> None:
    """Test that test targets are returned when command succeeds."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "//foo:test1 //bar:test2\n"

    with patch("workflow_utils.subprocess.run", return_value=mock_result):
        result = _get_changed_test_targets()

    assert result == "//foo:test1 //bar:test2"


def test__get_changed_test_targets_empty_output() -> None:
    """Test that None is returned when command returns empty output."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""

    with patch("workflow_utils.subprocess.run", return_value=mock_result):
        result = _get_changed_test_targets()

    assert result is None


def test__get_changed_test_targets_whitespace_only() -> None:
    """Test that None is returned when command returns only whitespace."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "   \n\n  "

    with patch("workflow_utils.subprocess.run", return_value=mock_result):
        result = _get_changed_test_targets()

    assert result is None


def test__get_changed_test_targets_command_fails() -> None:
    """Test that None is returned when command fails."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "Error"

    with patch("workflow_utils.subprocess.run", return_value=mock_result):
        result = _get_changed_test_targets()

    assert result is None


def test__get_changed_test_targets_command_not_found() -> None:
    """Test that None is returned when command is not found."""
    with patch(
        "workflow_utils.subprocess.run",
        side_effect=FileNotFoundError("changed_test_targets not found"),
    ):
        result = _get_changed_test_targets()

    assert result is None


def test__get_changed_test_targets_verbose_logs_success() -> None:
    """Test that no log is printed when command succeeds with verbose=True."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "//foo:test1"

    with (
        patch("workflow_utils.subprocess.run", return_value=mock_result),
        patch("rich_utils.print_status") as mock_print_status,
    ):
        result = _get_changed_test_targets(verbose=True)

    assert result == "//foo:test1"
    mock_print_status.assert_not_called()


def test__get_changed_test_targets_verbose_logs_empty() -> None:
    """Test that log is printed when command returns empty with verbose=True."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""

    with (
        patch("workflow_utils.subprocess.run", return_value=mock_result),
        patch("rich_utils.print_status") as mock_print_status,
    ):
        result = _get_changed_test_targets(verbose=True)

    assert result is None
    mock_print_status.assert_called_once()
    call_args = mock_print_status.call_args
    assert "empty output" in call_args[0][0]


def test__get_changed_test_targets_verbose_logs_failure() -> None:
    """Test that log is printed when command fails with verbose=True."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "Error occurred"

    with (
        patch("workflow_utils.subprocess.run", return_value=mock_result),
        patch("rich_utils.print_status") as mock_print_status,
    ):
        result = _get_changed_test_targets(verbose=True)

    assert result is None
    mock_print_status.assert_called_once()
    call_args = mock_print_status.call_args
    assert "failed" in call_args[0][0]


def test_add_test_hooks_if_available_no_targets() -> None:
    """Test that function returns True when no targets are found."""
    with patch("workflow_utils._get_changed_test_targets", return_value=None):
        result = add_test_hooks_if_available("/fake/project.gp", "cl_name")

    assert result is True


def test_add_test_hooks_if_available_adds_hooks() -> None:
    """Test that function adds hooks when targets are found."""
    with (
        patch(
            "workflow_utils._get_changed_test_targets",
            return_value="//foo:test1 //bar:test2",
        ),
        patch(
            "ace.hooks.add_test_target_hooks_to_changespec", return_value=True
        ) as mock_add_hooks,
        patch("rich_utils.print_status"),
    ):
        result = add_test_hooks_if_available("/fake/project.gp", "cl_name")

    assert result is True
    # No existing_hooks passed - function reads fresh state inside lock
    mock_add_hooks.assert_called_once_with(
        "/fake/project.gp",
        "cl_name",
        ["//foo:test1", "//bar:test2"],
    )


def test_add_test_hooks_if_available_changes_directory() -> None:
    """Test that function changes to workspace_dir when provided."""
    original_dir = "/original/dir"
    workspace_dir = "/workspace/dir"

    with (
        patch("os.getcwd", return_value=original_dir),
        patch("os.chdir") as mock_chdir,
        patch("workflow_utils._get_changed_test_targets", return_value=None),
    ):
        result = add_test_hooks_if_available(
            "/fake/project.gp", "cl_name", workspace_dir=workspace_dir
        )

    assert result is True
    # Should change to workspace_dir and then back to original
    assert mock_chdir.call_count == 2
    mock_chdir.assert_any_call(workspace_dir)
    mock_chdir.assert_any_call(original_dir)


def test_add_test_hooks_if_available_restores_directory_on_error() -> None:
    """Test that function restores directory even if _get_changed_test_targets fails."""
    original_dir = "/original/dir"
    workspace_dir = "/workspace/dir"

    with (
        patch("os.getcwd", return_value=original_dir),
        patch("os.chdir") as mock_chdir,
        patch(
            "workflow_utils._get_changed_test_targets",
            side_effect=Exception("Test error"),
        ),
    ):
        try:
            add_test_hooks_if_available(
                "/fake/project.gp", "cl_name", workspace_dir=workspace_dir
            )
        except Exception:
            pass

    # Should still restore the original directory
    mock_chdir.assert_any_call(original_dir)


def test_add_test_hooks_if_available_returns_false_on_failure() -> None:
    """Test that function returns False when adding hooks fails."""
    with (
        patch("workflow_utils._get_changed_test_targets", return_value="//foo:test1"),
        patch("workflow_utils.get_changespec_from_file", return_value=None),
        patch("ace.hooks.add_test_target_hooks_to_changespec", return_value=False),
        patch("rich_utils.print_status"),
    ):
        result = add_test_hooks_if_available("/fake/project.gp", "cl_name")

    assert result is False


# Tests for get_initial_hooks_for_changespec


def test_get_initial_hooks_for_changespec_returns_required_hooks() -> None:
    """Test that required hooks are always returned."""
    with patch("workflow_utils._get_changed_test_targets", return_value=None):
        result = get_initial_hooks_for_changespec()

    assert "!$bb_hg_presubmit" in result
    assert "bb_hg_lint" in result
    assert len(result) == 2


def test_get_initial_hooks_for_changespec_includes_test_targets() -> None:
    """Test that test target hooks are appended after required hooks."""
    with patch(
        "workflow_utils._get_changed_test_targets",
        return_value="//foo:test1 //bar:test2",
    ):
        result = get_initial_hooks_for_changespec()

    assert result == [
        "!$bb_hg_presubmit",
        "bb_hg_lint",
        "bb_rabbit_test //foo:test1",
        "bb_rabbit_test //bar:test2",
    ]


def test_get_initial_hooks_for_changespec_preserves_order() -> None:
    """Test that hooks are in correct order: required first, then test targets."""
    with patch("workflow_utils._get_changed_test_targets", return_value="//foo:test1"):
        result = get_initial_hooks_for_changespec()

    # Required hooks should be first
    assert result[0] == "!$bb_hg_presubmit"
    assert result[1] == "bb_hg_lint"
    # Test targets should be last
    assert result[2] == "bb_rabbit_test //foo:test1"


def test_get_initial_hooks_for_changespec_handles_empty_test_targets() -> None:
    """Test that empty test target string is handled correctly."""
    with patch("workflow_utils._get_changed_test_targets", return_value=""):
        result = get_initial_hooks_for_changespec()

    # Should only have required hooks when test targets is empty string
    # (empty string is falsy, so test targets won't be added)
    assert len(result) == 2
    assert "!$bb_hg_presubmit" in result
    assert "bb_hg_lint" in result
