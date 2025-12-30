"""Tests for the workflows_runner module."""

import os
import tempfile

from ace.changespec import (
    ChangeSpec,
    CommentEntry,
    CommitEntry,
    HookEntry,
    HookStatusLine,
)
from ace.loop.workflows_runner.monitor import (
    WORKFLOW_COMPLETE_MARKER,
    check_workflow_completion,
    get_running_crs_workflows,
    get_running_fix_hook_workflows,
)
from ace.loop.workflows_runner.starter import (
    _crs_workflow_eligible,
    _fix_hook_workflow_eligible,
    get_project_basename,
    get_workflow_output_path,
)
from gai_utils import get_gai_directory


def _make_changespec(
    name: str = "test_cl",
    file_path: str = "/path/to/test.gp",
    hooks: list[HookEntry] | None = None,
    comments: list[CommentEntry] | None = None,
    commits: list[CommitEntry] | None = None,
) -> ChangeSpec:
    """Create a test ChangeSpec with minimal required fields."""
    return ChangeSpec(
        name=name,
        file_path=file_path,
        description="test description",
        cl=None,
        parent=None,
        hooks=hooks,
        commits=commits,
        status="Drafted",
        test_targets=None,
        comments=comments,
        kickstart=None,
        line_number=1,
    )


def test_get_workflows_directory() -> None:
    """Test that get_gai_directory('workflows') returns correct path."""
    result = get_gai_directory("workflows")
    assert result == os.path.expanduser("~/.gai/workflows")


def testget_workflow_output_path() -> None:
    """Test get_workflow_output_path creates valid paths."""
    result = get_workflow_output_path("test_name", "crs", "251227_123456")
    assert "test_name_crs-251227_123456.txt" in result
    assert result.startswith(os.path.expanduser("~/.gai/workflows"))


def testget_workflow_output_path_sanitizes_name() -> None:
    """Test that special characters in name are replaced with underscores."""
    result = get_workflow_output_path(
        "test-name/with.special", "fix-hook", "251227_123456"
    )
    # Special chars should be replaced with underscores
    assert "test_name_with_special_fix-hook-251227_123456.txt" in result


def testget_project_basename() -> None:
    """Test extracting project basename from changespec file path."""
    cs = _make_changespec(file_path="/path/to/myproject.gp")
    assert get_project_basename(cs) == "myproject"


def test_crs_workflow_eligible_with_reviewer_no_suffix() -> None:
    """Test CRS eligible when critique comment has no suffix."""
    comment = CommentEntry(
        reviewer="critique", file_path="~/.gai/comments/test.json", suffix=None
    )
    cs = _make_changespec(comments=[comment])
    result = _crs_workflow_eligible(cs)
    assert len(result) == 1
    assert result[0].reviewer == "critique"


def test_crs_workflow_eligible_with_author_no_suffix() -> None:
    """Test CRS eligible when critique:me comment has no suffix."""
    comment = CommentEntry(
        reviewer="critique:me", file_path="~/.gai/comments/test.json", suffix=None
    )
    cs = _make_changespec(comments=[comment])
    result = _crs_workflow_eligible(cs)
    assert len(result) == 1
    assert result[0].reviewer == "critique:me"


def test_crs_workflow_eligible_with_suffix_not_eligible() -> None:
    """Test CRS not eligible when comment has suffix (already processed)."""
    comment = CommentEntry(
        reviewer="reviewer",
        file_path="~/.gai/comments/test.json",
        suffix="251227123456",
    )
    cs = _make_changespec(comments=[comment])
    result = _crs_workflow_eligible(cs)
    assert len(result) == 0


def test_crs_workflow_eligible_no_comments() -> None:
    """Test CRS not eligible when no comments."""
    cs = _make_changespec(comments=None)
    result = _crs_workflow_eligible(cs)
    assert len(result) == 0


def test_fix_hook_workflow_eligible_with_failed_no_suffix() -> None:
    """Test fix-hook eligible when hook FAILED and no suffix."""
    status_line = HookStatusLine(
        commit_entry_num="1",
        timestamp="251227123456",
        status="FAILED",
        duration="5s",
        suffix=None,
    )
    hook = HookEntry(command="make test", status_lines=[status_line])
    commits = [CommitEntry(number=1, note="Initial commit")]
    cs = _make_changespec(hooks=[hook], commits=commits)
    result = _fix_hook_workflow_eligible(cs)
    assert len(result) == 1
    hook_entry, entry_id = result[0]
    assert hook_entry.command == "make test"
    assert entry_id == "1"


def test_fix_hook_workflow_eligible_with_suffix_not_eligible() -> None:
    """Test fix-hook not eligible when hook has suffix (already processed)."""
    status_line = HookStatusLine(
        commit_entry_num="1",
        timestamp="251227123456",
        status="FAILED",
        duration="5s",
        suffix="!",
    )
    hook = HookEntry(command="make test", status_lines=[status_line])
    cs = _make_changespec(hooks=[hook])
    result = _fix_hook_workflow_eligible(cs)
    assert len(result) == 0


