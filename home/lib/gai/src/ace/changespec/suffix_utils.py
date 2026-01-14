"""Suffix parsing utilities for ChangeSpec entries."""

from typing import NamedTuple


class _ParsedSuffix(NamedTuple):
    """Result of parsing a suffix value."""

    value: str | None
    suffix_type: str | None


# Prefix mappings in priority order (longer prefixes first)
_PREFIX_MAP: list[tuple[str, str | None]] = [
    ("~!:", "rejected_proposal"),
    ("~@:", "killed_agent"),
    ("~$:", "killed_process"),
    ("?$:", "pending_dead_process"),
    ("!:", "error"),
    ("@:", "running_agent"),
    ("$:", "running_process"),
    ("%:", "summarize_complete"),
    ("~:", None),  # Legacy prefix, treated as plain suffix
]


def parse_suffix_prefix(suffix_val: str | None) -> _ParsedSuffix:
    """Parse suffix prefix markers and return (value, suffix_type).

    Handles all suffix type markers:
    - "~!:" -> rejected_proposal
    - "!:" -> error
    - "~@:" -> killed_agent
    - "@:" -> running_agent
    - "@" (alone) -> running_agent with empty value
    - "~$:" -> killed_process
    - "?$:" -> pending_dead_process
    - "$:" -> running_process
    - "%:" -> summarize_complete
    - "%" (alone) -> summarize_complete with empty value
    - "~:" -> plain (legacy, no suffix_type)

    Args:
        suffix_val: The raw suffix string to parse

    Returns:
        _ParsedSuffix with value (message without prefix) and suffix_type.
    """
    if suffix_val is None:
        return _ParsedSuffix(None, None)

    for prefix, suffix_type in _PREFIX_MAP:
        if suffix_val.startswith(prefix):
            return _ParsedSuffix(suffix_val[len(prefix) :].strip(), suffix_type)

    # Handle standalone markers
    if suffix_val == "@":
        return _ParsedSuffix("", "running_agent")
    if suffix_val == "%":
        return _ParsedSuffix("", "summarize_complete")

    # No prefix - return as-is with no suffix_type
    return _ParsedSuffix(suffix_val, None)
