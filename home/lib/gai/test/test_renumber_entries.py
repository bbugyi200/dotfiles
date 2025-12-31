"""Tests for _renumber_commit_entries function in accept_workflow module."""

import os
import tempfile

from accept_workflow import _renumber_commit_entries


def test_renumber_commit_entries_accept_single_proposal() -> None:
    """Test renumbering after accepting a single proposal."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("      | DIFF: ~/.gai/diffs/first.diff\n")
        f.write("  (2) Second commit\n")
        f.write("      | DIFF: ~/.gai/diffs/second.diff\n")
        f.write("  (2a) First proposal\n")
        f.write("      | DIFF: ~/.gai/diffs/proposal_a.diff\n")
        f.write("  (2b) Second proposal\n")
        f.write("      | DIFF: ~/.gai/diffs/proposal_b.diff\n")
        temp_path = f.name

    try:
        result = _renumber_commit_entries(temp_path, "test_cl", [(2, "a")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # (2a) became (3)
        assert "(3) First proposal" in content
        # (2b) became (3a) - renumbered to new base
        assert "(3a) Second proposal" in content
        # Original entries unchanged
        assert "(1) First commit" in content
        assert "(2) Second commit" in content
    finally:
        os.unlink(temp_path)


def test_renumber_commit_entries_accept_multiple_proposals() -> None:
    """Test renumbering after accepting multiple proposals."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("  (1a) Proposal A\n")
        f.write("  (1b) Proposal B\n")
        f.write("  (1c) Proposal C\n")
        temp_path = f.name

    try:
        # Accept a and c, leaving b as a proposal
        result = _renumber_commit_entries(temp_path, "test_cl", [(1, "a"), (1, "c")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # (1) unchanged
        assert "(1) First commit" in content
        # (1a) became (2) - first accepted
        assert "(2) Proposal A" in content
        # (1c) became (3) - second accepted
        assert "(3) Proposal C" in content
        # (1b) became (3a) - remaining proposal renumbered
        assert "(3a) Proposal B" in content
    finally:
        os.unlink(temp_path)


def test_renumber_commit_entries_no_remaining_proposals() -> None:
    """Test renumbering when all proposals are accepted."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("  (1a) Only proposal\n")
        temp_path = f.name

    try:
        result = _renumber_commit_entries(temp_path, "test_cl", [(1, "a")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        assert "(1) First commit" in content
        assert "(2) Only proposal" in content
        # No proposal letters should remain
        assert "(2a)" not in content
    finally:
        os.unlink(temp_path)


def test_renumber_commit_entries_nonexistent_file() -> None:
    """Test renumbering with non-existent file."""
    result = _renumber_commit_entries("/nonexistent/file.gp", "test_cl", [(1, "a")])
    assert result is False


def test_renumber_commit_entries_no_history_section() -> None:
    """Test renumbering when no COMMITS section exists."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        temp_path = f.name

    try:
        result = _renumber_commit_entries(temp_path, "test_cl", [(1, "a")])
        assert result is False
    finally:
        os.unlink(temp_path)


def test_renumber_commit_entries_preserves_diffs() -> None:
    """Test that renumbering preserves DIFF paths."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("      | DIFF: ~/.gai/diffs/first.diff\n")
        f.write("  (1a) Proposal\n")
        f.write("      | CHAT: ~/.gai/chats/proposal.md\n")
        f.write("      | DIFF: ~/.gai/diffs/proposal.diff\n")
        temp_path = f.name

    try:
        result = _renumber_commit_entries(temp_path, "test_cl", [(1, "a")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # Original diffs preserved
        assert "| DIFF: ~/.gai/diffs/first.diff" in content
        # Proposal diffs preserved
        assert "| CHAT: ~/.gai/chats/proposal.md" in content
        assert "| DIFF: ~/.gai/diffs/proposal.diff" in content
    finally:
        os.unlink(temp_path)


def test_renumber_commit_entries_with_extra_msg() -> None:
    """Test that extra_msg is appended to accepted entry note."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("  (1a) Original note\n")
        temp_path = f.name

    try:
        result = _renumber_commit_entries(
            temp_path, "test_cl", [(1, "a")], extra_msgs=["fix typo"]
        )
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # Check that extra_msg was appended
        assert "(2) Original note - fix typo" in content
    finally:
        os.unlink(temp_path)


def test_renumber_commit_entries_with_per_proposal_messages() -> None:
    """Test that per-proposal messages are appended to each accepted entry."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("  (1a) Proposal A\n")
        f.write("  (1b) Proposal B\n")
        f.write("  (1c) Proposal C\n")
        temp_path = f.name

    try:
        # Accept a and c with messages, b stays as proposal
        result = _renumber_commit_entries(
            temp_path,
            "test_cl",
            [(1, "a"), (1, "c")],
            extra_msgs=["Add foobar field", "Fix the baz"],
        )
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # (1a) became (2) with message
        assert "(2) Proposal A - Add foobar field" in content
        # (1c) became (3) with message
        assert "(3) Proposal C - Fix the baz" in content
        # (1b) became (3a) - no message
        assert "(3a) Proposal B" in content
        # Make sure "Proposal B" doesn't have an extra message
        assert "Proposal B - " not in content
    finally:
        os.unlink(temp_path)


def test_renumber_commit_entries_with_mixed_none_messages() -> None:
    """Test that None messages in extra_msgs don't append anything."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("  (1a) Proposal A\n")
        f.write("  (1b) Proposal B\n")
        temp_path = f.name

    try:
        # Accept both, but only first has a message
        result = _renumber_commit_entries(
            temp_path,
            "test_cl",
            [(1, "a"), (1, "b")],
            extra_msgs=["Has message", None],
        )
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # (1a) became (2) with message
        assert "(2) Proposal A - Has message" in content
        # (1b) became (3) without message
        assert "(3) Proposal B\n" in content or "(3) Proposal B" in content
        # Make sure "Proposal B" doesn't have an extra message
        assert "Proposal B - " not in content
    finally:
        os.unlink(temp_path)


def test_renumber_commit_entries_updates_hook_status_lines() -> None:
    """Test that hook status lines are updated with new entry IDs."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("  (2) Second commit\n")
        f.write("  (2a) First proposal\n")
        f.write("  (2b) Second proposal\n")
        f.write("HOOKS:\n")
        f.write("  make lint\n")
        f.write("    (1) [251224_120000] PASSED (1m23s)\n")
        f.write("    (2) [251224_120100] PASSED (2m45s)\n")
        f.write("    (2a) [251224_120200] PASSED (30s)\n")
        f.write("    (2b) [251224_120300] RUNNING\n")
        temp_path = f.name

    try:
        result = _renumber_commit_entries(temp_path, "test_cl", [(2, "a")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # History entries renumbered
        assert "(3) First proposal" in content
        assert "(3a) Second proposal" in content

        # Hook status lines should be updated
        # (1) unchanged
        assert "(1) [251224_120000] PASSED (1m23s)" in content
        # (2) unchanged
        assert "(2) [251224_120100] PASSED (2m45s)" in content
        # (2a) became (3)
        assert "(3) [251224_120200] PASSED (30s)" in content
        # (2b) became (3a)
        assert "(3a) [251224_120300] RUNNING" in content
    finally:
        os.unlink(temp_path)


def test_renumber_commit_entries_sorts_hook_status_lines() -> None:
    """Test that hook status lines are sorted by entry ID after renumbering."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("  (1a) Proposal A\n")
        f.write("  (1b) Proposal B\n")
        f.write("HOOKS:\n")
        f.write("  make lint\n")
        # Status lines in non-sorted order
        f.write("    (1b) [251224_120200] RUNNING\n")
        f.write("    (1) [251224_120000] PASSED (1m23s)\n")
        f.write("    (1a) [251224_120100] PASSED (30s)\n")
        temp_path = f.name

    try:
        # Accept 1a, so 1b becomes 2a
        result = _renumber_commit_entries(temp_path, "test_cl", [(1, "a")])
        assert result is True

        with open(temp_path) as f:
            lines = f.readlines()

        # Find the hook status lines
        status_lines = [line for line in lines if line.strip().startswith("(")]

        # Should be sorted: (1), (2), (2a)
        assert "(1)" in status_lines[0]
        assert "(2)" in status_lines[1]
        assert "(2a)" in status_lines[2]
    finally:
        os.unlink(temp_path)


def test_renumber_commit_entries_preserves_hook_suffix() -> None:
    """Test that hook status line suffixes are preserved during renumbering."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("  (1a) Proposal\n")
        f.write("HOOKS:\n")
        f.write("  make lint\n")
        f.write("    (1) [251224_120000] PASSED (1m23s)\n")
        f.write("    (1a) [251224_120100] FAILED (30s) - (!)\n")
        temp_path = f.name

    try:
        result = _renumber_commit_entries(temp_path, "test_cl", [(1, "a")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # The suffix "- (!)" should be preserved
        assert "(2) [251224_120100] FAILED (30s) - (!)" in content
    finally:
        os.unlink(temp_path)


def test_renumber_commit_entries_multiple_hooks() -> None:
    """Test renumbering with multiple hooks."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("  (1a) Proposal\n")
        f.write("HOOKS:\n")
        f.write("  make lint\n")
        f.write("    (1) [251224_120000] PASSED (1m23s)\n")
        f.write("    (1a) [251224_120100] PASSED (30s)\n")
        f.write("  make test\n")
        f.write("    (1) [251224_120000] PASSED (5m0s)\n")
        f.write("    (1a) [251224_120100] FAILED (2m30s)\n")
        temp_path = f.name

    try:
        result = _renumber_commit_entries(temp_path, "test_cl", [(1, "a")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # Both hooks should have their status lines updated
        # make lint: (1a) -> (2)
        assert "make lint" in content
        assert "(2) [251224_120100] PASSED (30s)" in content

        # make test: (1a) -> (2)
        assert "make test" in content
        assert "(2) [251224_120100] FAILED (2m30s)" in content
    finally:
        os.unlink(temp_path)


def test_renumber_commit_entries_multi_accept_archives_hooks() -> None:
    """Test full renumbering archives hook status lines for non-first proposals."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("  (1a) Proposal A\n")
        f.write("  (1b) Proposal B\n")
        f.write("  (1c) Proposal C\n")
        f.write("HOOKS:\n")
        f.write("  make lint\n")
        f.write("    (1) [251224_120000] PASSED (1m)\n")
        f.write("    (1a) [251224_120100] PASSED (30s)\n")
        f.write("    (1b) [251224_120200] RUNNING\n")
        f.write("    (1c) [251224_120300] PASSED (45s)\n")
        temp_path = f.name

    try:
        # Accept c and a (in that order)
        result = _renumber_commit_entries(temp_path, "test_cl", [(1, "c"), (1, "a")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # COMMITS entries renumbered
        assert "(2) Proposal C" in content  # 1c -> 2 (first accepted)
        assert "(3) Proposal A" in content  # 1a -> 3 (second accepted)
        assert "(3a) Proposal B" in content  # 1b -> 3a (remaining)

        # HOOKS status lines:
        # (1) unchanged
        assert "(1) [251224_120000] PASSED (1m)" in content
        # (1c) promoted to (2) - first accepted
        assert "(2) [251224_120300] PASSED (45s)" in content
        # (1a) archived to (1a-3) - second accepted
        assert "(1a-3) [251224_120100] PASSED (30s)" in content
        # (1b) promoted to (3a) - remaining proposal
        assert "(3a) [251224_120200] RUNNING" in content
        # No (3) hook status line should exist - ensures loop runs hooks for entry 3
        # Hook status lines are 4-space indented
        lines = content.split("\n")
        lines_with_3 = [ln for ln in lines if ln.startswith("    (3) ")]
        assert not lines_with_3, f"Unexpected (3) status: {lines_with_3}"
    finally:
        os.unlink(temp_path)
