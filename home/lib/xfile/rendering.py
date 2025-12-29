"""Rendered file creation for xfile processing."""

from __future__ import annotations

import glob as glob_module
import os
import re
from datetime import datetime
from pathlib import Path

from utils import (  # type: ignore[import-not-found]
    execute_cached_command,
    expand_braces,
    find_xfile,
    make_relative_to_home,
    process_command_substitution,
)


def generate_rendered_filepath(xfile_names: list[str]) -> Path:
    """Generate a unique filename for the rendered xfile."""
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    xfile_part = "_".join(xfile_names)
    # Sanitize filename
    xfile_part = re.sub(r"[^\w_-]", "_", xfile_part)
    filename = f"xfile_rendered_{xfile_part}_{timestamp}.txt"

    xcmds_dir = Path.cwd() / "xcmds"
    xcmds_dir.mkdir(exist_ok=True)
    return xcmds_dir / filename


def create_rendered_file(xfile_paths: list[Path], output_path: Path) -> None:
    """Create a rendered file that shows the processed xfile content."""
    rendered_content: list[str] = []

    # Add file header
    rendered_content.append(
        "# ----------------------------------------------------------------------------------"
    )
    rendered_content.append(
        "# This file contains a summary of some of the files that have been added to context."
    )
    rendered_content.append(
        "# ----------------------------------------------------------------------------------\n"
    )

    # Process each xfile
    for i, xfile_path in enumerate(xfile_paths):
        if i > 0:
            rendered_content.extend(["", "---", ""])

        # Read and process the xfile content
        try:
            content = xfile_path.read_text()
        except Exception as e:
            rendered_content.append(f"ERROR: Failed to read xfile: {xfile_path} - {e}")
            continue

        lines = content.splitlines()
        processed_xfiles: set[Path] = set()

        # Process lines with look-ahead to filter out comments/blanks before empty targets
        j = 0
        while j < len(lines):
            line = lines[j]
            trimmed = line.strip()

            # If this is a comment or blank line, we need to look ahead
            if not trimmed or trimmed.startswith("#"):
                # Collect consecutive comments and blank lines
                comment_group: list[str] = []
                k = j

                # Collect all consecutive comments and blank lines
                while k < len(lines):
                    current_line = lines[k]
                    current_trimmed = current_line.strip()

                    if not current_trimmed or current_trimmed.startswith("#"):
                        comment_group.append(current_line)
                        k += 1
                    else:
                        break  # Found a non-comment, non-blank line

                # Check if the next non-comment line (if any) produces output
                should_include_comments = True
                if k < len(lines):
                    next_line = lines[k]
                    next_rendered = _render_target_line(next_line, processed_xfiles)
                    if next_rendered is None:
                        # Next target produces no output, skip the comment group
                        should_include_comments = False

                # Add the comment group if we should include it
                if should_include_comments:
                    rendered_content.extend(comment_group)

                # Move to the next non-comment line
                j = k
            else:
                # This is a target line, render it normally
                rendered_line = _render_target_line(line, processed_xfiles)
                if rendered_line is not None:
                    rendered_content.append(rendered_line)
                j += 1

    # Write the rendered file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(rendered_content))


