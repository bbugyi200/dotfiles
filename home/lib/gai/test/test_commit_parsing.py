"""Tests for COMMITS field parsing and CommitEntry dataclass."""

from ace.changespec import CommitEntry
from ace.changespec.parser import _build_commit_entry, _parse_changespec_from_lines


# Tests for _build_commit_entry
def test_build_commit_entry_all_fields() -> None:
    """Test building CommitEntry with all fields."""
    entry_dict: dict[str, str | int | None] = {
        "number": 1,
        "note": "Initial Commit",
        "chat": "~/.gai/chats/test.md",
        "diff": "~/.gai/diffs/test.diff",
    }
    entry = _build_commit_entry(entry_dict)
    assert entry.number == 1
    assert entry.note == "Initial Commit"
    assert entry.chat == "~/.gai/chats/test.md"
    assert entry.diff == "~/.gai/diffs/test.diff"


def test_build_commit_entry_missing_optional_fields() -> None:
    """Test building CommitEntry with only required fields."""
    entry_dict: dict[str, str | int | None] = {
        "number": 2,
        "note": "Test commit",
        "chat": None,
        "diff": None,
    }
    entry = _build_commit_entry(entry_dict)
    assert entry.number == 2
    assert entry.note == "Test commit"
    assert entry.chat is None
    assert entry.diff is None


def test_build_commit_entry_defaults() -> None:
    """Test building CommitEntry with empty dict (all defaults)."""
    entry_dict: dict[str, str | int | None] = {}
    entry = _build_commit_entry(entry_dict)
    assert entry.number == 0
    assert entry.note == ""
    assert entry.chat is None
    assert entry.diff is None


# Tests for HISTORY field parsing
def test_parse_changespec_with_history() -> None:
    """Test parsing ChangeSpec with HISTORY field."""
    lines = [
        "## ChangeSpec\n",
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test description\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (1) Initial Commit\n",
        "      | CHAT: ~/.gai/chats/test-251221130813.md\n",
        "      | DIFF: ~/.gai/diffs/test_251221130813.diff\n",
        "  (2) Added feature\n",
        "      | DIFF: ~/.gai/diffs/test_251221140000.diff\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    assert changespec.name == "test_cl"
    assert changespec.commits is not None
    assert len(changespec.commits) == 2
    # Check first entry
    assert changespec.commits[0].number == 1
    assert changespec.commits[0].note == "Initial Commit"
    assert changespec.commits[0].chat == "~/.gai/chats/test-251221130813.md"
    assert changespec.commits[0].diff == "~/.gai/diffs/test_251221130813.diff"
    # Check second entry
    assert changespec.commits[1].number == 2
    assert changespec.commits[1].note == "Added feature"
    assert changespec.commits[1].chat is None
    assert changespec.commits[1].diff == "~/.gai/diffs/test_251221140000.diff"


def test_parse_changespec_without_history() -> None:
    """Test parsing ChangeSpec without HISTORY field."""
    lines = [
        "## ChangeSpec\n",
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test description\n",
        "STATUS: Drafted\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    assert changespec.name == "test_cl"
    assert changespec.commits is None


def test_parse_changespec_history_without_optional_fields() -> None:
    """Test parsing HISTORY entry without CHAT field."""
    lines = [
        "## ChangeSpec\n",
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test description\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (1) Manual commit\n",
        "      | DIFF: ~/.gai/diffs/test.diff\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    assert changespec.commits is not None
    assert len(changespec.commits) == 1
    assert changespec.commits[0].number == 1
    assert changespec.commits[0].note == "Manual commit"
    assert changespec.commits[0].chat is None
    assert changespec.commits[0].diff == "~/.gai/diffs/test.diff"


# Tests for CommitEntry dataclass
def test_history_entry_dataclass() -> None:
    """Test CommitEntry dataclass creation."""
    entry = CommitEntry(
        number=1,
        note="Test note",
        chat="test.md",
        diff="test.diff",
    )
    assert entry.number == 1
    assert entry.note == "Test note"
    assert entry.chat == "test.md"
    assert entry.diff == "test.diff"


def test_history_entry_dataclass_defaults() -> None:
    """Test CommitEntry dataclass with default values."""
    entry = CommitEntry(number=1, note="Test")
    assert entry.number == 1
    assert entry.note == "Test"
    assert entry.chat is None
    assert entry.diff is None


# Tests for CommitEntry proposal properties
def test_history_entry_is_proposed_false() -> None:
    """Test is_proposed returns False for regular entries."""
    entry = CommitEntry(number=1, note="Test")
    assert entry.is_proposed is False


def test_history_entry_is_proposed_true() -> None:
    """Test is_proposed returns True for proposed entries."""
    entry = CommitEntry(number=2, note="Test", proposal_letter="a")
    assert entry.is_proposed is True


def test_history_entry_display_number_regular() -> None:
    """Test display_number for regular entries."""
    entry = CommitEntry(number=3, note="Test")
    assert entry.display_number == "3"


def test_history_entry_display_number_proposed() -> None:
    """Test display_number for proposed entries."""
    entry = CommitEntry(number=2, note="Test", proposal_letter="b")
    assert entry.display_number == "2b"


# Tests for parsing proposed HISTORY entries
def test_parse_changespec_with_proposed_entries() -> None:
    """Test parsing ChangeSpec with proposed HISTORY entries."""
    lines = [
        "## ChangeSpec\n",
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test description\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (1) Initial Commit\n",
        "      | DIFF: ~/.gai/diffs/first.diff\n",
        "  (2) Second commit\n",
        "      | DIFF: ~/.gai/diffs/second.diff\n",
        "  (2a) First proposal\n",
        "      | DIFF: ~/.gai/diffs/proposal_a.diff\n",
        "  (2b) Second proposal\n",
        "      | CHAT: ~/.gai/chats/proposal_b.md\n",
        "      | DIFF: ~/.gai/diffs/proposal_b.diff\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    assert changespec.commits is not None
    assert len(changespec.commits) == 4

    # Regular entries
    assert changespec.commits[0].number == 1
    assert changespec.commits[0].is_proposed is False
    assert changespec.commits[0].display_number == "1"

    assert changespec.commits[1].number == 2
    assert changespec.commits[1].is_proposed is False
    assert changespec.commits[1].display_number == "2"

    # Proposed entries
    assert changespec.commits[2].number == 2
    assert changespec.commits[2].proposal_letter == "a"
    assert changespec.commits[2].is_proposed is True
    assert changespec.commits[2].display_number == "2a"
    assert changespec.commits[2].note == "First proposal"

    assert changespec.commits[3].number == 2
    assert changespec.commits[3].proposal_letter == "b"
    assert changespec.commits[3].is_proposed is True
    assert changespec.commits[3].display_number == "2b"
    assert changespec.commits[3].chat == "~/.gai/chats/proposal_b.md"
