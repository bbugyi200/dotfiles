"""File reference processing for prompts."""

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from rich_utils import (
    print_file_operation,
    print_status,
)

# Pattern to match '@' followed by a file path
# This captures paths like @/path/to/file.txt or @path/to/file
# We look for @ followed by non-whitespace characters that look like file paths
# Only match @ that is:
#   - At the start of the string (^)
#   - At the start of a line (after \n)
#   - After a space or whitespace character
# This prevents matching things like "foo@bar" or URLs with @ in them
_FILE_REF_PATTERN = r"(?:^|(?<=\s))@((?:[^\s,;:()[\]{}\"'`])+)"

# Common TLDs used to skip domain-like patterns
_COMMON_TLDS = (
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


@dataclass
class _ParsedFileRefs:
    """Holds categorized file references from parsing."""

    absolute_paths: list[tuple[str, str]] = field(default_factory=list)
    parent_dir_paths: list[str] = field(default_factory=list)
    context_dir_paths: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    seen_paths: dict[str, int] = field(default_factory=dict)

    @property
    def duplicate_paths(self) -> list[str]:
        """Return paths that appear more than once."""
        return [path for path, count in self.seen_paths.items() if count > 1]


def _parse_file_refs(prompt: str) -> _ParsedFileRefs:
    """
    Parse @file references in the prompt and categorize them.

    Args:
        prompt: The prompt text to parse

    Returns:
        Categorized file references
    """
    result = _ParsedFileRefs()

    # Find all matches (MULTILINE so ^ matches start of each line)
    matches = re.findall(_FILE_REF_PATTERN, prompt, re.MULTILINE)

    if not matches:
        return result

    for file_path in matches:
        # Clean up the path (remove trailing punctuation)
        file_path = file_path.rstrip(".,;:!?)")

        # Skip if it looks like a URL
        if file_path.startswith("http"):
            continue

        # Skip if it looks like a domain name (e.g., @google.com at start of line)
        # Domain names end with common TLDs and don't contain path separators
        if "/" not in file_path and any(
            file_path.endswith(tld) for tld in _COMMON_TLDS
        ):
            continue

        # Track this file path for duplicate detection
        result.seen_paths[file_path] = result.seen_paths.get(file_path, 0) + 1

        # Expand tilde (~) to home directory
        expanded_path = os.path.expanduser(file_path)

        # Check if the file path is absolute (after tilde expansion)
        if os.path.isabs(expanded_path):
            # Validate existence using expanded path
            if not os.path.exists(expanded_path):
                if file_path not in result.missing_files:
                    result.missing_files.append(file_path)
            else:
                # Store tuple of (original_path, expanded_path) for later processing
                if not any(orig == file_path for orig, _ in result.absolute_paths):
                    result.absolute_paths.append((file_path, expanded_path))
            continue

        # Check if the file path starts with '..' (tries to escape CWD)
        if file_path.startswith(".."):
            if file_path not in result.parent_dir_paths:
                result.parent_dir_paths.append(file_path)
            continue

        # Check if the file path is in bb/gai/context/ (reserved directory)
        if file_path.startswith("bb/gai/context/") or file_path.startswith(
            "./bb/gai/context/"
        ):
            if file_path not in result.context_dir_paths:
                result.context_dir_paths.append(file_path)
            continue

        # Check if the file exists (relative path)
        if not os.path.exists(file_path) and file_path not in result.missing_files:
            result.missing_files.append(file_path)

    return result


def _print_validation_errors(parsed: _ParsedFileRefs, check_context_dir: bool) -> bool:
    """
    Print validation errors and return True if any errors were found.

    Args:
        parsed: The parsed file references
        check_context_dir: Whether to check for reserved context directory usage

    Returns:
        True if validation errors were found, False otherwise
    """
    has_errors = False

    if parsed.parent_dir_paths:
        has_errors = True
        print(
            "\n❌ ERROR: The following file(s) use parent directory paths ('..' prefix) in '@' references:"
        )
        for file_path in parsed.parent_dir_paths:
            print(f"  - @{file_path}")
        print("\n⚠️ All '@' file references MUST NOT start with '..' to escape the CWD.")
        print(
            "⚠️ This ensures agents can only access files within the project directory."
        )
        print("⚠️ File validation failed. Terminating workflow to prevent errors.\n")

    if check_context_dir and parsed.context_dir_paths:
        has_errors = True
        print(
            "\n❌ ERROR: The following file(s) reference the reserved 'bb/gai/context/' directory:"
        )
        for file_path in parsed.context_dir_paths:
            print(f"  - @{file_path}")
        print("\n⚠️ The 'bb/gai/context/' directory is reserved for system use.")
        print("⚠️ This directory is cleared and recreated on each agent invocation.")
        print("⚠️ Please reference files from other locations.\n")

    if parsed.missing_files:
        has_errors = True
        print(
            "\n❌ ERROR: The following file(s) referenced in the prompt do not exist:"
        )
        for file_path in parsed.missing_files:
            print(f"  - @{file_path}")
        print("\n⚠️ File validation failed. Terminating workflow to prevent errors.\n")

    if parsed.duplicate_paths:
        has_errors = True
        print(
            "\n❌ ERROR: The following file(s) have duplicate '@' references in the prompt:"
        )
        for file_path in parsed.duplicate_paths:
            count = parsed.seen_paths[file_path]
            print(f"  - @{file_path} (appears {count} times)")
        print("\n⚠️ Each file should be referenced with '@' only ONCE in the prompt.")
        print("⚠️ Duplicate references waste tokens and can confuse the AI agent.")
        print("⚠️ File validation failed. Terminating workflow to prevent errors.\n")

    return has_errors


def validate_file_references(prompt: str) -> None:
    """
    Validate @file references in the prompt without modifying it.

    Checks that:
    1. All referenced files exist
    2. No paths use '..' to escape the current working directory
    3. No duplicate file references

    Note: Unlike process_file_references(), this does NOT check for reserved
    context directory usage or copy any files.

    Args:
        prompt: The prompt text to validate

    Raises:
        SystemExit: If any validation error is found
    """
    parsed = _parse_file_refs(prompt)
    if _print_validation_errors(parsed, check_context_dir=False):
        sys.exit(1)


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

    parsed = _parse_file_refs(prompt)

    # Validate and exit on errors (including context_dir check)
    if _print_validation_errors(parsed, check_context_dir=True):
        sys.exit(1)

    # If there are no absolute paths to copy, just return the original prompt
    if not parsed.absolute_paths:
        return prompt

    # Notify user that we're processing absolute file paths
    file_count = len(parsed.absolute_paths)
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

    for original_path, expanded_path in parsed.absolute_paths:
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


# --- xcmd processing (#(filename: command) syntax) ---

# Pattern to match #(filename: command)
# Captures: group(1) = filename (before colon), group(2) = command (after colon)
_XCMD_PATTERN = r"#\(([^:]+):\s*([^)]+)\)"

# Command cache for xcmd processing to avoid duplicate executions
_xcmd_cache: dict[str, tuple[str | None, bool]] = {}


def _execute_xcmd_cached(cmd: str) -> tuple[str | None, bool]:
    """
    Execute a command with caching to avoid duplicate runs.

    Args:
        cmd: The shell command to execute

    Returns:
        Tuple of (output, success) where output is stdout and success is True if exit code was 0
    """
    if cmd in _xcmd_cache:
        return _xcmd_cache[cmd]

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
        _xcmd_cache[cmd] = (output, success)
        return output, success
    except Exception:
        _xcmd_cache[cmd] = (None, False)
        return None, False


def _process_xcmd_substitution(filename: str) -> str:
    """
    Process command substitution $(cmd) in filename.

    Args:
        filename: The filename that may contain $(cmd) patterns

    Returns:
        The filename with command substitutions expanded
    """

    def _replace_cmd(match: re.Match[str]) -> str:
        cmd = match.group(1)
        output, success = _execute_xcmd_cached(cmd)
        if success and output:
            return output.strip()
        return ""

    return re.sub(r"\$\(([^)]+)\)", _replace_cmd, filename)


def process_xcmd_references(prompt: str) -> str:
    """
    Process #(filename: command) references in the prompt.

    Executes shell commands and stores their output in bb/gai/xcmds/,
    replacing the pattern with @-prefixed file references.

    Args:
        prompt: The prompt text to process

    Returns:
        The transformed prompt with #(filename: cmd) replaced by @file references
    """
    # Quick check before regex matching
    if "#(" not in prompt:
        return prompt

    # Find all matches
    matches = list(re.finditer(_XCMD_PATTERN, prompt))
    if not matches:
        return prompt

    # Process from last to first to preserve string positions
    for match in reversed(matches):
        filename = match.group(1).strip()
        cmd = match.group(2).strip()

        # Process command substitution in filename (e.g., $(date +%Y%m%d))
        processed_filename = _process_xcmd_substitution(filename)

        # Execute command (cached)
        output, success = _execute_xcmd_cached(cmd)

        if not success or not output or not output.strip():
            # Command failed or empty output - remove pattern from prompt
            prompt = prompt[: match.start()] + prompt[match.end() :]
            continue

        # Generate timestamp suffix (format: -YYmmdd_HHMMSS)
        timestamp_suffix = datetime.now().strftime("-%y%m%d_%H%M%S")

        # Add timestamp suffix before extension
        if ext_match := re.search(r"\.\w+$", processed_filename):
            # Insert before existing extension (e.g., output.json → output-240427_153045.json)
            ext = ext_match.group()
            base = processed_filename[: ext_match.start()]
            processed_filename = f"{base}{timestamp_suffix}{ext}"
        else:
            # No extension - add suffix then .txt (e.g., foo → foo-240427_153045.txt)
            processed_filename = f"{processed_filename}{timestamp_suffix}.txt"

        # Create output directory
        xcmds_dir = Path("bb/gai/xcmds")
        xcmds_dir.mkdir(parents=True, exist_ok=True)

        # Write output file with metadata header
        output_file = xcmds_dir / processed_filename
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with output_file.open("w") as f:
            f.write(f"# Generated from command: {cmd}\n")
            f.write(f"# Timestamp: {timestamp}\n\n")
            f.write(output)

        # Replace pattern with @file reference
        replacement = f"@{output_file}"
        prompt = prompt[: match.start()] + replacement + prompt[match.end() :]

    return prompt


# --- Command substitution processing ($(cmd) syntax) ---


def _find_matching_paren(text: str, start: int) -> int:
    """Find the index of the closing ) that matches the opening paren.

    Uses balanced parentheses counting to handle nested parens like $(echo $(date)).

    Args:
        text: The text to search
        start: Index of the first character AFTER the opening paren

    Returns:
        Index of the matching closing paren, or -1 if not found
    """
    depth = 1
    i = start
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _find_command_substitutions(text: str) -> list[tuple[int, int, str]]:
    """Find all $(...) command substitutions in text.

    Handles:
    - Nested parentheses: $(echo $(date))
    - Escaped patterns: \\$( is NOT substituted

    Args:
        text: The text to scan

    Returns:
        List of tuples (start_index, end_index, command) sorted by position.
        start_index is the index of '$', end_index is the index after ')'.
    """
    substitutions: list[tuple[int, int, str]] = []
    i = 0

    while i < len(text) - 1:
        # Look for $(
        if text[i] == "$" and text[i + 1] == "(":
            # Check if escaped by backslash
            if i > 0 and text[i - 1] == "\\":
                i += 1
                continue

            # Find matching closing paren
            cmd_start = i + 2  # After $(
            close_idx = _find_matching_paren(text, cmd_start)

            if close_idx != -1:
                command = text[cmd_start:close_idx]
                substitutions.append((i, close_idx + 1, command))
                i = close_idx + 1
            else:
                # No matching paren - skip this $
                i += 1
        else:
            i += 1

    return substitutions


def process_command_substitution(prompt: str) -> str:
    """Process $(cmd) command substitutions in the prompt.

    Executes shell commands and replaces $(cmd) with their output.

    Features:
    - Handles nested parentheses: $(echo $(date)) works correctly
    - Supports escape: \\$( is replaced with literal $(
    - Commands are executed via shell (sh -c)
    - Failed commands or empty output result in empty string replacement

    Args:
        prompt: The prompt text to process

    Returns:
        The prompt with all $(cmd) patterns replaced with command output
    """
    # Quick check - if no $( in prompt, nothing to do
    if "$(" not in prompt:
        return prompt

    # Handle escaped \$( first - replace with placeholder, restore later
    # Use a placeholder unlikely to appear in real text
    escape_placeholder = "\x00ESCAPED_DOLLAR_PAREN\x00"
    prompt = prompt.replace("\\$(", escape_placeholder)

    # Find all substitutions (process from end to preserve indices)
    substitutions = _find_command_substitutions(prompt)

    # Process from end to start to preserve string positions
    for start, end, command in reversed(substitutions):
        # Execute command using the cached executor
        output, success = _execute_xcmd_cached(command)

        if success and output:
            replacement = output.strip()
        else:
            replacement = ""

        prompt = prompt[:start] + replacement + prompt[end:]

    # Restore escaped patterns as literal $(
    prompt = prompt.replace(escape_placeholder, "$(")

    return prompt
