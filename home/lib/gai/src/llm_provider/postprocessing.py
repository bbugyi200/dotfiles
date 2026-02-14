"""Postprocessing functions for LLM responses."""

import os
from datetime import datetime

from chat_history import save_chat_history
from gai_utils import EASTERN_TZ
from rich_utils import print_prompt_and_response
from shared_utils import get_gai_log_file, run_bam_command

from .types import LoggingContext


def log_prompt_and_response(
    prompt: str,
    response: str,
    artifacts_dir: str,
    agent_type: str = "agent",
    iteration: int | None = None,
    workflow_tag: str | None = None,
) -> None:
    """Log a prompt and response to the workflow-specific gai.md file.

    Args:
        prompt: The prompt sent to the AI.
        response: The response received from the AI.
        artifacts_dir: Directory where the gai.md file should be stored.
        agent_type: Type of agent (e.g., "editor", "planner", "research").
        iteration: Iteration number if applicable.
        workflow_tag: Workflow tag if available.
    """
    try:
        log_file = get_gai_log_file(artifacts_dir)
        timestamp = datetime.now(EASTERN_TZ).strftime("%Y-%m-%d %H:%M:%S EST")

        header_parts = [agent_type]
        if iteration is not None:
            header_parts.append(f"iteration {iteration}")
        if workflow_tag:
            header_parts.append(f"tag {workflow_tag}")

        header = " - ".join(header_parts)

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

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)

    except Exception as e:
        print(f"Warning: Failed to log prompt and response to gai.md: {e}")


def save_prompt_to_file(
    prompt: str,
    artifacts_dir: str,
    agent_type: str = "agent",
    iteration: int | None = None,
) -> None:
    """Save the prompt to a file in the artifacts directory before running the agent.

    Args:
        prompt: The prompt to save.
        artifacts_dir: Directory where the prompt file should be stored.
        agent_type: Type of agent (e.g., "editor", "planner", "research").
        iteration: Iteration number if applicable.
    """
    try:
        if iteration is not None:
            filename = f"{agent_type}_iter_{iteration}_prompt.md"
        else:
            filename = f"{agent_type}_prompt.md"

        prompt_path = os.path.join(artifacts_dir, filename)
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt)
    except Exception as e:
        print(f"Warning: Failed to save prompt to file: {e}")


def _build_chat_agent_name(
    agent_type: str, workflow: str, *, is_error: bool = False
) -> str | None:
    """Build the agent name for chat history, or None if same as workflow.

    Only includes agent in the filename if it's different from the workflow
    (for multi-agent workflows like crs).

    Args:
        agent_type: The agent type string.
        workflow: The workflow name.
        is_error: If True, append "_ERROR" suffix.

    Returns:
        The agent name string for chat history, or None if agent matches workflow.
    """
    suffix = "_ERROR" if is_error else ""
    if agent_type:
        normalized_agent = agent_type.replace("-", "_")
        normalized_workflow = workflow.replace("-", "_")
        if normalized_agent != normalized_workflow:
            return f"{agent_type}{suffix}"
        elif is_error:
            return "_ERROR"
    elif is_error:
        return "_ERROR"
    return None


def run_postprocessing(
    query: str,
    response: str,
    context: LoggingContext,
    start_timestamp: str,
) -> None:
    """Run standard postprocessing after a successful LLM response.

    Handles audio notification, artifact logging, and chat history saving.

    Args:
        query: The preprocessed prompt that was sent.
        response: The response text from the LLM.
        context: The logging context with metadata.
        start_timestamp: Timestamp string for chat file naming.
    """
    if not context.suppress_output:
        run_bam_command("Agent reply received", delay=0.2)

    if context.artifacts_dir:
        log_prompt_and_response(
            prompt=query,
            response=response,
            artifacts_dir=context.artifacts_dir,
            agent_type=context.agent_type,
            iteration=context.iteration,
            workflow_tag=context.workflow_tag,
        )

    if context.workflow:
        chat_agent = _build_chat_agent_name(context.agent_type, context.workflow)
        save_chat_history(
            prompt=query,
            response=response,
            workflow=context.workflow,
            agent=chat_agent,
            timestamp=start_timestamp,
        )


def run_error_postprocessing(
    query: str,
    error_content: str,
    context: LoggingContext,
    agent_type_with_size: str,
    start_timestamp: str,
) -> None:
    """Run postprocessing after an LLM invocation error.

    Handles error display, artifact logging, and chat history saving.

    Args:
        query: The preprocessed prompt that was sent.
        error_content: The error message/content.
        context: The logging context with metadata.
        agent_type_with_size: Agent type label with model size suffix (e.g. "editor [BIG]").
        start_timestamp: Timestamp string for chat file naming.
    """
    if not context.suppress_output:
        print_prompt_and_response(
            prompt=query,
            response=error_content,
            agent_type=f"{agent_type_with_size}_ERROR",
            iteration=context.iteration,
            show_prompt=True,
        )

    if context.artifacts_dir:
        log_prompt_and_response(
            prompt=query,
            response=error_content,
            artifacts_dir=context.artifacts_dir,
            agent_type=f"{context.agent_type}_ERROR",
            iteration=context.iteration,
            workflow_tag=context.workflow_tag,
        )

    if context.workflow:
        chat_agent = _build_chat_agent_name(
            context.agent_type, context.workflow, is_error=True
        )
        save_chat_history(
            prompt=query,
            response=error_content,
            workflow=context.workflow,
            agent=chat_agent,
            timestamp=start_timestamp,
        )
