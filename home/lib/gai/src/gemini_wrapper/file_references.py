"""File reference processing for prompts."""

import os
import re
import subprocess
import sys

from rich_utils import (
    print_file_operation,
    print_status,
)


def process_file_references(prompt: str) -> str:
    """
    Process file paths prefixed with '@' in the prompt.

    For absolute paths:
    - Copy the file to bb/gai/context/ directory
    - Replace the path in the prompt with the relative path

    For relative paths: validate they exist and don't escape CWD

    This function extracts all file paths from the prompt that are prefixed
    with '@' and verifies that:
    1. Absolute paths exist and are copied to bb/gai/context/
    2. Relative paths do not start with '..' (to prevent escaping CWD)
    3. All files exist
    4. There are no duplicate file path references

    If any file starts with '..', does not exist, or is duplicated,
    it prints an error message and terminates the script.

    Args:
        prompt: The prompt text to process

    Returns:
        The modified prompt with absolute paths replaced by relative paths to bb/gai/context/

    Raises:
        SystemExit: If any referenced file starts with '..', does not exist, or is duplicated
    """
    import shutil
    from pathlib import Path

    # Pattern to match '@' followed by a file path
    # This captures paths like @/path/to/file.txt or @path/to/file
    # We look for @ followed by non-whitespace characters that look like file paths
    # Only match @ that is:
    #   - At the start of the string (^)
    #   - At the start of a line (after \n)
    #   - After a space or whitespace character
    # This prevents matching things like "foo@bar" or URLs with @ in them
    pattern = r"(?:^|(?<=\s))@((?:[^\s,;:()[\]{}\"'`])+)"

    # Find all matches (MULTILINE so ^ matches start of each line)
    matches = re.findall(pattern, prompt, re.MULTILINE)

    if not matches:
        return prompt  # No file references found

    # Collect absolute paths that need copying: list of (original_path, expanded_path)
    absolute_paths_to_copy: list[tuple[str, str]] = []
    parent_dir_paths: list[str] = []
    context_dir_paths: list[str] = []  # Paths in bb/gai/context/ (reserved)
    missing_files: list[str] = []
    seen_paths: dict[str, int] = {}  # Track file paths and their occurrence count

    for file_path in matches:
        # Clean up the path (remove trailing punctuation)
        file_path = file_path.rstrip(".,;:!?)")

        # Skip if it looks like a URL
        if file_path.startswith("http"):
            continue

        # Skip if it looks like a domain name (e.g., @google.com at start of line)
        # Domain names end with common TLDs and don't contain path separators
        common_tlds = (
            ".com",
            ".org",
            ".net",
            ".io",
            ".edu",
            ".gov",
            ".co",
            ".dev",
            ".app",
        )
        if "/" not in file_path and any(file_path.endswith(tld) for tld in common_tlds):
            continue

        # Track this file path for duplicate detection
        seen_paths[file_path] = seen_paths.get(file_path, 0) + 1

        # Expand tilde (~) to home directory
        expanded_path = os.path.expanduser(file_path)

        # Check if the file path is absolute (after tilde expansion)
        if os.path.isabs(expanded_path):
            # Validate existence using expanded path
            if not os.path.exists(expanded_path):
                if file_path not in missing_files:
                    missing_files.append(file_path)
            else:
                # Store tuple of (original_path, expanded_path) for later processing
                if not any(orig == file_path for orig, _ in absolute_paths_to_copy):
                    absolute_paths_to_copy.append((file_path, expanded_path))
            continue

        # Check if the file path starts with '..' (tries to escape CWD)
        if file_path.startswith(".."):
            if file_path not in parent_dir_paths:
                parent_dir_paths.append(file_path)
            continue

        # Check if the file path is in bb/gai/context/ (reserved directory)
        if file_path.startswith("bb/gai/context/") or file_path.startswith(
            "./bb/gai/context/"
        ):
            if file_path not in context_dir_paths:
                context_dir_paths.append(file_path)
            continue

        # Check if the file exists (relative path)
        if not os.path.exists(file_path) and file_path not in missing_files:
            missing_files.append(file_path)

    # Check for duplicates
    duplicate_paths = [path for path, count in seen_paths.items() if count > 1]

    # Validate issues
    if parent_dir_paths:
        print(
            "\n❌ ERROR: The following file(s) use parent directory paths ('..' prefix) in '@' references:"
        )
        for file_path in parent_dir_paths:
            print(f"  - @{file_path}")
        print("\n⚠️ All '@' file references MUST NOT start with '..' to escape the CWD.")
        print(
            "⚠️ This ensures agents can only access files within the project directory."
        )
        print("⚠️ File validation failed. Terminating workflow to prevent errors.\n")
        sys.exit(1)

    if context_dir_paths:
        print(
            "\n❌ ERROR: The following file(s) reference the reserved 'bb/gai/context/' directory:"
        )
        for file_path in context_dir_paths:
            print(f"  - @{file_path}")
        print("\n⚠️ The 'bb/gai/context/' directory is reserved for system use.")
        print("⚠️ This directory is cleared and recreated on each agent invocation.")
        print("⚠️ Please reference files from other locations.\n")
        sys.exit(1)

    if missing_files:
        print(
            "\n❌ ERROR: The following file(s) referenced in the prompt do not exist:"
        )
        for file_path in missing_files:
            print(f"  - @{file_path}")
        print("\n⚠️ File validation failed. Terminating workflow to prevent errors.\n")
        sys.exit(1)

    if duplicate_paths:
        print(
            "\n❌ ERROR: The following file(s) have duplicate '@' references in the prompt:"
        )
        for file_path in duplicate_paths:
            count = seen_paths[file_path]
            print(f"  - @{file_path} (appears {count} times)")
        print("\n⚠️ Each file should be referenced with '@' only ONCE in the prompt.")
        print("⚠️ Duplicate references waste tokens and can confuse the AI agent.")
        print("⚠️ File validation failed. Terminating workflow to prevent errors.\n")
        sys.exit(1)

    # If there are no absolute paths to copy, just return the original prompt
    if not absolute_paths_to_copy:
        return prompt

    # Notify user that we're processing absolute file paths
    file_count = len(absolute_paths_to_copy)
    file_word = "file" if file_count == 1 else "files"
    print_status(
        f"Processing {file_count} absolute {file_word} - copying to bb/gai/context/",
        "info",
    )

    # Prepare process-specific context directory to avoid race conditions
    # when multiple gai processes run in parallel (e.g., summarize-hook workflows)
    base_context_dir = "bb/gai/context"
    pid = os.getpid()
    bb_gai_context_dir = f"{base_context_dir}/{pid}"

    # Clean up stale context directories from dead processes
    if os.path.exists(base_context_dir):
        for subdir in os.listdir(base_context_dir):
            subdir_path = os.path.join(base_context_dir, subdir)
            if os.path.isdir(subdir_path):
                try:
                    old_pid = int(subdir)
                    # Signal 0 doesn't kill, just checks if process exists
                    try:
                        os.kill(old_pid, 0)
                    except OSError:
                        # Process doesn't exist, safe to clean up
                        shutil.rmtree(subdir_path)
                except ValueError:
                    pass  # Not a PID-named directory, leave it

    # Clear and recreate this process's context directory
    if os.path.exists(bb_gai_context_dir):
        shutil.rmtree(bb_gai_context_dir)
    Path(bb_gai_context_dir).mkdir(parents=True, exist_ok=True)

    # Copy absolute paths and track replacements
    replacements: dict[str, str] = {}
    basename_counts: dict[str, int] = {}

    for original_path, expanded_path in absolute_paths_to_copy:
        # Generate unique filename in bb/gai/context/
        basename = os.path.basename(expanded_path)
        base_name, ext = os.path.splitext(basename)

        # Handle filename conflicts with counter
        count = basename_counts.get(basename, 0)
        basename_counts[basename] = count + 1

        if count == 0:
            dest_filename = basename
        else:
            dest_filename = f"{base_name}_{count}{ext}"

        dest_path = os.path.join(bb_gai_context_dir, dest_filename)

        # Copy the file using expanded path
        try:
            shutil.copy2(expanded_path, dest_path)
            # Track replacement using original path (for prompt substitution)
            replacements[original_path] = dest_path
            # Notify user of successful copy
            print_file_operation(f"Copied for Gemini: {basename}", dest_path, True)
        except Exception as e:
            print_status(f"Failed to copy {expanded_path} to {dest_path}: {e}", "error")

    # Apply replacements to prompt
    modified_prompt = prompt
    for old_path, new_path in replacements.items():
        modified_prompt = modified_prompt.replace(f"@{old_path}", f"@{new_path}")

    # Notify user that prompt was modified
    replacement_count = len(replacements)
    if replacement_count > 0:
        path_word = "path" if replacement_count == 1 else "paths"
        print_status(
            f"Prompt modified: {replacement_count} absolute {path_word} replaced with relative paths",
            "success",
        )

    return modified_prompt


def process_xfile_references(prompt: str) -> str:
    """
    Process x:: references in the prompt by piping through xfile command.

    If the prompt contains any "x::" substring, it pipes the entire prompt
    through the xfile command which will replace x::name patterns with
    formatted file lists.

    Args:
        prompt: The prompt text to process

    Returns:
        The transformed prompt with x::name patterns replaced by file lists
    """
    # Check if the prompt contains x:: pattern
    if "x::" not in prompt:
        return prompt  # No xfile references found

    try:
        # Run xfile command with prompt as stdin
        process = subprocess.Popen(
            ["xfile"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Send prompt to xfile and get the transformed output
        stdout, stderr = process.communicate(input=prompt)

        if process.returncode != 0:
            print_status(
                f"xfile command failed (exit code {process.returncode})",
                "error",
            )
            if stderr:
                print(f"\n{stderr.strip()}\n", file=sys.stderr)
            sys.exit(1)

        return stdout

    except FileNotFoundError:
        print_status(
            "xfile command not found. Install xfile or add it to PATH.",
            "error",
        )
        sys.exit(1)
    except Exception as e:
        print_status(f"Error processing xfile references: {e}", "error")
        sys.exit(1)
