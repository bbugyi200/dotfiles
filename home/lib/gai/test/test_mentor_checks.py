"""Tests for the mentor_checks module."""

from typing import Any

from ace.changespec import ChangeSpec, CommitEntry, HookEntry, HookStatusLine
from ace.loop.mentor_checks import (
    _all_non_skip_hooks_passed,
    _extract_changed_files_from_diff,
    _get_commit_entry_diff_path,
    _get_commit_entry_note,
    _get_latest_real_commit_id,
)


def _make_changespec(**kwargs: Any) -> ChangeSpec:
    """Helper to create a ChangeSpec with defaults."""
    defaults = {
        "name": "test-cl",
        "description": "Test description",
        "parent": None,
        "cl": None,
        "status": "Drafted",
        "test_targets": None,
        "kickstart": None,
        "file_path": "/tmp/test.md",
        "line_number": 1,
        "commits": None,
        "hooks": None,
        "comments": None,
        "mentors": None,
    }
    defaults.update(kwargs)
    return ChangeSpec(**defaults)  # type: ignore[arg-type]


def test_get_latest_real_commit_id_empty() -> None:
    """Test with no commits."""
    cs = _make_changespec(commits=None)
    assert _get_latest_real_commit_id(cs) is None


def test_get_latest_real_commit_id_single() -> None:
    """Test with a single commit."""
    cs = _make_changespec(commits=[CommitEntry(number=1, note="First commit")])
    assert _get_latest_real_commit_id(cs) == "1"


def test_get_latest_real_commit_id_multiple() -> None:
    """Test with multiple commits, returns highest."""
    cs = _make_changespec(
        commits=[
            CommitEntry(number=1, note="First"),
            CommitEntry(number=2, note="Second"),
            CommitEntry(number=3, note="Third"),
        ]
    )
    assert _get_latest_real_commit_id(cs) == "3"


def test_get_latest_real_commit_id_ignores_proposals() -> None:
    """Test that proposal entries (1a, 2b) are ignored."""
    cs = _make_changespec(
        commits=[
            CommitEntry(number=1, note="First"),
            CommitEntry(number=1, proposal_letter="a", note="Proposal 1"),
            CommitEntry(number=2, note="Second"),
            CommitEntry(number=2, proposal_letter="a", note="Proposal 2"),
        ]
    )
    # Should return "2", not "2a"
    assert _get_latest_real_commit_id(cs) == "2"


def test_all_non_skip_hooks_passed_no_hooks() -> None:
    """Test with no hooks returns True."""
    cs = _make_changespec(hooks=None)
    assert _all_non_skip_hooks_passed(cs, "1") is True


def test_all_non_skip_hooks_passed_with_passed_hook() -> None:
    """Test with a passed hook returns True."""
    cs = _make_changespec(
        hooks=[
            HookEntry(
                command="make test",  # No prefix = skip_fix_hook is False
                status_lines=[
                    HookStatusLine(
                        commit_entry_num="1",
                        timestamp="240101_120000",
                        status="PASSED",
                        duration="1m0s",
                    )
                ],
            )
        ]
    )
    assert _all_non_skip_hooks_passed(cs, "1") is True


def test_all_non_skip_hooks_passed_with_failed_hook() -> None:
    """Test with a failed hook returns False."""
    cs = _make_changespec(
        hooks=[
            HookEntry(
                command="make test",  # No prefix = skip_fix_hook is False
                status_lines=[
                    HookStatusLine(
                        commit_entry_num="1",
                        timestamp="240101_120000",
                        status="FAILED",
                        duration="1m0s",
                    )
                ],
            )
        ]
    )
    assert _all_non_skip_hooks_passed(cs, "1") is False


