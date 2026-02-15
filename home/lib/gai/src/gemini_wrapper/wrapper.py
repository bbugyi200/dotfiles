"""Gemini command wrapper and agent invocation utilities.

.. deprecated::
    Use :mod:`llm_provider` directly. This module is kept for backward
    compatibility only.
"""

import os
from typing import Any, Literal, cast

from langchain_core.messages import AIMessage, HumanMessage

# Backward-compat re-exports: tests import these from gemini_wrapper.wrapper
from llm_provider.gemini import (  # noqa: F401
    stream_process_output as _stream_process_output,
)
from llm_provider.postprocessing import (  # noqa: F401
    log_prompt_and_response as _log_prompt_and_response,
)
from llm_provider.postprocessing import (  # noqa: F401
    save_prompt_to_file as _save_prompt_to_file,
)
from llm_provider.types import _MODEL_SIZE_TO_TIER
from rich_utils import print_decision_counts


def invoke_agent(
    prompt: str,
    *,
    agent_type: str,
    model_size: Literal["little", "big"] = "big",
    iteration: int | None = None,
    workflow_tag: str | None = None,
    artifacts_dir: str | None = None,
    workflow: str | None = None,
    suppress_output: bool = False,
    timestamp: str | None = None,
    is_home_mode: bool = False,
) -> AIMessage:
    """Invoke a Gemini agent with standard logging context.

    .. deprecated::
        Use ``llm_provider.invoke_agent()`` directly with ``model_tier``
        instead of ``model_size``.

    Args:
        prompt: The prompt to send to the agent.
        agent_type: Type of agent (e.g., "editor", "planner", "research").
        model_size: Model size ("little" or "big"). Deprecated.
        iteration: Optional iteration number.
        workflow_tag: Optional workflow tag.
        artifacts_dir: Optional artifacts directory for logging.
        workflow: Optional workflow name for chat history.
        suppress_output: If True, suppress output display.
        timestamp: Optional timestamp for chat file naming (YYmmdd_HHMMSS format).
        is_home_mode: If True, skip file copying for @ file references.

    Returns:
        The AIMessage response from the agent.
    """
    from llm_provider import invoke_agent as _llm_invoke_agent

    return _llm_invoke_agent(
        prompt,
        agent_type=agent_type,
        model_size=model_size,
        iteration=iteration,
        workflow_tag=workflow_tag,
        artifacts_dir=artifacts_dir,
        workflow=workflow,
        suppress_output=suppress_output,
        timestamp=timestamp,
        is_home_mode=is_home_mode,
    )


class GeminiCommandWrapper:
    """Wrapper around Gemini CLI invocation.

    .. deprecated::
        Use ``llm_provider.invoke_agent()`` directly.
    """

    def __init__(self, model_size: Literal["little", "big"] = "big") -> None:
        self.decision_counts: dict[str, Any] | None = None
        self.agent_type: str = "agent"
        self.iteration: int | None = None
        self.workflow_tag: str | None = None
        self.artifacts_dir: str | None = None
        self.workflow: str | None = None
        self.timestamp: str | None = None
        self.suppress_output: bool = False
        self.is_home_mode: bool = False
        # Check for global override first, then use constructor arg
        override = os.environ.get("GAI_MODEL_SIZE_OVERRIDE")
        self.model_size: Literal["little", "big"] = (
            cast(Literal["little", "big"], override) if override else model_size
        )

    def set_decision_counts(self, decision_counts: dict[str, Any]) -> None:
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
        is_home_mode: bool = False,
    ) -> None:
        """Set the context for logging prompts and responses."""
        self.agent_type = agent_type
        self.iteration = iteration
        self.workflow_tag = workflow_tag
        self.artifacts_dir = artifacts_dir
        self.suppress_output = suppress_output
        self.workflow = workflow
        self.timestamp = timestamp
        self.is_home_mode = is_home_mode

    def _display_decision_counts(self) -> None:
        """Display the planning agent decision counts."""
        if self.decision_counts is not None:
            print_decision_counts(self.decision_counts)

    def invoke(self, messages: list[HumanMessage | AIMessage]) -> AIMessage:
        """Invoke the LLM with the given messages.

        Delegates to ``llm_provider.invoke_agent()`` internally.
        """
        query: str = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                content = msg.content
                if isinstance(content, str):
                    query = content
                else:
                    query = str(content)
                break

        if not query:
            return AIMessage(content="No query found in messages")

        from llm_provider import invoke_agent as _llm_invoke_agent

        return _llm_invoke_agent(
            query,
            agent_type=self.agent_type,
            model_tier=_MODEL_SIZE_TO_TIER[self.model_size],
            iteration=self.iteration,
            workflow_tag=self.workflow_tag,
            artifacts_dir=self.artifacts_dir,
            workflow=self.workflow,
            suppress_output=self.suppress_output,
            timestamp=self.timestamp,
            is_home_mode=self.is_home_mode,
            decision_counts=self.decision_counts,
        )
