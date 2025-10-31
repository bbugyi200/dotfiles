import os
import subprocess
from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import print_decision_counts, print_prompt_and_response


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


class GeminiCommandWrapper:
    def __init__(self) -> None:
        self.decision_counts = None
        self.agent_type = "agent"
        self.iteration = None
        self.workflow_tag = None
        self.artifacts_dir = None
        self.suppress_output = (
            False  # Flag to suppress immediate prompt/response output
        )

    def set_decision_counts(self, decision_counts: dict) -> None:
        """Set the decision counts for display after prompts."""
        self.decision_counts = decision_counts

    def set_logging_context(
        self,
        agent_type: str = "agent",
        iteration: Optional[int] = None,
        workflow_tag: Optional[str] = None,
        artifacts_dir: Optional[str] = None,
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

    def invoke(self, messages: List[HumanMessage | AIMessage]) -> AIMessage:
        query = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                query = msg.content
                break

        if not query:
            return AIMessage(content="No query found in messages")

        # Display decision counts before the prompt if available (only if not suppressed)
        if not self.suppress_output:
            self._display_decision_counts()

        # Print prompt BEFORE execution for non-research agents (only if not suppressed)
        if not self.suppress_output:
            print_prompt_and_response(
                prompt=query,
                response="",  # Empty response since we haven't executed yet
                agent_type=self.agent_type,
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
            extra_args_env = os.environ.get("GEMINI_CLI_EXTRA_ARGS")
            if extra_args_env:
                # Split the environment variable on whitespace to get individual args
                for arg in extra_args_env.split():
                    base_args.append(arg)

            # Pass query via stdin to avoid "Argument list too long" error
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
                    agent_type=self.agent_type,
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
                    agent_type=f"{self.agent_type}_ERROR",
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
                    agent_type=f"{self.agent_type}_ERROR",
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
