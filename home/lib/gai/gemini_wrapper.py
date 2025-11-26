import os
import re
import select
import subprocess
import sys
from datetime import datetime
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import (
    gemini_timer,
    print_decision_counts,
    print_file_operation,
    print_prompt_and_response,
    print_status,
)
from shared_utils import run_bam_command


def _get_gai_log_file(artifacts_dir: str) -> str:
    """Get the path to the workflow-specific gai.md log file."""
    return os.path.join(artifacts_dir, "gai.md")


def _log_prompt_and_response(
    prompt: str,
    response: str,
    artifacts_dir: str,
    agent_type: str = "agent",
    iteration: int = None,
    workflow_tag: str = None,
) -> None:
    """
    Log a prompt and response to the workflow-specific gai.md file.

    Args:
        prompt: The prompt sent to the AI
        response: The response received from the AI
        artifacts_dir: Directory where the gai.md file should be stored
        agent_type: Type of agent (e.g., "editor", "planner", "research", "verification")
        iteration: Iteration number if applicable
        workflow_tag: Workflow tag if available
    """
    try:
        log_file = _get_gai_log_file(artifacts_dir)
        eastern = ZoneInfo("America/New_York")
        timestamp = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S EST")

        # Create header for this entry
        header_parts = [agent_type]
        if iteration is not None:
            header_parts.append(f"iteration {iteration}")
        if workflow_tag:
            header_parts.append(f"tag {workflow_tag}")

        header = " - ".join(header_parts)

        # Format the log entry
        log_entry = f"""
## {timestamp} - {header}

### PROMPT:
```
{prompt}
```

### RESPONSE:
```
{response}
```

---

"""

        # Append to the log file
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)

    except Exception as e:
        print(f"Warning: Failed to log prompt and response to gai.md: {e}")


def _stream_process_output(
    process: subprocess.Popen, suppress_output: bool = False
) -> tuple[str, str, int]:
    """Stream stdout and stderr from a process in real-time.

    Args:
        process: The subprocess.Popen process to stream from
        suppress_output: If True, don't print output to console

    Returns:
        Tuple of (stdout_content, stderr_content, return_code)
    """
    stdout_lines = []
    stderr_lines = []

    # Set stdout and stderr to non-blocking mode
    if process.stdout:
        os.set_blocking(process.stdout.fileno(), False)
    if process.stderr:
        os.set_blocking(process.stderr.fileno(), False)

    while True:
        # Use select to wait for data on stdout or stderr
        readable = []
        if process.stdout:
            readable.append(process.stdout)
        if process.stderr:
            readable.append(process.stderr)

        if not readable:
            break

        ready, _, _ = select.select(readable, [], [], 0.1)

        # Read from stdout
        if process.stdout and process.stdout in ready:
            line = process.stdout.readline()
            if line:
                stdout_lines.append(line)
                if not suppress_output:
                    print(line, end="", flush=True)

        # Read from stderr
        if process.stderr and process.stderr in ready:
            line = process.stderr.readline()
            if line:
                stderr_lines.append(line)
                if not suppress_output:
                    print(line, end="", file=sys.stderr, flush=True)

        # Check if process has finished
        if process.poll() is not None:
            # Read any remaining output
            if process.stdout:
                for line in process.stdout:
                    stdout_lines.append(line)
                    if not suppress_output:
                        print(line, end="", flush=True)
            if process.stderr:
                for line in process.stderr:
                    stderr_lines.append(line)
                    if not suppress_output:
                        print(line, end="", file=sys.stderr, flush=True)
            break

    return_code = process.wait()
    stdout_content = "".join(stdout_lines)
    stderr_content = "".join(stderr_lines)

    return stdout_content, stderr_content, return_code


