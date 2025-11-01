#!/usr/bin/env python3
"""xfile - Process xfile targets and resolve them to actual files.

xfiles contain targets (one per line) which can be:
- File paths (absolute or relative to cwd)
- Glob patterns (relative to cwd)
- Directory paths (absolute or relative to cwd)
- Shell commands in [[filename]] command format
- Commands that output file paths in !command format
- xfile references in x:filename format
"""

from __future__ import annotations

import argparse
import glob as glob_module
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# Command cache to avoid running the same command multiple times
_command_cache: dict[str, tuple[str | None, bool]] = {}


def main(argv: list[str] | None = None) -> int:
    """Main entry point for xfile command."""
    parser = argparse.ArgumentParser(
        description="Process xfile targets and resolve them to actual files"
    )
    parser.add_argument(
        "xfiles",
        nargs="+",
        help="Names of xfiles to process (without .txt extension)",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List available xfiles",
    )
    parser.add_argument(
        "--render",
        "-r",
        action="store_true",
        help="Create rendered summary file",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file for rendered summary (default: auto-generated in xcmds/)",
    )
    parser.add_argument(
        "--absolute",
        action="store_true",
        help="Output absolute file paths (default: relative to current directory)",
    )
    parser.add_argument(
        "--prefix-at",
        action="store_true",
        help="Prefix all output file paths with '@'",
    )

    args = parser.parse_args(argv)

    if args.list:
        return _list_xfiles()

    # Clear command cache for each run
    _clear_command_cache()

    # Ensure directories exist
    _ensure_xfiles_dirs()

    # Process each xfile
    all_resolved_files: list[Path] = []
    xfile_paths: list[Path] = []

    for xfile_name in args.xfiles:
        xfile_path = _find_xfile(xfile_name)
        if xfile_path is None:
            print(
                f"Error: xfile '{xfile_name}' not found in local or global directories",
                file=sys.stderr,
            )
            return 1

        xfile_paths.append(xfile_path)
        resolved_files = _process_xfile(xfile_path)
        all_resolved_files.extend(resolved_files)

    # Create rendered file if requested
    rendered_file: Path | None = None
    if args.render:
        output_path = (
            Path(args.output)
            if args.output
            else _generate_rendered_filepath(args.xfiles)
        )
        _create_rendered_file(xfile_paths, output_path)
        rendered_file = output_path

    # Output all files (rendered file first if it exists, then resolved files)
    cwd = Path.cwd()
    if rendered_file:
        output_path = _format_output_path(rendered_file, args.absolute, args.prefix_at, cwd)
        print(output_path)
    for file_path in all_resolved_files:
        output_path = _format_output_path(file_path, args.absolute, args.prefix_at, cwd)
        print(output_path)

    return 0


def _list_xfiles() -> int:
    """List available xfiles from both global and local directories."""
    local_dir = _get_local_xfiles_dir()
    global_dir = _get_global_xfiles_dir()

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


def _clear_command_cache() -> None:
    """Clear the command cache."""
    global _command_cache
    _command_cache = {}


def _execute_cached_command(cmd: str) -> tuple[str | None, bool]:
    """Execute a command with caching to avoid duplicate runs."""
    if cmd in _command_cache:
        return _command_cache[cmd]

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout
        success = result.returncode == 0
        _command_cache[cmd] = (output, success)
        return output, success
    except Exception:
        _command_cache[cmd] = (None, False)
        return None, False


def _get_global_xfiles_dir() -> Path:
    """Get the global xfiles directory path."""
    return Path.home() / ".local/share/nvim/codecompanion/user/xfiles"


def _get_local_xfiles_dir() -> Path:
    """Get the local xfiles directory path."""
    return Path.cwd() / "xfiles"


def _ensure_xfiles_dirs() -> None:
    """Ensure both global and local xfiles directories exist."""
    _get_global_xfiles_dir().mkdir(parents=True, exist_ok=True)
    _get_local_xfiles_dir().mkdir(parents=True, exist_ok=True)