def test_fix_hook_workflow_eligible_passed_not_eligible() -> None:
    """Test fix-hook not eligible when hook PASSED."""
    status_line = HookStatusLine(
        commit_entry_num="1",
        timestamp="251227123456",
        status="PASSED",
        duration="5s",
        suffix=None,
    )
    hook = HookEntry(command="make test", status_lines=[status_line])
    cs = _make_changespec(hooks=[hook])
    result = _fix_hook_workflow_eligible(cs)
    assert len(result) == 0


def test_fix_hook_workflow_eligible_no_hooks() -> None:
    """Test fix-hook not eligible when no hooks."""
    cs = _make_changespec(hooks=None)
    result = _fix_hook_workflow_eligible(cs)
    assert len(result) == 0


def testcheck_workflow_completion_file_not_exists() -> None:
    """Test completion check when file doesn't exist."""
    result = check_workflow_completion("/nonexistent/path.txt")
    assert result == (False, None, None)


def testcheck_workflow_completion_no_marker() -> None:
    """Test completion check when marker not present."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Some output without completion marker")
        temp_path = f.name

    try:
        result = check_workflow_completion(temp_path)
        assert result == (False, None, None)
    finally:
        os.unlink(temp_path)


def testcheck_workflow_completion_with_marker_success() -> None:
    """Test completion check when marker present with success."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Some output\n")
        f.write(f"{WORKFLOW_COMPLETE_MARKER}2a EXIT_CODE: 0")
        temp_path = f.name

    try:
        completed, proposal_id, exit_code = check_workflow_completion(temp_path)
        assert completed is True
        assert proposal_id == "2a"
        assert exit_code == 0
    finally:
        os.unlink(temp_path)


def testcheck_workflow_completion_with_marker_failure() -> None:
    """Test completion check when marker present with failure."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Some output\n")
        f.write(f"{WORKFLOW_COMPLETE_MARKER}None EXIT_CODE: 1")
        temp_path = f.name

    try:
        completed, proposal_id, exit_code = check_workflow_completion(temp_path)
        assert completed is True
        assert proposal_id is None
        assert exit_code == 1
    finally:
        os.unlink(temp_path)


def testget_running_crs_workflows_with_timestamp_suffix() -> None:
    """Test detecting running CRS workflows by timestamp suffix."""
    comment = CommentEntry(
        reviewer="critique",
        file_path="~/.gai/comments/test.json",
        suffix="251227_123456",
    )
    cs = _make_changespec(comments=[comment])
    result = get_running_crs_workflows(cs)
    assert len(result) == 1
    assert result[0] == ("critique", "251227_123456")


def testget_running_crs_workflows_with_non_timestamp_suffix() -> None:
    """Test that non-timestamp suffixes are not considered running."""
    comment = CommentEntry(
        reviewer="reviewer",
        file_path="~/.gai/comments/test.json",
        suffix="!",  # Not a timestamp
    )
    cs = _make_changespec(comments=[comment])
    result = get_running_crs_workflows(cs)
    assert len(result) == 0


def testget_running_crs_workflows_no_comments() -> None:
    """Test running CRS workflows when no comments."""
    cs = _make_changespec(comments=None)
    result = get_running_crs_workflows(cs)
    assert len(result) == 0


def testget_running_fix_hook_workflows_with_timestamp_suffix() -> None:
    """Test detecting running fix-hook workflows by timestamp suffix."""
    status_line = HookStatusLine(
        commit_entry_num="1",
        timestamp="251227_100000",
        status="FAILED",
        duration="5s",
        suffix="251227_123456",  # This is a timestamp suffix
    )
    hook = HookEntry(command="make test", status_lines=[status_line])
    cs = _make_changespec(hooks=[hook])
    result = get_running_fix_hook_workflows(cs)
    assert len(result) == 1
    assert result[0] == ("make test", "251227_123456")


def testget_running_fix_hook_workflows_with_non_timestamp_suffix() -> None:
    """Test that non-timestamp suffixes are not considered running."""
    status_line = HookStatusLine(
        commit_entry_num="1",
        timestamp="251227100000",
        status="FAILED",
        duration="5s",
        suffix="2a",  # This is a proposal ID, not a timestamp
    )
    hook = HookEntry(command="make test", status_lines=[status_line])
    cs = _make_changespec(hooks=[hook])
    result = get_running_fix_hook_workflows(cs)
    assert len(result) == 0


def testget_running_fix_hook_workflows_no_hooks() -> None:
    """Test running fix-hook workflows when no hooks."""
    cs = _make_changespec(hooks=None)
    result = get_running_fix_hook_workflows(cs)
    assert len(result) == 0


def testcheck_workflow_completion_with_parsing_error() -> None:
    """Test completion check when exit code is not a number."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Some output\n")
        # EXIT_CODE value is not a number - should trigger ValueError
        f.write(f"{WORKFLOW_COMPLETE_MARKER}None EXIT_CODE: notanumber")
        temp_path = f.name

    try:
        completed, proposal_id, exit_code = check_workflow_completion(temp_path)
        # Should still mark as completed but with error values
        assert completed is True
        assert proposal_id is None
        assert exit_code == 1
    finally:
        os.unlink(temp_path)