def _process_file_references(prompt: str) -> str:
    """
    Process file paths prefixed with '@' in the prompt.

    For absolute paths:
    - Copy the file to bb/gai/ directory
    - Replace the path in the prompt with the relative path

    For relative paths: validate they exist and don't escape CWD

    This function extracts all file paths from the prompt that are prefixed
    with '@' and verifies that:
    1. Absolute paths exist and are copied to bb/gai/
    2. Relative paths do not start with '..' (to prevent escaping CWD)
    3. All files exist
    4. There are no duplicate file path references

    If any file starts with '..', does not exist, or is duplicated,
    it prints an error message and terminates the script.

    Args:
        prompt: The prompt text to process

    Returns:
        The modified prompt with absolute paths replaced by relative paths to bb/gai/

    Raises:
        SystemExit: If any referenced file starts with '..', does not exist, or is duplicated
    """
    import shutil
    from pathlib import Path

    # Pattern to match '@' followed by a file path
    # This captures paths like @/path/to/file.txt or @path/to/file
    # We look for @ followed by non-whitespace characters that look like file paths
    # Use negative lookbehind to skip @ that's part of an email address
    # (i.e., preceded by email-like characters: alphanumeric, ., _, +, -)
    pattern = r"(?<![a-zA-Z0-9._+-])@((?:[^\s,;:()[\]{}\"'`])+)"

    # Find all matches
    matches = re.findall(pattern, prompt)

    if not matches:
        return prompt  # No file references found

    # Collect absolute paths that need copying
    absolute_paths_to_copy = []
    parent_dir_paths = []
    missing_files = []
    seen_paths: dict[str, int] = {}  # Track file paths and their occurrence count

    for file_path in matches:
        # Clean up the path (remove trailing punctuation)
        file_path = file_path.rstrip(".,;:!?)")

        # Skip if it looks like an email address, URL, or domain name
        if "@" in file_path or file_path.startswith("http"):
            continue

        # Skip if it looks like a domain name (e.g., google.com, github.io)
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

        # Check if the file path is absolute
        if os.path.isabs(file_path):
            # Validate existence
            if not os.path.exists(file_path):
                if file_path not in missing_files:
                    missing_files.append(file_path)
            else:
                if file_path not in absolute_paths_to_copy:
                    absolute_paths_to_copy.append(file_path)
            continue

        # Check if the file path starts with '..' (tries to escape CWD)
        if file_path.startswith(".."):
            if file_path not in parent_dir_paths:
                parent_dir_paths.append(file_path)
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
        f"Processing {file_count} absolute {file_word} - copying to bb/gai/", "info"
    )

    # Prepare bb/gai/ directory (clear and recreate)
    bb_gai_dir = "bb/gai"
    if os.path.exists(bb_gai_dir):
        shutil.rmtree(bb_gai_dir)
    Path(bb_gai_dir).mkdir(parents=True, exist_ok=True)

    # Copy absolute paths and track replacements
    replacements: dict[str, str] = {}
    basename_counts: dict[str, int] = {}

    for file_path in absolute_paths_to_copy:
        # Generate unique filename in bb/gai/
        basename = os.path.basename(file_path)
        base_name, ext = os.path.splitext(basename)

        # Handle filename conflicts with counter
        count = basename_counts.get(basename, 0)
        basename_counts[basename] = count + 1

        if count == 0:
            dest_filename = basename
        else:
            dest_filename = f"{base_name}_{count}{ext}"

        dest_path = os.path.join(bb_gai_dir, dest_filename)

        # Copy the file
        try:
            shutil.copy2(file_path, dest_path)
            # Track replacement
            replacements[file_path] = dest_path
            # Notify user of successful copy
            print_file_operation(f"Copied for Gemini: {basename}", dest_path, True)
        except Exception as e:
            print_status(f"Failed to copy {file_path} to {dest_path}: {e}", "error")

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


def _process_xfile_references(prompt: str) -> str:
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
                f"Warning: xfile command failed (exit code {process.returncode}): {stderr}",
                "error",
            )
            return prompt  # Return original prompt on error

        return stdout

    except FileNotFoundError:
        print_status(
            "Warning: xfile command not found. Install xfile or add it to PATH.",
            "error",
        )
        return prompt  # Return original prompt if xfile not found
    except Exception as e:
        print_status(f"Warning: Error processing xfile references: {e}", "error")
        return prompt  # Return original prompt on error


