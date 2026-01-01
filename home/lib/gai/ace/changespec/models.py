"""ChangeSpec data models and constants."""

import re
from dataclasses import dataclass

# Error suffix messages that require "!: " prefix when formatting/displaying
ERROR_SUFFIX_MESSAGES = frozenset(
    {
        "ZOMBIE",
        "Hook Command Failed",
        "Unresolved Critique Comments",
    }
)


def is_error_suffix(suffix: str | None) -> bool:
    """Check if a suffix indicates an error condition requiring '!: ' prefix.

    Args:
        suffix: The suffix value (message part only, not including "!: " prefix).

    Returns:
        True if the suffix indicates an error, False otherwise.
    """
    return suffix is not None and suffix in ERROR_SUFFIX_MESSAGES


def is_running_agent_suffix(suffix: str | None) -> bool:
    """Check if a suffix indicates a running agent requiring '@: ' prefix.

    Running agent suffixes contain timestamps (YYmmdd_HHMMSS format) that indicate
    an agent is actively working. Displayed with bold white on orange background.

    Args:
        suffix: The suffix value (message part only, not including "@: " prefix).

    Returns:
        True if the suffix is a running agent format, False otherwise.
    """
    if suffix is None:
        return False
    # New format with agent prefix: <agent>-YYmmdd_HHMMSS (e.g., fix_hook-251230_151429)
    # Agent prefix contains word chars only, followed by dash and 13-char timestamp
    if "-" in suffix:
        parts = suffix.rsplit("-", 1)
        if len(parts) == 2:
            agent, ts = parts
            if agent and len(ts) == 13 and ts[6] == "_":
                return True
    # Legacy format: 13 chars with underscore at position 6 (YYmmdd_HHMMSS)
    if len(suffix) == 13 and suffix[6] == "_":
        return True
    # Older legacy format: 12 digits (YYmmddHHMMSS)
    if len(suffix) == 12 and suffix.isdigit():
        return True
    return False


def is_running_process_suffix(suffix: str | None) -> bool:
    """Check if a suffix indicates a running hook process requiring '$: ' prefix.

    Running process suffixes are process IDs (PIDs) that indicate a hook
    subprocess is actively running. Displayed with bold black on yellow background.

    Args:
        suffix: The suffix value (message part only, not including "$: " prefix).

    Returns:
        True if the suffix is a PID (all digits), False otherwise.
    """
    if suffix is None:
        return False
    # PID format: all digits, typically 4-6 chars but could be more
    return suffix.isdigit() and len(suffix) >= 1


# Valid suffix_type values for HookStatusLine, CommitEntry, CommentEntry:
# - "error": Displayed with "!: " prefix (red color)
# - "running_agent": Displayed with "@: " prefix (agent is actively working)
# - "running_process": Displayed with "$: " prefix (hook subprocess running with PID)
# - "plain": Displayed without any prefix (explicitly no prefix, bypasses auto-detect)
# - None: Falls back to message-based auto-detection of type


# Suffix appended to STATUS line when ChangeSpec is ready to be mailed
READY_TO_MAIL_SUFFIX = " - (!: READY TO MAIL)"


def has_ready_to_mail_suffix(status: str) -> bool:
    """Check if a status has the READY TO MAIL suffix.

    Args:
        status: The STATUS value (e.g., "Drafted - (!: READY TO MAIL)").

    Returns:
        True if the status contains the READY TO MAIL marker.
    """
    return "(!: READY TO MAIL)" in status


def get_base_status(status: str) -> str:
    """Get base status without READY TO MAIL suffix.

    Args:
        status: The STATUS value (e.g., "Drafted - (!: READY TO MAIL)").

    Returns:
        The base status value (e.g., "Drafted").
    """
    if has_ready_to_mail_suffix(status):
        return status.replace(READY_TO_MAIL_SUFFIX, "").strip()
    return status


@dataclass
class CommitEntry:
    """Represents a single entry in the COMMITS field.

    Regular entries have format: (N) Note text
    Proposed entries have format: (Na) Note text (where 'a' is a lowercase letter)
    Entries can have optional suffix: (Na) Note text - (!: MSG) or - (MSG)
    """

    number: int
    note: str
    chat: str | None = None
    diff: str | None = None
    proposal_letter: str | None = None  # e.g., 'a', 'b', 'c' for proposed entries
    suffix: str | None = None  # e.g., "NEW PROPOSAL" (message without prefix)
    suffix_type: str | None = None  # "error" for !:, None for plain

    @property
    def is_proposed(self) -> bool:
        """Check if this is a proposed (not yet accepted) commit entry."""
        return self.proposal_letter is not None

    @property
    def display_number(self) -> str:
        """Get the display string for this entry's number (e.g., '2' or '2a')."""
        if self.proposal_letter:
            return f"{self.number}{self.proposal_letter}"
        return str(self.number)


def parse_commit_entry_id(entry_id: str) -> tuple[int, str]:
    """Parse a commit entry ID into (number, letter) for sorting.

    Args:
        entry_id: The entry ID string (e.g., "1", "1a", "2").

    Returns:
        Tuple of (number, letter) where letter is "" for regular entries.
        E.g., "1" -> (1, ""), "1a" -> (1, "a"), "2" -> (2, "").
    """
    # Match digit(s) optionally followed by a letter
    match = re.match(r"^(\d+)([a-z]?)$", entry_id)
    if match:
        return int(match.group(1)), match.group(2)
    # Fallback for unexpected format
    return 0, entry_id


