import os
import re
import subprocess
import sys
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import gemini_timer, print_decision_counts, print_prompt_and_response


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


def _validate_file_references(prompt: str) -> None:
    """
    Validate that all file paths prefixed with '@' in the prompt exist and are relative.

    This function extracts all file paths from the prompt that are prefixed
    with '@' and verifies that:
    1. Each file path is relative (not absolute)
    2. Each file exists
    3. There are no duplicate file path references

    If any file is absolute, does not exist, or is duplicated, it prints an
    error message and terminates the script.

    Args:
        prompt: The prompt text to validate

    Raises:
        SystemExit: If any referenced file is absolute, does not exist, or is duplicated
    """
    # Pattern to match '@' followed by a file path
    # This captures paths like @/path/to/file.txt or @path/to/file
    # We look for @ followed by non-whitespace characters that look like file paths
    pattern = r"@((?:[^\s,;:()[\]{}\"'`])+)"

    # Find all matches
    matches = re.findall(pattern, prompt)

    if not matches:
        return  # No file references found

    absolute_paths = []
    missing_files = []
    seen_paths: dict[str, int] = {}  # Track file paths and their occurrence count

    for file_path in matches:
        # Clean up the path (remove trailing punctuation)
        file_path = file_path.rstrip(".,;:!?)")

        # Skip if it looks like an email address or mention
        if "@" in file_path or file_path.startswith("http"):
            continue

        # Track this file path
        seen_paths[file_path] = seen_paths.get(file_path, 0) + 1

        # Check if the file path is absolute
        if os.path.isabs(file_path):
            if file_path not in absolute_paths:
                absolute_paths.append(file_path)
            continue

        # Check if the file exists
        if not os.path.exists(file_path) and file_path not in missing_files:
            missing_files.append(file_path)

    # Check for duplicates
    duplicate_paths = [path for path, count in seen_paths.items() if count > 1]

    if absolute_paths:
        print("\n❌ ERROR: The following file(s) use absolute paths in '@' references:")
        for file_path in absolute_paths:
            print(f"  - @{file_path}")
        print("\n⚠️ All '@' file references MUST use relative paths (relative to CWD).")
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


class GeminiCommandWrapper:
    def __init__(self, model_size: str = "little") -> None:
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
        self.model_size: str = override if override else model_size  # "little" or "big"

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

        # Validate file references in the prompt
        _validate_file_references(query)

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

            # Pass query via stdin to avoid "Argument list too long" error
            # Show timer only if output is not suppressed
            if not self.suppress_output:
                with gemini_timer("Waiting for Gemini"):
                    result = subprocess.run(
                        base_args,
                        input=query,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
            else:
                result = subprocess.run(
                    base_args,
                    input=query,
                    capture_output=True,
                    text=True,
                    check=True,
                )
            response_content = result.stdout.strip()

            # Print only the response using Rich formatting (only if not suppressed)
            if not self.suppress_output:
                print_prompt_and_response(
                    prompt="",  # Empty prompt since we already showed it
                    response=response_content,
                    agent_type=agent_type_with_size,
                    iteration=self.iteration,
                    show_prompt=False,  # Don't show prompt again
                    show_response=True,  # Only show response
                )

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
