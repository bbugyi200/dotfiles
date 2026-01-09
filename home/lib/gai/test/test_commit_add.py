"""Tests for adding and modifying commit entries."""

import os
import tempfile
from pathlib import Path

from commit_utils import (
    add_commit_entry,
    add_proposed_commit_entry,
    get_next_commit_number,
    save_diff,
)
from commit_utils.entries import (
    _get_last_regular_commit_number,
    _get_next_proposal_letter,
)


# Tests for get_next_commit_number
def test_get_next_commit_number_no_history() -> None:
    """Test getting next history number when no history exists."""
    lines = [
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test\n",
        "STATUS: Drafted\n",
    ]
    next_num = get_next_commit_number(lines, "test_cl")
    assert next_num == 1


def test_get_next_commit_number_with_history() -> None:
    """Test getting next history number when history exists."""
    lines = [
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (1) First commit\n",
        "      | DIFF: test.diff\n",
        "  (2) Second commit\n",
        "      | DIFF: test2.diff\n",
    ]
    next_num = get_next_commit_number(lines, "test_cl")
    assert next_num == 3


def test_get_next_commit_number_wrong_changespec() -> None:
    """Test getting next history number for non-existent changespec."""
    lines = [
        "NAME: other_cl\n",
        "DESCRIPTION:\n",
        "  Test\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (1) First commit\n",
    ]
    next_num = get_next_commit_number(lines, "test_cl")
    assert next_num == 1


# Tests for add_commit_entry
def test_add_commit_entry_new_history_field() -> None:
    """Test adding history entry when HISTORY field doesn't exist."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("DESCRIPTION:\n")
        f.write("  Test description\n")
        f.write("STATUS: Drafted\n")
        temp_path = f.name

    try:
        result = add_commit_entry(
            project_file=temp_path,
            cl_name="test_cl",
            note="Initial Commit",
            diff_path="~/.gai/diffs/test.diff",
            chat_path="~/.gai/chats/test.md",
        )
        assert result is True

        # Verify the file contents
        with open(temp_path) as f:
            content = f.read()
        assert "COMMITS:" in content
        assert "  (1) Initial Commit" in content
        assert "      | CHAT: ~/.gai/chats/test.md" in content
        assert "      | DIFF: ~/.gai/diffs/test.diff" in content
    finally:
        os.unlink(temp_path)


def test_add_commit_entry_existing_history_field() -> None:
    """Test adding history entry when HISTORY field already exists."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("DESCRIPTION:\n")
        f.write("  Test description\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("      | DIFF: ~/.gai/diffs/first.diff\n")
        temp_path = f.name

    try:
        result = add_commit_entry(
            project_file=temp_path,
            cl_name="test_cl",
            note="Second commit",
            diff_path="~/.gai/diffs/second.diff",
        )
        assert result is True

        # Verify the file contents
        with open(temp_path) as f:
            content = f.read()
        assert "  (1) First commit" in content
        assert "  (2) Second commit" in content
        assert "      | DIFF: ~/.gai/diffs/second.diff" in content
    finally:
        os.unlink(temp_path)


def test_add_commit_entry_nonexistent_file() -> None:
    """Test adding history entry to non-existent file."""
    result = add_commit_entry(
        project_file="/nonexistent/file.gp",
        cl_name="test_cl",
        note="Test",
    )
    assert result is False


def test_add_commit_entry_no_optional_fields() -> None:
    """Test adding history entry without optional fields."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        temp_path = f.name

    try:
        result = add_commit_entry(
            project_file=temp_path,
            cl_name="test_cl",
            note="Manual commit",
        )
        assert result is True

        # Verify the file contents
        with open(temp_path) as f:
            content = f.read()
        assert "  (1) Manual commit" in content
        assert "| CHAT:" not in content
        assert "| DIFF:" not in content
    finally:
        os.unlink(temp_path)


# Tests for save_diff
def test_save_diff_no_changes(tmp_path: Path) -> None:
    """Test save_diff when there are no changes (returns None)."""
    # Create a temporary directory that's not an hg repo
    result = save_diff("test_cl", str(tmp_path))
    # Should return None since not in an hg repo or no changes
    assert result is None


# Tests for _get_last_regular_commit_number
def test_get_last_regular_commit_number_no_history() -> None:
    """Test getting last regular number when no history exists."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
    ]
    last_num = _get_last_regular_commit_number(lines, "test_cl")
    assert last_num == 0