def _find_xfile(name: str) -> Path | None:
    """Find an xfile by name, checking local directory first, then global."""
    # Remove .txt extension if provided
    if name.endswith(".txt"):
        name = name[:-4]

    local_path = _get_local_xfiles_dir() / f"{name}.txt"
    if local_path.exists():
        return local_path

    global_path = _get_global_xfiles_dir() / f"{name}.txt"
    if global_path.exists():
        return global_path

    return None


def _generate_rendered_filepath(xfile_names: list[str]) -> Path:
    """Generate a unique filename for the rendered xfile."""
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    xfile_part = "_".join(xfile_names)
    # Sanitize filename
    xfile_part = re.sub(r"[^\w_-]", "_", xfile_part)
    filename = f"xfile_rendered_{xfile_part}_{timestamp}.txt"

    xcmds_dir = Path.cwd() / "xcmds"
    xcmds_dir.mkdir(exist_ok=True)
    return xcmds_dir / filename


def _process_xfile(xfile_path: Path) -> list[Path]:
    """Process an xfile and return all resolved file paths."""
    content = xfile_path.read_text()
    lines = content.splitlines()

    all_resolved_files: list[Path] = []
    processed_xfiles: set[Path] = set()

    for line in lines:
        resolved_files = _resolve_target(line, processed_xfiles)
        all_resolved_files.extend(resolved_files)

    return all_resolved_files


def _resolve_target(
    target_line: str, processed_xfiles: set[Path] | None = None
) -> list[Path]:
    """Parse and resolve a target line to file paths."""
    if processed_xfiles is None:
        processed_xfiles = set()

    resolved_files: list[Path] = []
    trimmed = target_line.strip()

    # Skip empty lines and comments
    if not trimmed or trimmed.startswith("#"):
        return resolved_files

    # Handle x:reference
    xfile_match = re.match(r"^x:(.+)$", trimmed)
    if xfile_match:
        xfile_ref = xfile_match.group(1)
        xfile_path = _find_xfile(xfile_ref)

        if xfile_path is None:
            print(
                f"Warning: Referenced xfile not found: {xfile_ref}",
                file=sys.stderr,
            )
            return resolved_files

        # Prevent infinite recursion
        if xfile_path in processed_xfiles:
            print(
                f"Warning: Circular xfile reference detected: {xfile_ref}",
                file=sys.stderr,
            )
            return resolved_files

        # Mark this xfile as being processed
        processed_xfiles.add(xfile_path)

        # Read and process the referenced xfile
        content = xfile_path.read_text()
        lines = content.splitlines()
        for line in lines:
            ref_resolved = _resolve_target(line, processed_xfiles)
            resolved_files.extend(ref_resolved)

        # Unmark this xfile after processing
        processed_xfiles.discard(xfile_path)

        return resolved_files

    # Handle !command that outputs file paths
    bang_match = re.match(r"^!(.+)$", trimmed)
    if bang_match:
        bang_cmd = bang_match.group(1)
        output, success = _execute_cached_command(bang_cmd)

        if success and output and output.strip():
            lines = output.splitlines()
            for line in lines:
                file_path_str = line.strip()
                if file_path_str:
                    file_path = Path(file_path_str)
                    # Handle relative vs absolute paths
                    if not file_path.is_absolute():
                        file_path = Path.cwd() / file_path
                    if file_path.is_file():
                        resolved_files.append(file_path)

        return resolved_files

    # Handle [[filename]] command format
    shell_match = re.match(r"^\[\[(.+)\]\]\s+(.+)$", trimmed)
    if shell_match:
        shell_filename = shell_match.group(1)
        shell_cmd = shell_match.group(2)

        # Process command substitution in the filename
        processed_filename = _process_command_substitution(shell_filename)

        # Execute shell command
        output, success = _execute_cached_command(shell_cmd)
        if success and output and output.strip():
            # Use custom extension if provided, otherwise default to .txt
            if not re.search(r"\.\w+$", processed_filename):
                processed_filename = f"{processed_filename}.txt"

            xcmds_dir = Path.cwd() / "xcmds"
            xcmds_dir.mkdir(exist_ok=True)
            output_file = xcmds_dir / processed_filename

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with output_file.open("w") as f:
                f.write(f"# Generated from command: {shell_cmd}\n")
                f.write(f"# Timestamp: {timestamp}\n\n")
                f.write(output)

            resolved_files.append(output_file)

        return resolved_files

    # Check if it contains glob patterns FIRST
    if any(char in trimmed for char in ["*", "?", "[", "]"]):
        # It's a glob pattern - use glob relative to cwd
        matches = glob_module.glob(trimmed, recursive=True)
        for match in matches:
            match_path = Path(match)
            if match_path.is_file():
                resolved_files.append(match_path)
        return resolved_files

    # Handle regular files and directories
    expanded_path = Path(os.path.expanduser(trimmed))

    # Check if it's an absolute path or make it relative to cwd
    if not expanded_path.is_absolute():
        expanded_path = Path.cwd() / expanded_path

    if expanded_path.is_dir():
        # It's a directory - get all files recursively
        for file_path in expanded_path.rglob("*"):
            if file_path.is_file():
                resolved_files.append(file_path)
    elif expanded_path.is_file():
        # It's a regular file
        resolved_files.append(expanded_path)

    return resolved_files


