"""Tests for rewind_commit_entries function in rewind_workflow.renumber module."""

import os
import tempfile

from rewind_workflow.renumber import rewind_commit_entries


def test_rewind_to_entry_1_basic() -> None:
    """Test rewinding to entry (1) - the edge case that triggered this bug."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("      | DIFF: ~/.gai/diffs/first.diff\n")
        f.write("  (2) Second commit\n")
        f.write("      | DIFF: ~/.gai/diffs/second.diff\n")
        temp_path = f.name

    try:
        result = rewind_commit_entries(temp_path, "test_cl", 1)
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # Entry (1) stays as (1) with NEW PROPOSAL suffix
        assert "(1) First commit - (!: NEW PROPOSAL)" in content
        # Entry (2) becomes (1a) with NEW PROPOSAL suffix
        assert "(1a) Second commit - (!: NEW PROPOSAL)" in content
        # Original DIFFs preserved
        assert "| DIFF: ~/.gai/diffs/first.diff" in content
        assert "| DIFF: ~/.gai/diffs/second.diff" in content
        # No (0) entries should exist (bug was base_num = 0 when rewinding to 1)
        assert "(0" not in content
    finally:
        os.unlink(temp_path)


def test_rewind_to_middle_entry() -> None:
    """Test rewinding to a middle entry (e.g., entry 3)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("  (2) Second commit\n")
        f.write("  (3) Third commit\n")
        f.write("  (4) Fourth commit\n")
        f.write("  (5) Fifth commit\n")
        temp_path = f.name

    try:
        result = rewind_commit_entries(temp_path, "test_cl", 3)
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # Entries (1), (2) unchanged
        assert "(1) First commit\n" in content or "(1) First commit" in content
        assert "(2) Second commit\n" in content or "(2) Second commit" in content
        # Entry (3) stays as (3) with NEW PROPOSAL suffix
        assert "(3) Third commit - (!: NEW PROPOSAL)" in content
        # Entry (4) becomes (3a) with NEW PROPOSAL suffix
        assert "(3a) Fourth commit - (!: NEW PROPOSAL)" in content
        # Entries (5) deleted
        assert "(5) Fifth commit" not in content
    finally:
        os.unlink(temp_path)


def test_rewind_with_existing_proposals() -> None:
    """Test rewinding when there are existing proposals for the selected entry."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("  (2) Second commit\n")
        f.write("  (2a) Proposal A for second\n")
        f.write("  (2b) Proposal B for second\n")
        f.write("  (3) Third commit\n")
        f.write("  (4) Fourth commit\n")
        temp_path = f.name

    try:
        result = rewind_commit_entries(temp_path, "test_cl", 2)
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # Entry (1) unchanged
        assert "(1) First commit" in content
        # Entry (2) stays as (2) with NEW PROPOSAL suffix
        assert "(2) Second commit - (!: NEW PROPOSAL)" in content
        # Existing proposals (2a), (2b) unchanged
        assert "(2a) Proposal A for second" in content
        assert "(2b) Proposal B for second" in content
        # Entry (3) becomes the lowest available letter (2c) with NEW PROPOSAL suffix
        assert "(2c) Third commit - (!: NEW PROPOSAL)" in content
        # Entry (4) deleted
        assert "(4) Fourth commit" not in content
    finally:
        os.unlink(temp_path)


def test_rewind_updates_hooks() -> None:
    """Test that HOOKS section is updated with correct ID mapping."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("  (2) Second commit\n")
        f.write("  (3) Third commit\n")
        f.write("HOOKS:\n")
        f.write("  make lint\n")
        f.write("      | (1) [251224_120000] PASSED (1m)\n")
        f.write("      | (2) [251224_120100] PASSED (2m)\n")
        f.write("      | (3) [251224_120200] PASSED (3m)\n")
        temp_path = f.name

    try:
        result = rewind_commit_entries(temp_path, "test_cl", 2)
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # Hook for (1) unchanged
        assert "(1) [251224_120000] PASSED (1m)" in content
        # Hook for (2) unchanged (stays as 2)
        assert "(2) [251224_120100] PASSED (2m)" in content
        # Hook for (3) becomes (2a)
        assert "(2a) [251224_120200] PASSED (3m)" in content
    finally:
        os.unlink(temp_path)


