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
import sys
from pathlib import Path

from rendering import (  # type: ignore[import-not-found]
    create_rendered_file,
    generate_rendered_filepath,
)
from targets import process_xfile  # type: ignore[import-not-found]
from utils import (  # type: ignore[import-not-found]
    clear_command_cache,
    ensure_xfiles_dirs,
    find_xfile,
    format_output_path,
)
from xfile_refs import (  # type: ignore[import-not-found]
    list_xfiles,
    process_stdin_with_xfile_refs,
)


def main(argv: list[str] | None = None) -> int:
    """Main entry point for xfile command."""
    parser = argparse.ArgumentParser(
        description="Process xfile targets and resolve them to actual files"
    )
    parser.add_argument(
        "xfiles",
        nargs="*",
        help="Names of xfiles to process (without .txt extension)",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List available xfiles",
    )
    parser.add_argument(
        "-s",
        "--create-summary",
        action="store_true",
        help="Create rendered summary file",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output file for rendered summary (default: auto-generated in xcmds/)",
    )
    parser.add_argument(
        "-a",
        "--absolute",
        action="store_true",
        help="Output absolute file paths (default: relative to current directory)",
    )

    args = parser.parse_args(argv)

    if args.list:
        return list_xfiles()

    if not args.xfiles:
        # When no xfiles provided, process STDIN for x::pattern references
        return process_stdin_with_xfile_refs(args.absolute)

    # Clear command cache for each run
    clear_command_cache()

    # Ensure directories exist
    ensure_xfiles_dirs()

    # Process each xfile
    all_resolved_files: list[Path] = []
    xfile_paths: list[Path] = []

    for xfile_name in args.xfiles:
        xfile_path = find_xfile(xfile_name)
        if xfile_path is None:
            print(
                f"Error: xfile '{xfile_name}' not found in local or global directories",
                file=sys.stderr,
            )
            return 1

        xfile_paths.append(xfile_path)
        resolved_files = process_xfile(xfile_path)
        all_resolved_files.extend(resolved_files)

    # Create rendered file if requested
    rendered_file: Path | None = None
    if args.create_summary:
        output_path = (
            Path(args.output)
            if args.output
            else generate_rendered_filepath(args.xfiles)
        )
        create_rendered_file(xfile_paths, output_path)
        rendered_file = output_path

    # Output all files (rendered file first if it exists, then resolved files)
    cwd = Path.cwd()
    all_output_files = []
    if rendered_file:
        all_output_files.append(rendered_file)
    all_output_files.extend(all_resolved_files)

    # Regular output
    for file_path in all_output_files:
        formatted_path = format_output_path(file_path, args.absolute, cwd)
        print(formatted_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
