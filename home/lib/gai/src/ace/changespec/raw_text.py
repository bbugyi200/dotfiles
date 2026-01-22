"""Extract raw ChangeSpec text from project files."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ChangeSpec


def get_raw_changespec_text(cs: ChangeSpec) -> str | None:
    """Extract the raw text of a ChangeSpec from its source file.

    Reads the file at cs.file_path starting from cs.line_number and extracts
    the exact raw text until one of these end conditions:
    - A `## ChangeSpec` header line (start of another ChangeSpec)
    - Two consecutive blank lines
    - A `NAME:` line (start of another ChangeSpec without header)
    - End of file

    Args:
        cs: The ChangeSpec to extract raw text for.

    Returns:
        The raw text of the ChangeSpec, or None if the file cannot be read.
        Trailing blank lines are stripped, but internal formatting is preserved.
    """
    try:
        with open(cs.file_path) as f:
            lines = f.readlines()
    except OSError:
        return None

    # Convert to 0-based index (line_number is 1-based)
    start_idx = cs.line_number - 1

    if start_idx < 0 or start_idx >= len(lines):
        return None

    result_lines: list[str] = []
    consecutive_blank_lines = 0
    idx = start_idx

    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()

        # Check for end conditions (but not on the first line)
        if idx > start_idx:
            # Check for ## ChangeSpec header
            if re.match(r"^##\s+ChangeSpec", stripped):
                break

            # Check for NAME: line (new ChangeSpec without header)
            if line.startswith("NAME: "):
                break

        # Track consecutive blank lines
        if stripped == "":
            consecutive_blank_lines += 1
            # Two consecutive blank lines end the ChangeSpec
            if consecutive_blank_lines >= 2:
                # Include one blank line for cleaner output
                result_lines.append(line)
                break
        else:
            consecutive_blank_lines = 0

        result_lines.append(line)
        idx += 1

    # Strip trailing blank lines but preserve internal formatting
    while result_lines and result_lines[-1].strip() == "":
        result_lines.pop()

    if not result_lines:
        return None

    # Join and return without trailing newline (rstrip one newline if present)
    result = "".join(result_lines)
    return result.rstrip("\n")
