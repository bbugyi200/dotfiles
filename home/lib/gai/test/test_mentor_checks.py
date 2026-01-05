"""Tests for the mentor_checks module."""

from typing import Any

from ace.changespec import ChangeSpec, CommitEntry, MentorEntry
from ace.loop.mentor_checks import (
    _extract_changed_files_from_diff,
    _get_commit_entry_diff_path,
    _get_commit_entry_note,
    _get_max_mentored_entry_id,
    _get_unmentored_commit_ids,
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


def test_get_max_mentored_entry_id_no_mentors() -> None:
    """Test with no MENTORS entries returns -1."""
    cs = _make_changespec(mentors=None)
    assert _get_max_mentored_entry_id(cs) == -1


def test_get_max_mentored_entry_id_empty_mentors() -> None:
    """Test with empty MENTORS list returns -1."""
    cs = _make_changespec(mentors=[])
    assert _get_max_mentored_entry_id(cs) == -1


def test_get_max_mentored_entry_id_single() -> None:
    """Test with a single MENTORS entry."""
    cs = _make_changespec(mentors=[MentorEntry(entry_id="2", profiles=["tests"])])
    assert _get_max_mentored_entry_id(cs) == 2


def test_get_max_mentored_entry_id_multiple() -> None:
    """Test with multiple MENTORS entries returns highest."""
    cs = _make_changespec(
        mentors=[
            MentorEntry(entry_id="1", profiles=["feature"]),
            MentorEntry(entry_id="3", profiles=["tests"]),
            MentorEntry(entry_id="2", profiles=["perf"]),
        ]
    )
    assert _get_max_mentored_entry_id(cs) == 3


def test_get_unmentored_commit_ids_no_commits() -> None:
    """Test with no commits returns empty list."""
    cs = _make_changespec(commits=None)
    assert _get_unmentored_commit_ids(cs) == []


def test_get_unmentored_commit_ids_no_mentors() -> None:
    """Test with commits but no mentors returns all non-proposal commit IDs."""
    cs = _make_changespec(
        commits=[
            CommitEntry(number=1, note="First"),
            CommitEntry(number=2, note="Second"),
            CommitEntry(number=2, proposal_letter="a", note="Proposal"),
        ],
        mentors=None,
    )
    # Should return "1" and "2", not "2a"
    assert _get_unmentored_commit_ids(cs) == ["1", "2"]


def test_get_unmentored_commit_ids_with_mentors() -> None:
    """Test that entries <= max mentored are excluded."""
    cs = _make_changespec(
        commits=[
            CommitEntry(number=1, note="First"),
            CommitEntry(number=2, note="Second"),
            CommitEntry(number=3, note="Third"),
            CommitEntry(number=4, note="Fourth"),
        ],
        mentors=[MentorEntry(entry_id="2", profiles=["tests"])],
    )
    # MENTORS has (2), so 1 and 2 are considered mentored
    # Only 3 and 4 should be returned
    assert _get_unmentored_commit_ids(cs) == ["3", "4"]


def test_get_unmentored_commit_ids_all_mentored() -> None:
    """Test when all commits are <= max mentored entry."""
    cs = _make_changespec(
        commits=[
            CommitEntry(number=1, note="First"),
            CommitEntry(number=2, note="Second"),
        ],
        mentors=[MentorEntry(entry_id="3", profiles=["tests"])],
    )
    # MENTORS has (3), so 1 and 2 are both <= 3, none should be returned
    assert _get_unmentored_commit_ids(cs) == []


def test_get_unmentored_commit_ids_ignores_proposals() -> None:
    """Test that proposal entries are never returned."""
    cs = _make_changespec(
        commits=[
            CommitEntry(number=1, note="First"),
            CommitEntry(number=1, proposal_letter="a", note="Proposal 1a"),
            CommitEntry(number=2, note="Second"),
            CommitEntry(number=2, proposal_letter="b", note="Proposal 2b"),
        ],
        mentors=[MentorEntry(entry_id="1", profiles=["tests"])],
    )
    # MENTORS has (1), so only "2" should be returned (not "1a" or "2b")
    assert _get_unmentored_commit_ids(cs) == ["2"]
