"""Proposal parsing and lookup functions for accept workflow."""

import re

from ace.changespec import CommitEntry


def parse_proposal_id(proposal_id: str) -> tuple[int, str] | None:
    """Parse a proposal ID into base number and letter.

    Args:
        proposal_id: The proposal ID (e.g., "2a", "2b").

    Returns:
        Tuple of (base_number, letter) or None if invalid.
    """
    match = re.match(r"^(\d+)([a-z])$", proposal_id)
    if not match:
        return None
    return int(match.group(1)), match.group(2)


def parse_proposal_entries(args: list[str]) -> list[tuple[str, str | None]] | None:
    """Parse proposal entry arguments into (id, msg) tuples.

    Supports:
    - New syntax: "2b(Add foobar field)" - id with optional message in parentheses
    - Legacy syntax: "2b" followed by optional separate message argument

    Args:
        args: List of arguments (e.g., ["2a(msg)", "2b"] or ["2a", "msg"]).

    Returns:
        List of (id, msg) tuples or None if invalid format.
    """
    if not args:
        return None

    # Regex patterns
    id_with_msg_pattern = re.compile(r"^(\d+[a-z])\((.+)\)$")  # "2a(msg)"
    bare_id_pattern = re.compile(r"^(\d+[a-z])$")  # "2a"

    entries: list[tuple[str, str | None]] = []

    i = 0
    while i < len(args):
        arg = args[i]

        # Check for new syntax with message in parentheses: "2a(msg)"
        match_with_msg = id_with_msg_pattern.match(arg)
        if match_with_msg:
            proposal_id = match_with_msg.group(1)
            msg = match_with_msg.group(2)
            entries.append((proposal_id, msg))
            i += 1
            continue

        # Check for bare ID: "2a"
        match_bare = bare_id_pattern.match(arg)
        if match_bare:
            proposal_id = match_bare.group(1)
            # Check if next arg is a message (not another proposal ID)
            if i + 1 < len(args):
                next_arg = args[i + 1]
                # If next arg doesn't look like a proposal ID (with or without msg),
                # treat it as a legacy message
                if not id_with_msg_pattern.match(
                    next_arg
                ) and not bare_id_pattern.match(next_arg):
                    entries.append((proposal_id, next_arg))
                    i += 2
                    continue
            entries.append((proposal_id, None))
            i += 1
            continue

        # Invalid format
        return None

    return entries if entries else None


def expand_shorthand_proposals(
    args: list[str],
    last_accepted_base: str | None,
) -> list[str] | None:
    """Expand shorthand proposal entries to full IDs.

    Shorthand format:
    - "a" -> "2a" (where 2 is last_accepted_base)
    - "a(msg)" -> "2a(msg)"

    Full format (pass through unchanged):
    - "2a", "2b(msg)", etc.

    Args:
        args: List of arguments (may contain shorthand or full IDs).
        last_accepted_base: The base number to prepend (e.g., "2").
            If None, shorthand cannot be expanded.

    Returns:
        List of expanded arguments, or None if shorthand used but
        last_accepted_base is not available or invalid format encountered.
    """
    # Regex patterns
    shorthand_bare = re.compile(r"^([a-z])$")  # "a"
    shorthand_with_msg = re.compile(r"^([a-z])\((.+)\)$")  # "a(msg)"
    full_id_bare = re.compile(r"^\d+[a-z]$")  # "2a"
    full_id_with_msg = re.compile(r"^\d+[a-z]\(.+\)$")  # "2a(msg)"

    expanded: list[str] = []

    for arg in args:
        # Check if already full format
        if full_id_bare.match(arg) or full_id_with_msg.match(arg):
            expanded.append(arg)
            continue

        # Check for shorthand bare letter
        match_bare = shorthand_bare.match(arg)
        if match_bare:
            if last_accepted_base is None:
                return None  # Cannot expand without base
            letter = match_bare.group(1)
            expanded.append(f"{last_accepted_base}{letter}")
            continue

        # Check for shorthand letter with message
        match_with_msg = shorthand_with_msg.match(arg)
        if match_with_msg:
            if last_accepted_base is None:
                return None
            letter = match_with_msg.group(1)
            msg = match_with_msg.group(2)
            expanded.append(f"{last_accepted_base}{letter}({msg})")
            continue

        # Invalid format
        return None

    return expanded


def parse_proposal_entries_with_shorthand(
    args: list[str],
    last_accepted_base: str | None,
) -> list[tuple[str, str | None]] | None:
    """Parse proposal entries with shorthand expansion support.

    Args:
        args: List of arguments (shorthand or full format).
        last_accepted_base: Base number for shorthand expansion.

    Returns:
        List of (id, msg) tuples or None if invalid.
    """
    expanded = expand_shorthand_proposals(args, last_accepted_base)
    if expanded is None:
        return None
    return parse_proposal_entries(expanded)


def find_proposal_entry(
    commits: list[CommitEntry] | None,
    base_number: int,
    letter: str,
) -> CommitEntry | None:
    """Find a proposal entry in commits by base number and letter.

    Args:
        commits: List of commit entries.
        base_number: The base number (e.g., 2 for "2a").
        letter: The proposal letter (e.g., "a" for "2a").

    Returns:
        The matching CommitEntry or None if not found.
    """
    if not commits:
        return None
    for entry in commits:
        if entry.number == base_number and entry.proposal_letter == letter:
            return entry
    return None