def test_crs_workflow_eligible_other_reviewer_not_eligible() -> None:
    """Test CRS not eligible when reviewer is neither 'reviewer' nor 'author'."""
    comment = CommentEntry(
        reviewer="other",
        file_path="~/.gai/comments/test.json",
        suffix=None,
    )
    cs = _make_changespec(comments=[comment])
    result = _crs_workflow_eligible(cs)
    assert len(result) == 0


def test_crs_workflow_eligible_multiple_comments_mixed() -> None:
    """Test CRS returns only eligible comments when mixed."""
    comments = [
        CommentEntry(
            reviewer="critique",
            file_path="~/.gai/comments/test1.json",
            suffix=None,  # Eligible
        ),
        CommentEntry(
            reviewer="critique:me",
            file_path="~/.gai/comments/test2.json",
            suffix="251227123456",  # Not eligible - has suffix
        ),
        CommentEntry(
            reviewer="other",
            file_path="~/.gai/comments/test3.json",
            suffix=None,  # Not eligible - wrong reviewer
        ),
    ]
    cs = _make_changespec(comments=comments)
    result = _crs_workflow_eligible(cs)
    assert len(result) == 1
    assert result[0].reviewer == "critique"


def testget_running_crs_workflows_with_author_timestamp() -> None:
    """Test detecting running critique:me CRS workflows."""
    comment = CommentEntry(
        reviewer="critique:me",
        file_path="~/.gai/comments/test.json",
        suffix="251227_123456",
    )
    cs = _make_changespec(comments=[comment])
    result = get_running_crs_workflows(cs)
    assert len(result) == 1
    assert result[0] == ("critique:me", "251227_123456")


def testget_running_crs_workflows_other_reviewer_ignored() -> None:
    """Test that other reviewer types are not considered running."""
    comment = CommentEntry(
        reviewer="other",
        file_path="~/.gai/comments/test.json",
        suffix="251227123456",  # Has timestamp but wrong reviewer
    )
    cs = _make_changespec(comments=[comment])
    result = get_running_crs_workflows(cs)
    assert len(result) == 0


def test_fix_hook_workflow_multiple_hooks_one_eligible() -> None:
    """Test that only eligible hooks are returned."""
    status_line_passed = HookStatusLine(
        commit_entry_num="1",
        timestamp="251227100000",
        status="PASSED",
        duration="5s",
        suffix=None,
    )
    status_line_failed_with_suffix = HookStatusLine(
        commit_entry_num="2",
        timestamp="251227110000",
        status="FAILED",
        duration="10s",
        suffix="!",  # Already processed
    )
    status_line_failed_no_suffix = HookStatusLine(
        commit_entry_num="3",
        timestamp="251227120000",
        status="FAILED",
        duration="15s",
        suffix=None,  # Eligible
    )
    hooks = [
        HookEntry(command="make build", status_lines=[status_line_passed]),
        HookEntry(command="make lint", status_lines=[status_line_failed_with_suffix]),
        HookEntry(command="make test", status_lines=[status_line_failed_no_suffix]),
    ]
    # Add commits with "3" as the latest all-numeric entry
    commits = [
        CommitEntry(number=1, note="First"),
        CommitEntry(number=2, note="Second"),
        CommitEntry(number=3, note="Third"),
    ]
    cs = _make_changespec(hooks=hooks, commits=commits)
    result = _fix_hook_workflow_eligible(cs)
    assert len(result) == 1
    hook_entry, entry_id = result[0]
    assert hook_entry.command == "make test"
    assert entry_id == "3"


def testget_running_fix_hook_workflows_no_status_line() -> None:
    """Test running fix-hook workflows when hook has no status lines."""
    hook = HookEntry(command="make test", status_lines=[])
    cs = _make_changespec(hooks=[hook])
    result = get_running_fix_hook_workflows(cs)
    assert len(result) == 0


def testget_project_basename_complex_path() -> None:
    """Test extracting project basename from complex path."""
    cs = _make_changespec(file_path="/home/user/.gai/projects/my-project.gp")
    assert get_project_basename(cs) == "my-project"


def testget_workflow_output_path_different_types() -> None:
    """Test output paths for different workflow types."""
    crs_path = get_workflow_output_path("test", "crs", "251227123456")
    fix_path = get_workflow_output_path("test", "fix-hook", "251227123456")
    assert "crs" in crs_path
    assert "fix-hook" in fix_path
    assert crs_path != fix_path
