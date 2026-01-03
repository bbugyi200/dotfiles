import os
import re
import select
import subprocess
import sys
from datetime import datetime
from typing import Any, Literal, cast

from chat_history import save_chat_history
from gai_utils import EASTERN_TZ, generate_timestamp
from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import (
    gemini_timer,
    print_decision_counts,
    print_file_operation,
    print_prompt_and_response,
    print_status,
)
from shared_utils import get_gai_log_file, run_bam_command


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
        log_file = get_gai_log_file(artifacts_dir)
        timestamp = datetime.now(EASTERN_TZ).strftime("%Y-%m-%d %H:%M:%S EST")

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

    # Prepare bb/gai/context/ directory (clear and recreate)
    bb_gai_context_dir = "bb/gai/context"
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


def invoke_agent(
    prompt: str,
    *,
    agent_type: str,
    model_size: Literal["little", "big"] = "little",
    iteration: int | None = None,
    workflow_tag: str | None = None,
    artifacts_dir: str | None = None,
    workflow: str | None = None,
    suppress_output: bool = False,
) -> AIMessage:
    """Invoke a Gemini agent with standard logging context.

    This is a convenience function that wraps the common pattern of:
    1. Creating a GeminiCommandWrapper
    2. Setting logging context
    3. Invoking with a HumanMessage prompt

    Args:
        prompt: The prompt to send to the agent.
        agent_type: Type of agent (e.g., "editor", "planner", "research").
        model_size: Model size ("little" or "big").
        iteration: Optional iteration number.
        workflow_tag: Optional workflow tag.
        artifacts_dir: Optional artifacts directory for logging.
        workflow: Optional workflow name for chat history.
        suppress_output: If True, suppress output display.

    Returns:
        The AIMessage response from the agent.
    """
    model = GeminiCommandWrapper(model_size=model_size)
    model.set_logging_context(
        agent_type=agent_type,
        iteration=iteration,
        workflow_tag=workflow_tag,
        artifacts_dir=artifacts_dir,
        suppress_output=suppress_output,
        workflow=workflow,
    )
    messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
    return model.invoke(messages)


class GeminiCommandWrapper:
    def __init__(self, model_size: Literal["little", "big"] = "little") -> None:
        self.decision_counts: dict[str, Any] | None = None
        self.agent_type: str = "agent"
        self.iteration: int | None = None
        self.workflow_tag: str | None = None
        self.artifacts_dir: str | None = None
        self.workflow: str | None = None  # Workflow name for chat history logging
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
        workflow: str | None = None,
    ) -> None:
        """Set the context for logging prompts and responses.

        Args:
            agent_type: Type of agent (e.g., "editor", "planner", "research")
            iteration: Iteration number if applicable
            workflow_tag: Workflow tag if available
            artifacts_dir: Directory where the gai.md file should be stored
            suppress_output: If True, suppress immediate prompt/response output
            workflow: Workflow name for saving to ~/.gai/chats/ (e.g., "fix-tests")
        """
        self.agent_type = agent_type
        self.iteration = iteration
        self.workflow_tag = workflow_tag
        self.artifacts_dir = artifacts_dir
        self.suppress_output = suppress_output
        self.workflow = workflow

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
        query = process_xfile_references(query)

        # Process file references in the prompt (copy absolute paths to bb/gai/context/ and update prompt)
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

        # Capture start timestamp for accurate duration calculation
        start_timestamp = generate_timestamp()

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

            # Save to central chat history (~/.gai/chats/) if workflow is set
            if self.workflow:
                save_chat_history(
                    prompt=query,
                    response=response_content,
                    workflow=self.workflow,
                    agent=self.agent_type,
                    timestamp=start_timestamp,
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

            # Save error to central chat history if workflow is set
            if self.workflow:
                save_chat_history(
                    prompt=query,
                    response=error_content,
                    workflow=self.workflow,
                    agent=f"{self.agent_type}_ERROR",
                    timestamp=start_timestamp,
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

            # Save error to central chat history if workflow is set
            if self.workflow:
                save_chat_history(
                    prompt=query,
                    response=error_content,
                    workflow=self.workflow,
                    agent=f"{self.agent_type}_ERROR",
                    timestamp=start_timestamp,
                )

            return AIMessage(content=error_content)
