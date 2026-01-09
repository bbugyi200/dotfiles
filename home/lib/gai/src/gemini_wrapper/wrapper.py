"""Gemini command wrapper and agent invocation utilities."""

import os
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
    print_prompt_and_response,
)
from shared_utils import get_gai_log_file, run_bam_command

from .file_references import (
    format_with_prettier,
    process_command_substitution,
    process_file_references,
    process_xcmd_references,
)
from .snippet_processor import process_snippet_references


def _log_prompt_and_response(
    prompt: str,
    response: str,
    artifacts_dir: str,
    agent_type: str = "agent",
    iteration: int | None = None,
    workflow_tag: str | None = None,
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
    timestamp: str | None = None,
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
        timestamp: Optional timestamp for chat file naming (YYmmdd_HHMMSS format).

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
        timestamp=timestamp,
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
        self.timestamp: str | None = None  # Timestamp for chat file naming
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
        timestamp: str | None = None,
    ) -> None:
        """Set the context for logging prompts and responses.

        Args:
            agent_type: Type of agent (e.g., "editor", "planner", "research")
            iteration: Iteration number if applicable
            workflow_tag: Workflow tag if available
            artifacts_dir: Directory where the gai.md file should be stored
            suppress_output: If True, suppress immediate prompt/response output
            workflow: Workflow name for saving to ~/.gai/chats/ (e.g., "fix-tests")
            timestamp: Optional timestamp for chat file naming (YYmmdd_HHMMSS format)
        """
        self.agent_type = agent_type
        self.iteration = iteration
        self.workflow_tag = workflow_tag
        self.artifacts_dir = artifacts_dir
        self.suppress_output = suppress_output
        self.workflow = workflow
        self.timestamp = timestamp

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

        # Process snippet references in the prompt (expand #name patterns)
        query = process_snippet_references(query)

        # Process command substitution in the prompt (expand $(cmd) patterns)
        query = process_command_substitution(query)

        # Process xcmd references in the prompt (expand #(filename: cmd) patterns)
        query = process_xcmd_references(query)

        # Process file references in the prompt (copy absolute paths to bb/gai/context/ and update prompt)
        query = process_file_references(query)

        # Format prompt with prettier for consistent markdown formatting
        query = format_with_prettier(query)

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

        # Use provided timestamp if available, otherwise generate one
        start_timestamp = self.timestamp or generate_timestamp()

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
                # Only include agent in filename if it's different from workflow
                # (for multi-agent workflows like fix-tests)
                chat_agent: str | None = None
                if self.agent_type:
                    normalized_agent = self.agent_type.replace("-", "_")
                    normalized_workflow = self.workflow.replace("-", "_")
                    if normalized_agent != normalized_workflow:
                        chat_agent = self.agent_type

                save_chat_history(
                    prompt=query,
                    response=response_content,
                    workflow=self.workflow,
                    agent=chat_agent,
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
                # Only include agent in filename if it's different from workflow
                # (for multi-agent workflows like fix-tests)
                if self.agent_type:
                    normalized_agent = self.agent_type.replace("-", "_")
                    normalized_workflow = self.workflow.replace("-", "_")
                    if normalized_agent != normalized_workflow:
                        chat_agent_error = f"{self.agent_type}_ERROR"
                    else:
                        chat_agent_error = "_ERROR"
                else:
                    chat_agent_error = "_ERROR"

                save_chat_history(
                    prompt=query,
                    response=error_content,
                    workflow=self.workflow,
                    agent=chat_agent_error,
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
                # Only include agent in filename if it's different from workflow
                # (for multi-agent workflows like fix-tests)
                if self.agent_type:
                    normalized_agent = self.agent_type.replace("-", "_")
                    normalized_workflow = self.workflow.replace("-", "_")
                    if normalized_agent != normalized_workflow:
                        chat_agent_error = f"{self.agent_type}_ERROR"
                    else:
                        chat_agent_error = "_ERROR"
                else:
                    chat_agent_error = "_ERROR"

                save_chat_history(
                    prompt=query,
                    response=error_content,
                    workflow=self.workflow,
                    agent=chat_agent_error,
                    timestamp=start_timestamp,
                )

            return AIMessage(content=error_content)