def _process_command_substitution(filename: str) -> str:
    """Process command substitution in the filename (e.g., foo_$(echo bar))."""
    result = filename

    def _replace_cmd(match: re.Match[str]) -> str:
        cmd = match.group(1)
        output, success = _execute_cached_command(cmd)
        if success and output:
            return output.strip()
        return ""

    result = re.sub(r"\$\(([^)]+)\)", _replace_cmd, result)
    return result


def _create_rendered_file(xfile_paths: list[Path], output_path: Path) -> None:
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
        xfile_path = _find_xfile(xfile_ref)

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
        output, success = _execute_cached_command(bang_cmd)

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
                        relative_path = _make_relative_to_home(file_path)
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
        processed_filename = _process_command_substitution(shell_filename)

        # Use custom extension if provided, otherwise default to .txt
        if not re.search(r"\.\w+$", processed_filename):
            processed_filename = f"{processed_filename}.txt"

        xcmds_dir = Path.cwd() / "xcmds"
        output_file = xcmds_dir / processed_filename
        relative_path = _make_relative_to_home(output_file)

        # Execute shell command to check if it produces output
        output, success = _execute_cached_command(shell_cmd)
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
    if any(char in trimmed for char in ["*", "?", "[", "]"]):
        result = []
        result.append(f"#\n# GLOB PATTERN: {trimmed}")

        matches = glob_module.glob(trimmed, recursive=True)
        for match in matches:
            match_path = Path(match)
            if match_path.is_file():
                relative_path = _make_relative_to_home(match_path)
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
                relative_path = _make_relative_to_home(file_path)
                result.append(str(relative_path))
                count += 1

        if count == 0:
            result.append("# No readable files in directory")

        return "\n".join(result)
    elif expanded_path.is_file():
        relative_path = _make_relative_to_home(expanded_path)
        return str(relative_path)
    else:
        return f"# ERROR: File not found or not readable: {trimmed}"


def _make_relative_to_home(path: Path) -> Path:
    """Convert absolute path to be relative to home directory with ~ prefix."""
    try:
        return Path("~") / path.relative_to(Path.home())
    except ValueError:
        return path


def _format_output_path(path: Path, absolute: bool, prefix_at: bool, cwd: Path) -> str:
    """Format a path for output based on the absolute and prefix_at flags."""
    if absolute:
        path_str = str(path)
    else:
        # Default: relative to cwd
        try:
            path_str = str(path.relative_to(cwd))
        except ValueError:
            # Path is outside cwd, return absolute path
            path_str = str(path)

    if prefix_at:
        return f"@{path_str}"
    else:
        return path_str


if __name__ == "__main__":
    sys.exit(main())
