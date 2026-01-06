"""Tests for the mentor_checks module."""

from typing import Any

from ace.changespec import ChangeSpec, CommitEntry, MentorEntry, MentorStatusLine
from ace.loop.mentor_checks import (
    _extract_changed_files_from_diff,
    _get_commit_entry_diff_path,
    _get_commit_entry_note,
    _get_started_mentors_for_entry,
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


def test_get_started_mentors_no_mentors() -> None:
    """Test with no MENTORS entries returns empty set."""
    cs = _make_changespec(mentors=None)
    assert _get_started_mentors_for_entry(cs, "1") == set()


def test_get_started_mentors_empty_mentors() -> None:
    """Test with empty MENTORS list returns empty set."""
    cs = _make_changespec(mentors=[])
    assert _get_started_mentors_for_entry(cs, "1") == set()


def test_get_started_mentors_no_status_lines() -> None:
    """Test with MENTORS entry but no status lines returns empty set."""
    cs = _make_changespec(
        mentors=[MentorEntry(entry_id="1", profiles=["code"], status_lines=None)]
    )
    assert _get_started_mentors_for_entry(cs, "1") == set()


def test_get_started_mentors_different_entry_id() -> None:
    """Test that only mentors for the specified entry_id are returned."""
    cs = _make_changespec(
        mentors=[
            MentorEntry(
                entry_id="1",
                profiles=["code"],
                status_lines=[
                    MentorStatusLine(
                        profile_name="code", mentor_name="dead_code", status="PASSED"
                    )
                ],
            )
        ]
    )
    # Asking for entry_id "2" should return empty set
    assert _get_started_mentors_for_entry(cs, "2") == set()


def test_get_started_mentors_single() -> None:
    """Test with a single started mentor."""
    cs = _make_changespec(
        mentors=[
            MentorEntry(
                entry_id="1",
                profiles=["code"],
                status_lines=[
                    MentorStatusLine(
                        profile_name="code", mentor_name="dead_code", status="RUNNING"
                    )
                ],
            )
        ]
    )
    assert _get_started_mentors_for_entry(cs, "1") == {("code", "dead_code")}


def test_get_started_mentors_multiple() -> None:
    """Test with multiple started mentors from same profile."""
    cs = _make_changespec(
        mentors=[
            MentorEntry(
                entry_id="1",
                profiles=["code"],
                status_lines=[
                    MentorStatusLine(
                        profile_name="code", mentor_name="dead_code", status="PASSED"
                    ),
                    MentorStatusLine(
                        profile_name="code", mentor_name="shared_code", status="RUNNING"
                    ),
                ],
            )
        ]
    )
    assert _get_started_mentors_for_entry(cs, "1") == {
        ("code", "dead_code"),
        ("code", "shared_code"),
    }


def test_get_started_mentors_multiple_profiles() -> None:
    """Test with mentors from different profiles."""
    cs = _make_changespec(
        mentors=[
            MentorEntry(
                entry_id="1",
                profiles=["code", "tests"],
                status_lines=[
                    MentorStatusLine(
                        profile_name="code", mentor_name="dead_code", status="PASSED"
                    ),
                    MentorStatusLine(
                        profile_name="tests", mentor_name="coverage", status="RUNNING"
                    ),
                ],
            )
        ]
    )
    assert _get_started_mentors_for_entry(cs, "1") == {
        ("code", "dead_code"),
        ("tests", "coverage"),
    }
