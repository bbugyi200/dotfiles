"""Tests for renumber_commit_entries function in accept_workflow module."""

import os
import tempfile

from accept_workflow import renumber_commit_entries
from accept_workflow.renumber import _clear_last_mentor_wip_flag


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
        result = renumber_commit_entries(temp_path, "test_cl", [(2, "a")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # (2a) became (3)
        assert "(3) First proposal" in content
        # (2b) stays as (2b) - unchanged
        assert "(2b) Second proposal" in content
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
        result = renumber_commit_entries(temp_path, "test_cl", [(1, "a"), (1, "c")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # (1) unchanged
        assert "(1) First commit" in content
        # (1a) became (2) - first accepted
        assert "(2) Proposal A" in content
        # (1c) became (3) - second accepted
        assert "(3) Proposal C" in content
        # (1b) stays as (1b) - unchanged
        assert "(1b) Proposal B" in content
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
        result = renumber_commit_entries(temp_path, "test_cl", [(1, "a")])
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
    result = renumber_commit_entries("/nonexistent/file.gp", "test_cl", [(1, "a")])
    assert result is False


def test_renumber_commit_entries_no_history_section() -> None:
    """Test renumbering when no COMMITS section exists."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        temp_path = f.name

    try:
        result = renumber_commit_entries(temp_path, "test_cl", [(1, "a")])
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
        result = renumber_commit_entries(temp_path, "test_cl", [(1, "a")])
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
        result = renumber_commit_entries(
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
        result = renumber_commit_entries(
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
        # (1b) stays as (1b) - unchanged, no message
        assert "(1b) Proposal B" in content
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
        result = renumber_commit_entries(
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
        f.write("      | (1) [251224_120000] PASSED (1m23s)\n")
        f.write("      | (2) [251224_120100] PASSED (2m45s)\n")
        f.write("      | (2a) [251224_120200] PASSED (30s)\n")
        f.write("      | (2b) [251224_120300] RUNNING\n")
        temp_path = f.name

    try:
        result = renumber_commit_entries(temp_path, "test_cl", [(2, "a")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # History entries renumbered
        assert "(3) First proposal" in content
        assert "(2b) Second proposal" in content

        # Hook status lines should be updated
        # (1) unchanged
        assert "(1) [251224_120000] PASSED (1m23s)" in content
        # (2) unchanged
        assert "(2) [251224_120100] PASSED (2m45s)" in content
        # (2a) became (3)
        assert "(3) [251224_120200] PASSED (30s)" in content
        # (2b) stays as (2b) - unchanged
        assert "(2b) [251224_120300] RUNNING" in content
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
        f.write("      | (1b) [251224_120200] RUNNING\n")
        f.write("      | (1) [251224_120000] PASSED (1m23s)\n")
        f.write("      | (1a) [251224_120100] PASSED (30s)\n")
        temp_path = f.name

    try:
        # Accept 1a, so 1b becomes 2a
        result = renumber_commit_entries(temp_path, "test_cl", [(1, "a")])
        assert result is True

        with open(temp_path) as f:
            lines = f.readlines()

        # Find the hook status lines
        status_lines = [line for line in lines if line.strip().startswith("(")]

        # Should be sorted: (1), (1b), (2)
        # (1a) was accepted and became (2), (1b) stays as (1b)
        assert "(1)" in status_lines[0]
        assert "(1b)" in status_lines[1]
        assert "(2)" in status_lines[2]
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
        f.write("      | (1) [251224_120000] PASSED (1m23s)\n")
        f.write("      | (1a) [251224_120100] FAILED (30s) - (!)\n")
        temp_path = f.name

    try:
        result = renumber_commit_entries(temp_path, "test_cl", [(1, "a")])
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
        f.write("      | (1) [251224_120000] PASSED (1m23s)\n")
        f.write("      | (1a) [251224_120100] PASSED (30s)\n")
        f.write("  make test\n")
        f.write("      | (1) [251224_120000] PASSED (5m0s)\n")
        f.write("      | (1a) [251224_120100] FAILED (2m30s)\n")
        temp_path = f.name

    try:
        result = renumber_commit_entries(temp_path, "test_cl", [(1, "a")])
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
        f.write("      | (1) [251224_120000] PASSED (1m)\n")
        f.write("      | (1a) [251224_120100] PASSED (30s)\n")
        f.write("      | (1b) [251224_120200] RUNNING\n")
        f.write("      | (1c) [251224_120300] PASSED (45s)\n")
        temp_path = f.name

    try:
        # Accept c and a (in that order)
        result = renumber_commit_entries(temp_path, "test_cl", [(1, "c"), (1, "a")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # COMMITS entries renumbered
        assert "(2) Proposal C" in content  # 1c -> 2 (first accepted)
        assert "(3) Proposal A" in content  # 1a -> 3 (second accepted)
        assert "(1b) Proposal B" in content  # 1b stays as 1b (unchanged)

        # HOOKS status lines:
        # (1) unchanged
        assert "(1) [251224_120000] PASSED (1m)" in content
        # (1c) promoted to (2) - first accepted
        assert "(2) [251224_120300] PASSED (45s)" in content
        # (1a) archived to (1a-3) - second accepted
        assert "(1a-3) [251224_120100] PASSED (30s)" in content
        # (1b) stays as (1b) - unchanged
        assert "(1b) [251224_120200] RUNNING" in content
        # No (3) hook status line should exist - ensures loop runs hooks for entry 3
        # Hook status lines are "      | " prefixed
        lines = content.split("\n")
        lines_with_3 = [ln for ln in lines if ln.startswith("      | (3) ")]
        assert not lines_with_3, f"Unexpected (3) status: {lines_with_3}"
    finally:
        os.unlink(temp_path)


def test_clear_last_mentor_wip_flag_multiple_wip() -> None:
    """Test that only the highest entry_id WIP entry has #WIP cleared."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: WIP\n",
        "COMMITS:\n",
        "  (1) First commit\n",
        "  (2) Second commit\n",
        "  (3) Third commit\n",
        "MENTORS:\n",
        "  (1) profile[0/2] #WIP\n",
        "  (2) profile[0/2] #WIP\n",
        "  (3) profile[0/2] #WIP\n",
    ]

    result = _clear_last_mentor_wip_flag(lines, "test_cl")

    # Only entry (3) should have #WIP cleared
    assert "  (1) profile[0/2] #WIP\n" in result
    assert "  (2) profile[0/2] #WIP\n" in result
    assert "  (3) profile[0/2]\n" in result


def test_clear_last_mentor_wip_flag_single_wip() -> None:
    """Test that a single WIP entry has #WIP cleared."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: WIP\n",
        "COMMITS:\n",
        "  (1) First commit\n",
        "MENTORS:\n",
        "  (1) profile[0/2] #WIP\n",
    ]

    result = _clear_last_mentor_wip_flag(lines, "test_cl")

    assert "  (1) profile[0/2]\n" in result
    assert "#WIP" not in "".join(result)


def test_clear_last_mentor_wip_flag_no_wip() -> None:
    """Test that nothing changes when no WIP entries exist."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (1) First commit\n",
        "MENTORS:\n",
        "  (1) profile[2/2]\n",
    ]

    result = _clear_last_mentor_wip_flag(lines, "test_cl")

    # Lines should be unchanged
    assert result == lines


def test_clear_last_mentor_wip_flag_mixed_entries() -> None:
    """Test with a mix of WIP and non-WIP entries."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: WIP\n",
        "COMMITS:\n",
        "  (1) First commit\n",
        "  (2) Second commit\n",
        "  (3) Third commit\n",
        "MENTORS:\n",
        "  (1) profile[2/2]\n",  # Not WIP
        "  (2) profile[0/2] #WIP\n",  # WIP - should remain
        "  (3) profile[0/2] #WIP\n",  # WIP - highest, should be cleared
    ]

    result = _clear_last_mentor_wip_flag(lines, "test_cl")

    # Entry (1) never had #WIP
    assert "  (1) profile[2/2]\n" in result
    # Entry (2) should keep #WIP (not the highest)
    assert "  (2) profile[0/2] #WIP\n" in result
    # Entry (3) should have #WIP cleared (highest WIP entry)
    assert "  (3) profile[0/2]\n" in result


def test_clear_last_mentor_wip_flag_proposal_entries() -> None:
    """Test with proposal entries (e.g., 2a, 2b)."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: WIP\n",
        "COMMITS:\n",
        "  (1) First commit\n",
        "  (2) Second commit\n",
        "  (2a) Proposal A\n",
        "  (2b) Proposal B\n",
        "MENTORS:\n",
        "  (1) profile[0/2] #WIP\n",
        "  (2) profile[0/2] #WIP\n",
        "  (2a) profile[0/2] #WIP\n",
        "  (2b) profile[0/2] #WIP\n",
    ]

    result = _clear_last_mentor_wip_flag(lines, "test_cl")

    # Entry (2b) is the highest (2, "b") > (2, "a") > (2, "") > (1, "")
    assert "  (1) profile[0/2] #WIP\n" in result
    assert "  (2) profile[0/2] #WIP\n" in result
    assert "  (2a) profile[0/2] #WIP\n" in result
    assert "  (2b) profile[0/2]\n" in result


def test_clear_last_mentor_wip_flag_with_status_lines() -> None:
    """Test that status lines are preserved when clearing #WIP."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: WIP\n",
        "COMMITS:\n",
        "  (1) First commit\n",
        "  (2) Second commit\n",
        "MENTORS:\n",
        "  (1) profile[1/2] #WIP\n",
        "      | profile:mentor1 - PASSED - (0h2m15s)\n",
        "  (2) profile[0/2] #WIP\n",
        "      | profile:mentor1 - RUNNING - (@: mentor_complete-12345-251230_1530)\n",
    ]

    result = _clear_last_mentor_wip_flag(lines, "test_cl")

    # Entry (1) keeps #WIP
    assert "  (1) profile[1/2] #WIP\n" in result
    # Entry (2) has #WIP cleared
    assert "  (2) profile[0/2]\n" in result
    # Status lines preserved
    assert "      | profile:mentor1 - PASSED - (0h2m15s)\n" in result
    assert (
        "      | profile:mentor1 - RUNNING - (@: mentor_complete-12345-251230_1530)\n"
        in result
    )


def test_clear_last_mentor_wip_flag_wrong_changespec() -> None:
    """Test that other ChangeSpecs are not affected."""
    lines = [
        "NAME: other_cl\n",
        "STATUS: WIP\n",
        "COMMITS:\n",
        "  (1) First commit\n",
        "MENTORS:\n",
        "  (1) profile[0/2] #WIP\n",
        "\n",
        "NAME: test_cl\n",
        "STATUS: WIP\n",
        "COMMITS:\n",
        "  (1) First commit\n",
        "MENTORS:\n",
        "  (1) profile[0/2] #WIP\n",
    ]

    result = _clear_last_mentor_wip_flag(lines, "test_cl")

    # other_cl should be unchanged
    result_str = "".join(result)
    # Count #WIP occurrences - should be 1 (other_cl's entry)
    assert result_str.count("#WIP") == 1
    # test_cl's entry should have #WIP cleared
    # Find the test_cl section
    test_cl_start = result_str.find("NAME: test_cl")
    test_cl_section = result_str[test_cl_start:]
    assert "#WIP" not in test_cl_section