def test_all_non_skip_hooks_passed_with_skip_hook() -> None:
    """Test that skip hooks (with ! prefix) are ignored."""
    cs = _make_changespec(
        hooks=[
            HookEntry(
                command="!make test",  # ! prefix = skip_fix_hook is True
                status_lines=[
                    HookStatusLine(
                        commit_entry_num="1",
                        timestamp="240101_120000",
                        status="FAILED",
                        duration="1m0s",
                    )
                ],
            )
        ]
    )
    # Even though the hook failed, it's a skip hook so should return True
    assert _all_non_skip_hooks_passed(cs, "1") is True


def test_all_non_skip_hooks_passed_no_status_for_entry() -> None:
    """Test when hook has no status for the requested entry."""
    cs = _make_changespec(
        hooks=[
            HookEntry(
                command="make test",  # No prefix = skip_fix_hook is False
                status_lines=[
                    HookStatusLine(
                        commit_entry_num="1",
                        timestamp="240101_120000",
                        status="PASSED",
                        duration="1m0s",
                    )
                ],
            )
        ]
    )
    # Asking for entry "2" which has no status
    assert _all_non_skip_hooks_passed(cs, "2") is False


def test_get_commit_entry_diff_path_found() -> None:
    """Test getting diff path for existing entry."""
    cs = _make_changespec(
        commits=[CommitEntry(number=1, note="First", diff="~/gai/diffs/test.diff")]
    )
    assert _get_commit_entry_diff_path(cs, "1") == "~/gai/diffs/test.diff"


def test_get_commit_entry_diff_path_not_found() -> None:
    """Test getting diff path for non-existent entry."""
    cs = _make_changespec(commits=[CommitEntry(number=1, note="First")])
    assert _get_commit_entry_diff_path(cs, "2") is None


def test_get_commit_entry_note_found() -> None:
    """Test getting note for existing entry."""
    cs = _make_changespec(commits=[CommitEntry(number=1, note="Refactor the module")])
    assert _get_commit_entry_note(cs, "1") == "Refactor the module"


def test_get_commit_entry_note_not_found() -> None:
    """Test getting note for non-existent entry."""
    cs = _make_changespec(commits=None)
    assert _get_commit_entry_note(cs, "1") is None


def test_extract_changed_files_from_diff_git_format() -> None:
    """Test extracting files from git diff format."""
    diff_content = """diff --git a/src/main.py b/src/main.py
index 123456..789abc 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,4 @@
 def main():
     pass
+    return 0
diff --git a/tests/test_main.py b/tests/test_main.py
index aaaaaa..bbbbbb 100644
--- a/tests/test_main.py
+++ b/tests/test_main.py
@@ -1 +1,2 @@
 def test_main(): pass
+def test_other(): pass
"""
    files = _extract_changed_files_from_diff(diff_content)
    assert files == ["src/main.py", "tests/test_main.py"]


def test_extract_changed_files_from_diff_hg_format() -> None:
    """Test extracting files from hg diff format."""
    diff_content = """diff -r abc123 src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,4 @@
 def main():
     pass
+    return 0
diff -r abc123 tests/test_main.py
--- a/tests/test_main.py
+++ b/tests/test_main.py
@@ -1 +1,2 @@
 def test_main(): pass
"""
    files = _extract_changed_files_from_diff(diff_content)
    assert files == ["src/main.py", "tests/test_main.py"]


def test_extract_changed_files_from_diff_empty() -> None:
    """Test with empty diff content."""
    files = _extract_changed_files_from_diff("")
    assert files == []


def test_extract_changed_files_from_diff_no_file_lines() -> None:
    """Test with diff content that has no file lines."""
    diff_content = """Some random content
that is not a diff
"""
    files = _extract_changed_files_from_diff(diff_content)
    assert files == []


def test_get_latest_real_commit_id_only_proposals() -> None:
    """Test with only proposal commits (should return None)."""
    cs = _make_changespec(
        commits=[
            CommitEntry(number=1, proposal_letter="a", note="Proposal 1"),
            CommitEntry(number=1, proposal_letter="b", note="Proposal 2"),
        ]
    )
    # No all-numeric entries, should return None
    assert _get_latest_real_commit_id(cs) is None