def _render_target_line(
    target_line: str, processed_xfiles: set[Path] | None = None
) -> str | None:
    """Render a single target line for the rendered file."""
    if processed_xfiles is None:
        processed_xfiles = set()

    trimmed = target_line.strip()

    # Preserve blank lines and comments
    if not trimmed:
        return ""

    if trimmed.startswith("#"):
        return trimmed

    # Handle x:reference
    xfile_match = re.match(r"^x:(.+)$", trimmed)
    if xfile_match:
        xfile_ref = xfile_match.group(1)
        xfile_path = find_xfile(xfile_ref)

        if xfile_path is None:
            return f"# ERROR: Referenced xfile not found: {xfile_ref}.txt"

        # Prevent infinite recursion
        if xfile_path in processed_xfiles:
            return f"# ERROR: Circular xfile reference detected: {xfile_ref}"

        # Mark this xfile as being processed
        processed_xfiles.add(xfile_path)

        result: list[str] = []
        # Read and process the referenced xfile
        try:
            content = xfile_path.read_text()
            lines = content.splitlines()
            for line in lines:
                rendered_ref_line = _render_target_line(line, processed_xfiles)
                if rendered_ref_line is not None:
                    result.append(rendered_ref_line)
        except Exception:
            result.append(f"# ERROR: Failed to read referenced xfile: {xfile_ref}.txt")

        # Unmark this xfile after processing
        processed_xfiles.discard(xfile_path)

        return "\n".join(result) if result else None

    # Handle !command that outputs file paths
    bang_match = re.match(r"^!(.+)$", trimmed)
    if bang_match:
        bang_cmd = bang_match.group(1)
        output, success = execute_cached_command(bang_cmd)

        if success and output and output.strip():
            result = []
            result.append(f"#\n# COMMAND THAT OUTPUT THESE FILES: {bang_cmd}")

            lines = output.splitlines()
            for line in lines:
                file_path_str = line.strip()
                if file_path_str:
                    file_path = Path(file_path_str)
                    if not file_path.is_absolute():
                        file_path = Path.cwd() / file_path
                    if file_path.is_file():
                        relative_path = make_relative_to_home(file_path)
                        result.append(str(relative_path))

            # Only return result if we have actual files
            if len(result) > 1:  # More than just the header comment
                return "\n".join(result)
            else:
                return None  # No output, skip this target entirely
        else:
            return None  # No output, skip this target entirely

    # Handle [[filename]] command format
    shell_match = re.match(r"^\[\[(.+)\]\]\s+(.+)$", trimmed)
    if shell_match:
        shell_filename = shell_match.group(1)
        shell_cmd = shell_match.group(2)

        # Process command substitution in the filename
        processed_filename = process_command_substitution(shell_filename)

        # Use custom extension if provided, otherwise default to .txt
        if not re.search(r"\.\w+$", processed_filename):
            processed_filename = f"{processed_filename}.txt"

        xcmds_dir = Path.cwd() / "xcmds"
        output_file = xcmds_dir / processed_filename
        relative_path = make_relative_to_home(output_file)

        # Execute shell command to check if it produces output
        output, success = execute_cached_command(shell_cmd)
        if success and output and output.strip():
            return (
                f"#\n# COMMAND THAT GENERATED THIS FILE: {shell_cmd}\n{relative_path}"
            )
        else:
            return None  # No output, skip this target entirely

    # Handle regular files, directories, and glob patterns
    expanded_path = Path(os.path.expanduser(trimmed))
    if not expanded_path.is_absolute():
        expanded_path = Path.cwd() / expanded_path

    # Check if it contains glob patterns
    if any(char in trimmed for char in ["*", "?", "[", "]", "{"]):
        result = []
        result.append(f"#\n# GLOB PATTERN: {trimmed}")

        expanded_pattern = os.path.expanduser(trimmed)
        brace_expanded = expand_braces(expanded_pattern)
        for pattern in brace_expanded:
            matches = glob_module.glob(pattern, recursive=True)
            for match in matches:
                match_path = Path(match)
                if match_path.is_file():
                    relative_path = make_relative_to_home(match_path)
                    result.append(str(relative_path))

        if len(result) == 1:
            result.append("# No files matched")

        return "\n".join(result)

    if expanded_path.is_dir():
        result = []
        result.append(f"#\n# DIRECTORY: {trimmed}")

        count = 0
        for file_path in expanded_path.rglob("*"):
            if file_path.is_file():
                relative_path = make_relative_to_home(file_path)
                result.append(str(relative_path))
                count += 1

        if count == 0:
            result.append("# No readable files in directory")

        return "\n".join(result)
    elif expanded_path.is_file():
        relative_path = make_relative_to_home(expanded_path)
        return str(relative_path)
    else:
        return f"# ERROR: File not found or not readable: {trimmed}"