def test_get_last_regular_commit_number_with_history() -> None:
    """Test getting last regular number with existing history."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (1) First commit\n",
        "  (2) Second commit\n",
    ]
    last_num = _get_last_regular_commit_number(lines, "test_cl")
    assert last_num == 2


def test_get_last_regular_commit_number_skips_proposals() -> None:
    """Test that proposed entries are skipped when counting."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (1) First commit\n",
        "  (2) Second commit\n",
        "  (2a) Proposed change\n",
        "  (2b) Another proposal\n",
    ]
    last_num = _get_last_regular_commit_number(lines, "test_cl")
    assert last_num == 2


# Tests for _get_next_proposal_letter
def test_get_next_proposal_letter_no_proposals() -> None:
    """Test getting first proposal letter when none exist."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (1) First commit\n",
        "  (2) Second commit\n",
    ]
    letter = _get_next_proposal_letter(lines, "test_cl", 2)
    assert letter == "a"


def test_get_next_proposal_letter_with_existing() -> None:
    """Test getting next proposal letter when some exist."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (2) Second commit\n",
        "  (2a) First proposal\n",
        "  (2b) Second proposal\n",
    ]
    letter = _get_next_proposal_letter(lines, "test_cl", 2)
    assert letter == "c"


def test_get_next_proposal_letter_fills_gap() -> None:
    """Test that next letter fills gaps."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (2) Second commit\n",
        "  (2a) First proposal\n",
        "  (2c) Third proposal\n",  # 'b' is missing
    ]
    letter = _get_next_proposal_letter(lines, "test_cl", 2)
    assert letter == "b"


# Tests for add_proposed_commit_entry
def test_add_proposed_commit_entry_new_history() -> None:
    """Test adding proposed entry when no HISTORY exists."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        temp_path = f.name

    try:
        success, entry_id = add_proposed_commit_entry(
            project_file=temp_path,
            cl_name="test_cl",
            note="Proposed change",
            diff_path="~/.gai/diffs/test.diff",
        )
        assert success is True
        assert entry_id == "0a"  # No prior entries, base is 0

        with open(temp_path) as f:
            content = f.read()
        assert "COMMITS:" in content
        assert "(0a) Proposed change" in content
        assert "| DIFF: ~/.gai/diffs/test.diff" in content
    finally:
        os.unlink(temp_path)


def test_add_proposed_commit_entry_existing_history() -> None:
    """Test adding proposed entry to existing HISTORY."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("      | DIFF: ~/.gai/diffs/first.diff\n")
        temp_path = f.name

    try:
        success, entry_id = add_proposed_commit_entry(
            project_file=temp_path,
            cl_name="test_cl",
            note="Proposed change",
            diff_path="~/.gai/diffs/proposed.diff",
            chat_path="~/.gai/chats/proposed.md",
        )
        assert success is True
        assert entry_id == "1a"

        with open(temp_path) as f:
            content = f.read()
        assert "(1) First commit" in content
        assert "(1a) Proposed change" in content
        assert "| CHAT: ~/.gai/chats/proposed.md" in content
        assert "| DIFF: ~/.gai/diffs/proposed.diff" in content
    finally:
        os.unlink(temp_path)


def test_add_proposed_commit_entry_multiple_proposals() -> None:
    """Test adding multiple proposed entries."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (2) Second commit\n")
        f.write("  (2a) First proposal\n")
        temp_path = f.name

    try:
        success, entry_id = add_proposed_commit_entry(
            project_file=temp_path,
            cl_name="test_cl",
            note="Second proposal",
            diff_path="~/.gai/diffs/second.diff",
        )
        assert success is True
        assert entry_id == "2b"

        with open(temp_path) as f:
            content = f.read()
        assert "(2) Second commit" in content
        assert "(2a) First proposal" in content
        assert "(2b) Second proposal" in content
    finally:
        os.unlink(temp_path)


def test_add_proposed_commit_entry_nonexistent_file() -> None:
    """Test adding proposed entry to non-existent file."""
    success, entry_id = add_proposed_commit_entry(
        project_file="/nonexistent/file.gp",
        cl_name="test_cl",
        note="Test",
    )
    assert success is False
    assert entry_id is None
