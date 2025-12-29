"""Xfile reference processing and STDIN handling."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from targets import resolve_target  # type: ignore[import-not-found]
from utils import (  # type: ignore[import-not-found]
    clear_command_cache,
    ensure_xfiles_dirs,
    find_xfile,
    format_output_path,
    get_global_xfiles_dir,
    get_local_xfiles_dir,
)


def list_xfiles() -> int:
    """List available xfiles from both global and local directories."""
    local_dir = get_local_xfiles_dir()
    global_dir = get_global_xfiles_dir()

    print("Local xfiles:")
    local_xfiles = sorted(local_dir.glob("*.txt"))
    if local_xfiles:
        for xfile_path in local_xfiles:
            print(f"  [L] {xfile_path.stem}")
    else:
        print("  (none)")

    print("\nGlobal xfiles:")
    global_xfiles = sorted(global_dir.glob("*.txt"))
    if global_xfiles:
        for xfile_path in global_xfiles:
            print(f"  [G] {xfile_path.stem}")
    else:
        print("  (none)")

    return 0


def _parse_xfile_metadata(xfile_path: Path) -> tuple[str, dict[str, str]]:
    """Parse xfile to extract header and descriptions for targets.

    Returns:
        A tuple of (header_text, target_descriptions) where:
        - header_text: Custom H3 header or "Context Files" if none found
        - target_descriptions: Dict mapping target lines to their descriptions
    """
    content = xfile_path.read_text()
    lines = content.splitlines()

    if not lines:
        return "Context Files", {}

    # Check for optional header comment at the top
    header_text = "Context Files"
    start_idx = 0

    if lines and lines[0].startswith("# "):
        # Extract header text (remove '# ' prefix)
        header_text = lines[0][2:].strip()
        # Check if followed by blank line
        if len(lines) > 1 and not lines[1].strip():
            start_idx = 2  # Skip header and blank line
        else:
            # Not a valid header, reset
            header_text = "Context Files"
            start_idx = 0

    # Parse descriptions for targets
    target_descriptions: dict[str, str] = {}
    current_description = ""
    i = start_idx

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Check if this is a comment
        if stripped.startswith("# "):
            # Extract description text (remove '# ' prefix)
            desc_text = stripped[2:].strip()
            if current_description:
                current_description += " " + desc_text
            else:
                current_description = desc_text
            i += 1
            continue

        # Check if this is a blank line
        if not stripped:
            # Blank line resets current description
            current_description = ""
            i += 1
            continue

        # This is a target line
        if current_description:
            # Associate current description with this target
            target_descriptions[stripped] = current_description

        i += 1

    return header_text, target_descriptions


def _process_xfile_reference(
    stripped: str,
    current_description: str,
    description_groups: dict[str, list[str]],
    no_description_files: list[str],
    absolute: bool,
    cwd: Path,
) -> bool:
    """Process x:reference, modifying description_groups and no_description_files."""
    xfile_ref_match = re.match(r"^x:(.+)$", stripped)
    if not xfile_ref_match:
        return False

    referenced_xfile_path = find_xfile(xfile_ref_match.group(1))

    if referenced_xfile_path and current_description:
        try:
            resolved_files = resolve_target(stripped)
            if resolved_files:
                formatted_files = [
                    format_output_path(f, absolute, cwd) for f in resolved_files
                ]
                if current_description not in description_groups:
                    description_groups[current_description] = []
                description_groups[current_description].extend(formatted_files)
        except Exception:
            pass
    elif referenced_xfile_path:
        ref_content = referenced_xfile_path.read_text()
        ref_lines = ref_content.splitlines()
        ref_start_idx = (
            2
            if ref_lines
            and ref_lines[0].startswith("# ")
            and len(ref_lines) > 1
            and not ref_lines[1].strip()
            else 0
        )

        ref_current_description = ""
        for ref_line in ref_lines[ref_start_idx:]:
            ref_stripped = ref_line.strip()

            if ref_stripped.startswith("# "):
                desc_text = ref_stripped[2:].strip()
                ref_current_description = (
                    ref_current_description + " " + desc_text
                    if ref_current_description
                    else desc_text
                )
                continue

            if not ref_stripped:
                ref_current_description = ""
                continue

            try:
                resolved_files = resolve_target(ref_stripped)
                if resolved_files:
                    formatted_files = [
                        format_output_path(f, absolute, cwd) for f in resolved_files
                    ]
                    if ref_current_description:
                        if ref_current_description not in description_groups:
                            description_groups[ref_current_description] = []
                        description_groups[ref_current_description].extend(
                            formatted_files
                        )
                    else:
                        no_description_files.extend(formatted_files)
            except Exception:
                pass

    return True


def _format_xfile_with_at_prefix(xfile_name: str, absolute: bool) -> str:
    """Format an xfile's resolved files with @ prefix (old -A behavior).

    Returns a markdown section with header and @ prefixed files with descriptions.
    Returns empty string if xfile not found or produces no files.
    """
    # Clear command cache for each xfile processing
    clear_command_cache()

    # Ensure directories exist
    ensure_xfiles_dirs()

    # Find and process the xfile
    xfile_path = find_xfile(xfile_name)
    if xfile_path is None:
        return f"### Context Files\n+ @ERROR: xfile '{xfile_name}' not found"

    # Parse metadata (header and descriptions)
    header_text, _ = _parse_xfile_metadata(xfile_path)

    # Read xfile content to process line by line with descriptions
    content = xfile_path.read_text()
    lines = content.splitlines()

    # Skip header if present
    start_idx = 0
    if lines and lines[0].startswith("# ") and len(lines) > 1 and not lines[1].strip():
        start_idx = 2

    # Process each target line and track which files came from which description
    cwd = Path.cwd()
    description_groups: dict[str, list[str]] = {}  # description -> list of files
    no_description_files: list[str] = []

    current_description = ""
    for i in range(start_idx, len(lines)):
        line = lines[i]
        stripped = line.strip()

        # Skip comments and blank lines
        if stripped.startswith("# "):
            # Extract description
            desc_text = stripped[2:].strip()
            if current_description:
                current_description += " " + desc_text
            else:
                current_description = desc_text
            continue

        if not stripped:
            current_description = ""
            continue

        # Check if this is an x:reference to another xfile
        if _process_xfile_reference(
            stripped,
            current_description,
            description_groups,
            no_description_files,
            absolute,
            cwd,
        ):
            continue

        # This is a regular target line - resolve it to files
        try:
            resolved_files = resolve_target(stripped)
            if resolved_files:
                formatted_files = [
                    format_output_path(f, absolute, cwd) for f in resolved_files
                ]

                if current_description:
                    # Add to description group
                    if current_description not in description_groups:
                        description_groups[current_description] = []
                    description_groups[current_description].extend(formatted_files)
                else:
                    # No description
                    no_description_files.extend(formatted_files)
        except Exception:
            # Skip files that fail to resolve
            pass

    # Build output
    result = [f"### {header_text}"]

    # Add description groups
    for description, files in description_groups.items():
        if len(files) == 1:
            # Single file with description
            result.append(f"+ @{files[0]} - {description}")
        else:
            # Multiple files with description
            result.append(f"+ {description}:")
            for file in files:
                result.append(f"  - @{file}")

    # Add files without descriptions
    for file in no_description_files:
        result.append(f"+ @{file}")

    # If no files were resolved, return empty
    if len(result) == 1:  # Only header
        return ""

    return "\n".join(result)


def _process_inline_target(
    line: str, inline_pattern: str, absolute: bool, cwd: Path
) -> str:
    """Process inline target x::(<target>), returns processed line."""
    inline_match = re.search(inline_pattern, line)
    if not inline_match:
        return line

    try:
        resolved_files = resolve_target(inline_match.group(1).strip())
        if not resolved_files:
            return re.sub(inline_pattern, "@ERROR: No files found", line, count=1)

        formatted_files = [format_output_path(f, absolute, cwd) for f in resolved_files]

        if len(formatted_files) == 1:
            return re.sub(inline_pattern, f"@{formatted_files[0]}", line, count=1)

        # Multi-file - must be in a bullet
        bullet_match = re.match(r"^(\s*)([\+\-\*])\s+", line)
        if not bullet_match:
            return re.sub(
                inline_pattern,
                "@ERROR: Multi-file target must be in markdown bullet",
                line,
                count=1,
            )

        indent, bullet = bullet_match.group(1), bullet_match.group(2)
        result_lines = [
            re.sub(inline_pattern, f"@{formatted_files[0]}", line, count=1).rstrip()
            + "\n"
        ]
        result_lines.extend(f"{indent}{bullet} @{f}\n" for f in formatted_files[1:])
        return "".join(result_lines)
    except Exception as e:
        return re.sub(
            inline_pattern, f"@ERROR: Failed to resolve target: {e}", line, count=1
        )


def process_stdin_with_xfile_refs(absolute: bool) -> int:
    """Process STDIN content, replacing x::foobar and x::(<target>) patterns.

    Reads from STDIN and searches for:
    - x::foobar - references to xfiles
    - x::(<target>) - inline target references

    For each pattern found, replaces it with the formatted xfile output.
    """
    # Read all content from STDIN
    stdin_content = sys.stdin.read()
    lines = stdin_content.splitlines(keepends=True)

    # Process line by line to handle bullet formatting for multi-file targets
    processed_lines = []
    cwd = Path.cwd()

    for line in lines:
        # First, replace x::foobar patterns (xfile references)
        xfile_pattern = r"x::([a-zA-Z0-9_-]+)"

        def replace_xfile_ref(match: re.Match[str]) -> str:
            xfile_name = match.group(1)
            return _format_xfile_with_at_prefix(xfile_name, absolute)

        line = re.sub(xfile_pattern, replace_xfile_ref, line)

        # Then, handle x::(<target>) patterns (inline targets)
        inline_pattern = r"x::\(([^)]+)\)"
        line = _process_inline_target(line, inline_pattern, absolute, cwd)

        processed_lines.append(line)

    # Output the processed content
    print("".join(processed_lines), end="")

    return 0