class GeminiCommandWrapper:
    def __init__(self, model_size: Literal["little", "big"] = "little") -> None:
        self.decision_counts: dict[str, Any] | None = None
        self.agent_type: str = "agent"
        self.iteration: int | None = None
        self.workflow_tag: str | None = None
        self.artifacts_dir: str | None = None
        self.suppress_output: bool = (
            False  # Flag to suppress immediate prompt/response output
        )
        # Check for global override first, then use constructor arg
        override = os.environ.get("GAI_MODEL_SIZE_OVERRIDE")
        self.model_size: Literal["little", "big"] = (
            cast(Literal["little", "big"], override) if override else model_size
        )

    def set_decision_counts(self, decision_counts: dict) -> None:
        """Set the decision counts for display after prompts."""
        self.decision_counts = decision_counts

    def set_logging_context(
        self,
        agent_type: str = "agent",
        iteration: int | None = None,
        workflow_tag: str | None = None,
        artifacts_dir: str | None = None,
        suppress_output: bool = False,
    ) -> None:
        """Set the context for logging prompts and responses."""
        self.agent_type = agent_type
        self.iteration = iteration
        self.workflow_tag = workflow_tag
        self.artifacts_dir = artifacts_dir
        self.suppress_output = suppress_output

    def _display_decision_counts(self) -> None:
        """Display the planning agent decision counts."""
        if self.decision_counts is not None:
            print_decision_counts(self.decision_counts)

    def invoke(self, messages: list[HumanMessage | AIMessage]) -> AIMessage:
        query: str = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                content = msg.content
                # Ensure content is a string (should always be the case for our use)
                if isinstance(content, str):
                    query = content
                else:
                    # Handle unexpected list/dict content by converting to string
                    query = str(content)
                break

        if not query:
            return AIMessage(content="No query found in messages")

        # Process xfile references in the prompt (replace x::name patterns with file lists)
        query = _process_xfile_references(query)

        # Process file references in the prompt (copy absolute paths to bb/gai/ and update prompt)
        query = _process_file_references(query)

        # Build agent type with model size suffix
        model_size_label = "BIG" if self.model_size == "big" else "LITTLE"
        agent_type_with_size = f"{self.agent_type} [{model_size_label}]"

        # Display decision counts before the prompt if available (only if not suppressed)
        if not self.suppress_output:
            self._display_decision_counts()

        # Print prompt BEFORE execution for non-research agents (only if not suppressed)
        if not self.suppress_output:
            print_prompt_and_response(
                prompt=query,
                response="",  # Empty response since we haven't executed yet
                agent_type=agent_type_with_size,
                iteration=self.iteration,
                show_prompt=True,
                show_response=False,  # Only show prompt, not response
            )

        try:
            # Build base command arguments
            base_args = [
                "/google/bin/releases/gemini-cli/tools/gemini",
                "--yolo",
            ]

            # Parse additional args from environment variable if set
            if self.model_size == "big":
                extra_args_env = os.environ.get("GAI_BIG_GEMINI_ARGS")
            else:
                extra_args_env = os.environ.get("GAI_LITTLE_GEMINI_ARGS")

            if extra_args_env:
                # Split the environment variable on whitespace to get individual args
                for arg in extra_args_env.split():
                    base_args.append(arg)

            # Start the process and stream output in real-time with timer
            # Use gemini_timer context manager if output is not suppressed
            timer_context = (
                gemini_timer("Waiting for Gemini") if not self.suppress_output else None
            )

            if timer_context:
                with timer_context:
                    process = subprocess.Popen(
                        base_args,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )

                    # Write query to stdin
                    if process.stdin:
                        process.stdin.write(query)
                        process.stdin.close()

                    # Stream output in real-time
                    response_content, stderr_content, return_code = (
                        _stream_process_output(
                            process, suppress_output=self.suppress_output
                        )
                    )

                    # Add newline to separate agent output from timer
                    print()
            else:
                process = subprocess.Popen(
                    base_args,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                # Write query to stdin
                if process.stdin:
                    process.stdin.write(query)
                    process.stdin.close()

                # Stream output in real-time
                response_content, stderr_content, return_code = _stream_process_output(
                    process, suppress_output=self.suppress_output
                )

            # Check if process failed
            if return_code != 0:
                error_content = (
                    f"Error running gemini command (exit code {return_code})"
                )
                if stderr_content:
                    error_content += f": {stderr_content.strip()}"
                raise subprocess.CalledProcessError(
                    return_code,
                    base_args,
                    output=response_content,
                    stderr=stderr_content,
                )

            response_content = response_content.strip()

            # Play audio notification for agent reply (only if not suppressed)
            if not self.suppress_output:
                run_bam_command("Agent reply received", delay=0.2)

            # Log the prompt and response to gai.md
            if self.artifacts_dir:
                _log_prompt_and_response(
                    prompt=query,
                    response=response_content,
                    artifacts_dir=self.artifacts_dir,
                    agent_type=self.agent_type,
                    iteration=self.iteration,
                    workflow_tag=self.workflow_tag,
                )

            return AIMessage(content=response_content)
        except subprocess.CalledProcessError as e:
            error_content = f"Error running gemini command: {e.stderr}"

            # Print error using Rich formatting (only if not suppressed)
            if not self.suppress_output:
                print_prompt_and_response(
                    prompt=query,
                    response=error_content,
                    agent_type=f"{agent_type_with_size}_ERROR",
                    iteration=self.iteration,
                    show_prompt=True,
                )

            # Log the error too
            if self.artifacts_dir:
                _log_prompt_and_response(
                    prompt=query,
                    response=error_content,
                    artifacts_dir=self.artifacts_dir,
                    agent_type=f"{self.agent_type}_ERROR",
                    iteration=self.iteration,
                    workflow_tag=self.workflow_tag,
                )

            return AIMessage(content=error_content)
        except Exception as e:
            error_content = f"Error: {str(e)}"

            # Print error using Rich formatting (only if not suppressed)
            if not self.suppress_output:
                print_prompt_and_response(
                    prompt=query,
                    response=error_content,
                    agent_type=f"{agent_type_with_size}_ERROR",
                    iteration=self.iteration,
                    show_prompt=True,
                )

            # Log the error too
            if self.artifacts_dir:
                _log_prompt_and_response(
                    prompt=query,
                    response=error_content,
                    artifacts_dir=self.artifacts_dir,
                    agent_type=f"{self.agent_type}_ERROR",
                    iteration=self.iteration,
                    workflow_tag=self.workflow_tag,
                )

            return AIMessage(content=error_content)