@dataclass
class HookStatusLine:
    """Represents a single hook status line.

    Format in file:
      (N) [YYmmdd_HHMMSS] RUNNING/PASSED/FAILED/ZOMBIE (XmYs) - (SUFFIX)
      (N) [YYmmdd_HHMMSS] RUNNING/PASSED/FAILED/ZOMBIE (XmYs) - (!: MSG)
    Where N is the COMMITS entry number (1-based).

    The optional suffix can be:
    - A timestamp (YYmmdd_HHMMSS) indicating a fix-hook agent is running
    - "Hook Command Failed" indicating no fix-hook hints should be shown
    - "ZOMBIE" indicating a stale fix-hook agent (>2h old timestamp)

    Note: The suffix stores just the message (e.g., "ZOMBIE"), and the
    "!: " prefix is added when formatting for display/storage.
    """

    commit_entry_num: str  # The COMMITS entry ID (e.g., "1", "1a", "2")
    timestamp: str  # YYmmdd_HHMMSS format
    status: str  # RUNNING, PASSED, FAILED, ZOMBIE
    duration: str | None = None  # e.g., "1m23s"
    suffix: str | None = None  # e.g., "YYmmdd_HHMMSS", "ZOMBIE", "Hook Command Failed"
    suffix_type: str | None = None  # "error" for (!:), None for plain


@dataclass
class HookEntry:
    """Represents a single hook command entry in the HOOKS field.

    Format in file:
      some_command
        (1) [YYmmdd_HHMMSS] PASSED (1m23s)
        (2) [YYmmdd_HHMMSS] RUNNING

    Each hook can have multiple status lines, one per COMMITS entry.

    Command prefixes:
    - "!" prefix: FAILED status lines auto-append "- (!: Hook Command Failed)"
      to skip fix-hook hints.
    - "$" prefix: Hook is NOT run for proposed COMMITS entries (e.g., "1a").

    Prefixes can be combined as "!$" (e.g., "!$bb_hg_presubmit").
    All prefixes are stripped when displaying or running the command.
    """

    command: str
    status_lines: list[HookStatusLine] | None = None

    def _get_prefix(self) -> str:
        """Extract the prefix portion (any combination of '!' and '$')."""
        prefix = ""
        for char in self.command:
            if char in "!$":
                prefix += char
            else:
                break
        return prefix

    @property
    def skip_fix_hook(self) -> bool:
        """Check if '!' prefix is present (skip fix-hook on failure)."""
        return "!" in self._get_prefix()

    @property
    def skip_proposal_runs(self) -> bool:
        """Check if '$' prefix is present (skip for proposal entries)."""
        return "$" in self._get_prefix()

    @property
    def display_command(self) -> str:
        """Get the command for display purposes (strips leading '!' and '$')."""
        return self.command.lstrip("!$")

    @property
    def run_command(self) -> str:
        """Get the command to actually run (strips leading '!' and '$')."""
        return self.command.lstrip("!$")

    @property
    def latest_status_line(self) -> HookStatusLine | None:
        """Get the most recent status line (highest commit entry ID)."""
        if not self.status_lines:
            return None
        return max(
            self.status_lines,
            key=lambda sl: parse_commit_entry_id(sl.commit_entry_num),
        )

    def get_status_line_for_commit_entry(
        self, commit_entry_id: str
    ) -> HookStatusLine | None:
        """Get status line for a specific COMMITS entry ID (e.g., '1', '1a')."""
        if not self.status_lines:
            return None
        for sl in self.status_lines:
            if sl.commit_entry_num == commit_entry_id:
                return sl
        return None

    # Backward-compatible properties that delegate to latest_status_line
    @property
    def timestamp(self) -> str | None:
        """Get timestamp from the latest status line (backward compatibility)."""
        sl = self.latest_status_line
        return sl.timestamp if sl else None

    @property
    def status(self) -> str | None:
        """Get status from the latest status line (backward compatibility)."""
        sl = self.latest_status_line
        return sl.status if sl else None

    @property
    def duration(self) -> str | None:
        """Get duration from the latest status line (backward compatibility)."""
        sl = self.latest_status_line
        return sl.duration if sl else None


@dataclass
class CommentEntry:
    """Represents a single entry in the COMMENTS field.

    Format in file:
      [critique] ~/.gai/comments/<name>-critique-YYmmdd_HHMMSS.json
      [critique] ~/.gai/comments/<name>-critique-YYmmdd_HHMMSS.json - (SUFFIX)
      [critique:me] ~/.gai/comments/<name>-critique_me-YYmmdd_HHMMSS.json - (!: MSG)

    The optional suffix can be:
    - A timestamp (YYmmdd_HHMMSS) indicating a CRS workflow is running
    - "Unresolved Critique Comments" indicating CRS completed but comments remain
    - "ZOMBIE" indicating a stale CRS run (>2h old timestamp)

    Note: The suffix stores just the message (e.g., "ZOMBIE"), and the
    "!: " prefix is added when formatting for display/storage.
    """

    reviewer: str  # The comment type (e.g., "critique", "critique:me")
    file_path: str  # Full path to the comments JSON file
    suffix: str | None = (
        None  # e.g., "YYmmdd_HHMMSS", "ZOMBIE", "Unresolved Critique Comments"
    )
    suffix_type: str | None = None  # "error" for (!:), None for plain


@dataclass
class ChangeSpec:
    """Represents a single ChangeSpec."""

    name: str
    description: str
    parent: str | None
    cl: str | None
    status: str
    test_targets: list[str] | None
    kickstart: str | None
    file_path: str
    line_number: int
    commits: list[CommitEntry] | None = None
    hooks: list[HookEntry] | None = None
    comments: list[CommentEntry] | None = None