def test_rewind_updates_mentors() -> None:
    """Test that MENTORS section is updated with correct ID mapping."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("  (2) Second commit\n")
        f.write("  (3) Third commit\n")
        f.write("MENTORS:\n")
        f.write("  (2) mentor1\n")
        f.write("      | (2) [251224_120100] PASSED\n")
        f.write("  (3) mentor2\n")
        f.write("      | (3) [251224_120200] PASSED\n")
        temp_path = f.name

    try:
        result = rewind_commit_entries(temp_path, "test_cl", 2)
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # Mentor for (2) unchanged (stays as 2)
        assert "(2) mentor1" in content
        # Mentor for (3) becomes (2a)
        assert "(2a) mentor2" in content
    finally:
        os.unlink(temp_path)


def test_rewind_deletes_entries_after_entry_after() -> None:
    """Test that entries N+2, N+3, etc. are deleted."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("  (2) Second commit\n")
        f.write("  (3) Third commit\n")
        f.write("  (4) Fourth commit\n")
        f.write("  (5) Fifth commit\n")
        f.write("  (6) Sixth commit\n")
        f.write("HOOKS:\n")
        f.write("  make lint\n")
        f.write("      | (4) [251224_120300] PASSED (4m)\n")
        f.write("      | (5) [251224_120400] PASSED (5m)\n")
        f.write("      | (6) [251224_120500] PASSED (6m)\n")
        temp_path = f.name

    try:
        result = rewind_commit_entries(temp_path, "test_cl", 3)
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # Entry (3) stays as (3) with NEW PROPOSAL suffix
        assert "(3) Third commit - (!: NEW PROPOSAL)" in content
        # Entry (4) becomes (3a) with NEW PROPOSAL suffix
        assert "(3a) Fourth commit - (!: NEW PROPOSAL)" in content
        # Entries (5), (6) deleted
        assert "(5) Fifth commit" not in content
        assert "(6) Sixth commit" not in content
        # Hook status for deleted entries should also be deleted
        assert "[251224_120400]" not in content
        assert "[251224_120500]" not in content
    finally:
        os.unlink(temp_path)


def test_rewind_preserves_chat_and_diff() -> None:
    """Test that CHAT and DIFF paths are preserved during rewind."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("      | CHAT: ~/.gai/chats/first.md\n")
        f.write("      | DIFF: ~/.gai/diffs/first.diff\n")
        f.write("  (2) Second commit\n")
        f.write("      | CHAT: ~/.gai/chats/second.md\n")
        f.write("      | DIFF: ~/.gai/diffs/second.diff\n")
        temp_path = f.name

    try:
        result = rewind_commit_entries(temp_path, "test_cl", 1)
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # Both CHAT and DIFF preserved
        assert "| CHAT: ~/.gai/chats/first.md" in content
        assert "| DIFF: ~/.gai/diffs/first.diff" in content
        assert "| CHAT: ~/.gai/chats/second.md" in content
        assert "| DIFF: ~/.gai/diffs/second.diff" in content
    finally:
        os.unlink(temp_path)


def test_rewind_strips_existing_suffix() -> None:
    """Test that existing suffixes are stripped before adding NEW PROPOSAL."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit - (~: OLD STATUS)\n")
        f.write("  (2) Second commit - (!: SOMETHING)\n")
        temp_path = f.name

    try:
        result = rewind_commit_entries(temp_path, "test_cl", 1)
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # Old suffix stripped, NEW PROPOSAL added
        assert "(1) First commit - (!: NEW PROPOSAL)" in content
        assert "(1a) Second commit - (!: NEW PROPOSAL)" in content
        # Old suffixes gone
        assert "OLD STATUS" not in content
        assert "SOMETHING" not in content
    finally:
        os.unlink(temp_path)


def test_rewind_nonexistent_file() -> None:
    """Test that rewinding a non-existent file returns False."""
    result = rewind_commit_entries("/nonexistent/file.gp", "test_cl", 1)
    assert result is False


def test_rewind_no_commits_section() -> None:
    """Test that rewinding when no COMMITS section exists returns False."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        temp_path = f.name

    try:
        result = rewind_commit_entries(temp_path, "test_cl", 1)
        assert result is False
    finally:
        os.unlink(temp_path)


def test_rewind_no_entry_after() -> None:
    """Test that rewinding fails when there's no entry after the selected one."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("  (2) Second commit\n")
        temp_path = f.name

    try:
        # Try to rewind to (2) - no entry (3) exists
        result = rewind_commit_entries(temp_path, "test_cl", 2)
        assert result is False
    finally:
        os.unlink(temp_path)
