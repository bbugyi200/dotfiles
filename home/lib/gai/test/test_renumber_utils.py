"""Tests for renumber_utils shared module."""

from typing import Any

from renumber_utils import (
    build_commits_section,
    find_commits_section,
    parse_commit_entries,
    sort_entries_by_id,
    sort_hook_status_lines,
)

# Tests for sort_hook_status_lines


def test_sort_hook_status_lines_basic() -> None:
    """Test basic sorting of hook status lines by entry ID."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "HOOKS:\n",
        "  make lint\n",
        "      | (2) [251224_120100] PASSED (30s)\n",
        "      | (1) [251224_120000] PASSED (1m23s)\n",
    ]

    result = sort_hook_status_lines(lines, "test_cl")

    status_lines = [line for line in result if line.strip().startswith("| (")]
    assert "(1)" in status_lines[0]
    assert "(2)" in status_lines[1]


def test_sort_hook_status_lines_with_letters() -> None:
    """Test sorting with proposal letters."""
    lines = [
        "NAME: test_cl\n",
        "HOOKS:\n",
        "  make lint\n",
        "      | (2) [251224_120100] PASSED (30s)\n",
        "      | (1a) [251224_120050] RUNNING\n",
        "      | (1) [251224_120000] PASSED (1m23s)\n",
    ]

    result = sort_hook_status_lines(lines, "test_cl")

    status_lines = [line for line in result if line.strip().startswith("| (")]
    assert "(1)" in status_lines[0]
    assert "(1a)" in status_lines[1]
    assert "(2)" in status_lines[2]


def test_sort_hook_status_lines_ignores_other_changespecs() -> None:
    """Test that sorting only affects the target ChangeSpec."""
    lines = [
        "NAME: other_cl\n",
        "HOOKS:\n",
        "  make lint\n",
        "      | (2) [251224_120100] PASSED\n",
        "      | (1) [251224_120000] PASSED\n",
        "\n",
        "NAME: test_cl\n",
        "HOOKS:\n",
        "  make lint\n",
        "      | (2) [251224_120100] PASSED\n",
        "      | (1) [251224_120000] PASSED\n",
    ]

    result = sort_hook_status_lines(lines, "test_cl")

    # other_cl should stay unsorted (2 before 1)
    other_section = "".join(result[:6])
    assert other_section.index("(2)") < other_section.index("(1)")

    # test_cl should be sorted (1 before 2)
    test_section = "".join(result[6:])
    assert test_section.index("(1)") < test_section.index("(2)")


# Tests for build_commits_section


def test_build_commits_section_basic() -> None:
    """Test building commits section from entries."""
    entries: list[dict[str, Any]] = [
        {
            "number": 1,
            "letter": None,
            "note": "First commit",
            "chat": None,
            "diff": None,
        },
        {
            "number": 2,
            "letter": None,
            "note": "Second commit",
            "chat": None,
            "diff": None,
        },
    ]

    result = build_commits_section(entries)

    assert result[0] == "COMMITS:\n"
    assert result[1] == "  (1) First commit\n"
    assert result[2] == "  (2) Second commit\n"


def test_build_commits_section_with_metadata() -> None:
    """Test building commits section with chat and diff metadata."""
    entries: list[dict[str, Any]] = [
        {
            "number": 1,
            "letter": "a",
            "note": "Proposal",
            "chat": "/path/to/chat",
            "diff": "/path/to/diff",
        },
    ]

    result = build_commits_section(entries)

    assert result[0] == "COMMITS:\n"
    assert result[1] == "  (1a) Proposal\n"
    assert result[2] == "      | CHAT: /path/to/chat\n"
    assert result[3] == "      | DIFF: /path/to/diff\n"


# Tests for sort_entries_by_id


def test_sort_entries_by_id_basic() -> None:
    """Test sorting entries by number then letter."""
    entries: list[dict[str, Any]] = [
        {"number": 2, "letter": None},
        {"number": 1, "letter": "b"},
        {"number": 1, "letter": None},
        {"number": 1, "letter": "a"},
    ]

    result = sort_entries_by_id(entries)

    assert result[0]["number"] == 1 and result[0]["letter"] is None
    assert result[1]["number"] == 1 and result[1]["letter"] == "a"
    assert result[2]["number"] == 1 and result[2]["letter"] == "b"
    assert result[3]["number"] == 2 and result[3]["letter"] is None


# Tests for parse_commit_entries


def test_parse_commit_entries_basic() -> None:
    """Test parsing basic commit entry lines."""
    commit_lines = [
        "  (1) First commit\n",
        "  (2) Second commit\n",
    ]

    result = parse_commit_entries(commit_lines)

    assert len(result) == 2
    assert result[0]["number"] == 1
    assert result[0]["letter"] is None
    assert result[0]["note"] == "First commit"
    assert result[1]["number"] == 2


def test_parse_commit_entries_with_metadata() -> None:
    """Test parsing commit entries with CHAT and DIFF lines."""
    commit_lines = [
        "  (1) First commit\n",
        "      | CHAT: /path/to/chat\n",
        "      | DIFF: /path/to/diff\n",
    ]

    result = parse_commit_entries(commit_lines)

    assert len(result) == 1
    assert result[0]["chat"] == "/path/to/chat"
    assert result[0]["diff"] == "/path/to/diff"


def test_parse_commit_entries_with_raw_lines() -> None:
    """Test parsing with include_raw_lines=True."""
    commit_lines = [
        "  (1) First commit\n",
        "      | CHAT: /path/to/chat\n",
    ]

    result = parse_commit_entries(commit_lines, include_raw_lines=True)

    assert len(result) == 1
    assert "raw_lines" in result[0]
    assert len(result[0]["raw_lines"]) == 2


def test_parse_commit_entries_without_raw_lines() -> None:
    """Test parsing without include_raw_lines (default)."""
    commit_lines = [
        "  (1) First commit\n",
    ]

    result = parse_commit_entries(commit_lines)

    assert len(result) == 1
    assert "raw_lines" not in result[0]


def test_parse_commit_entries_with_proposals() -> None:
    """Test parsing commit entries with proposal letters."""
    commit_lines = [
        "  (1) First commit\n",
        "  (1a) Proposal A - (!: NEW PROPOSAL)\n",
    ]

    result = parse_commit_entries(commit_lines)

    assert len(result) == 2
    assert result[1]["number"] == 1
    assert result[1]["letter"] == "a"
    assert "NEW PROPOSAL" in result[1]["note"]


# Tests for find_commits_section


def test_find_commits_section_basic() -> None:
    """Test finding commits section in a project file."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (1) First commit\n",
        "  (2) Second commit\n",
        "HOOKS:\n",
    ]

    start, end = find_commits_section(lines, "test_cl")

    assert start == 2
    assert end == 5


def test_find_commits_section_not_found() -> None:
    """Test finding commits section when CL not found."""
    lines = [
        "NAME: other_cl\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (1) First commit\n",
    ]

    start, end = find_commits_section(lines, "test_cl")

    assert start == -1
    assert end == -1


def test_find_commits_section_with_metadata() -> None:
    """Test finding commits section with CHAT/DIFF metadata lines."""
    lines = [
        "NAME: test_cl\n",
        "COMMITS:\n",
        "  (1) First commit\n",
        "      | CHAT: /path/to/chat\n",
        "      | DIFF: /path/to/diff\n",
        "HOOKS:\n",
    ]

    start, end = find_commits_section(lines, "test_cl")

    assert start == 1
    assert end == 5


def test_find_commits_section_at_end_of_file() -> None:
    """Test finding commits section at end of file (no next section)."""
    lines = [
        "NAME: test_cl\n",
        "COMMITS:\n",
        "  (1) First commit\n",
    ]

    start, end = find_commits_section(lines, "test_cl")

    assert start == 1
    assert end == 3
