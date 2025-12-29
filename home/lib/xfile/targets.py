"""Target resolution for xfile processing."""

from __future__ import annotations

import glob as glob_module
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from utils import (  # type: ignore[import-not-found]
    execute_cached_command,
    expand_braces,
    find_xfile,
    process_command_substitution,
)


def process_xfile(xfile_path: Path) -> list[Path]:
    """Process an xfile and return all resolved file paths."""
    content = xfile_path.read_text()
    lines = content.splitlines()

    all_resolved_files: list[Path] = []
    processed_xfiles: set[Path] = set()

    for line in lines:
        resolved_files = resolve_target(line, processed_xfiles)
        all_resolved_files.extend(resolved_files)

    return all_resolved_files


def resolve_target(
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
        xfile_path = find_xfile(xfile_ref)

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
            ref_resolved = resolve_target(line, processed_xfiles)
            resolved_files.extend(ref_resolved)

        # Unmark this xfile after processing
        processed_xfiles.discard(xfile_path)

        return resolved_files

    # Handle !command that outputs file paths
    bang_match = re.match(r"^!(.+)$", trimmed)
    if bang_match:
        bang_cmd = bang_match.group(1)
        output, success = execute_cached_command(bang_cmd)

        if success and output and output.strip():
            lines = output.splitlines()
            for line in lines:
                # Split by whitespace to handle multiple files on one line
                file_paths_in_line = line.split()
                for file_path_str in file_paths_in_line:
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
        processed_filename = process_command_substitution(shell_filename)

        # Execute shell command
        output, success = execute_cached_command(shell_cmd)
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
    if any(char in trimmed for char in ["*", "?", "[", "]", "{"]):
        # It's a glob pattern - expand ~ and braces, then use glob
        expanded_pattern = os.path.expanduser(trimmed)
        brace_expanded = expand_braces(expanded_pattern)
        for pattern in brace_expanded:
            matches = glob_module.glob(pattern, recursive=True)
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
