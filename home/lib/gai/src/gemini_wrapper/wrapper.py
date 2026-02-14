"""Gemini command wrapper and agent invocation utilities."""

import os
from typing import Any, Literal, cast

from gai_utils import generate_timestamp
from langchain_core.messages import AIMessage, HumanMessage
from llm_provider import (
    GeminiProvider,
    LLMInvocationError,
    LoggingContext,
    preprocess_prompt,
    run_error_postprocessing,
    run_postprocessing,
    save_prompt_to_file,
)
from rich_utils import print_decision_counts, print_prompt_and_response


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
        is_home_mode: If True, skip file copying for @ file references.

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
        is_home_mode=is_home_mode,
    )
    messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
    return model.invoke(messages)


class GeminiCommandWrapper:
    def __init__(self, model_size: Literal["little", "big"] = "big") -> None:
        self.decision_counts: dict[str, Any] | None = None
        # Check for global override first, then use constructor arg
        override = os.environ.get("GAI_MODEL_SIZE_OVERRIDE")
        self.model_size: Literal["little", "big"] = (
            cast(Literal["little", "big"], override) if override else model_size
        )
        self._context = LoggingContext(model_size=self.model_size)
        self._provider = GeminiProvider()

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
        """Set the context for logging prompts and responses.

        Args:
            agent_type: Type of agent (e.g., "editor", "planner", "research")
            iteration: Iteration number if applicable
            workflow_tag: Workflow tag if available
            artifacts_dir: Directory where the gai.md file should be stored
            suppress_output: If True, suppress immediate prompt/response output
            workflow: Workflow name for saving to ~/.gai/chats/ (e.g., "crs")
            timestamp: Optional timestamp for chat file naming (YYmmdd_HHMMSS format)
            is_home_mode: If True, skip file copying for @ file references
        """
        self._context = LoggingContext(
            agent_type=agent_type,
            model_size=self.model_size,
            iteration=iteration,
            workflow_tag=workflow_tag,
            artifacts_dir=artifacts_dir,
            workflow=workflow,
            timestamp=timestamp,
            suppress_output=suppress_output,
            is_home_mode=is_home_mode,
            decision_counts=self.decision_counts,
        )

    # Keep these as properties for backward compatibility with tests
    @property
    def agent_type(self) -> str:
        return self._context.agent_type

    @property
    def iteration(self) -> int | None:
        return self._context.iteration

    @property
    def workflow_tag(self) -> str | None:
        return self._context.workflow_tag

    @property
    def artifacts_dir(self) -> str | None:
        return self._context.artifacts_dir

    @property
    def suppress_output(self) -> bool:
        return self._context.suppress_output

    @property
    def workflow(self) -> str | None:
        return self._context.workflow

    @property
    def timestamp(self) -> str | None:
        return self._context.timestamp

    @property
    def is_home_mode(self) -> bool:
        return self._context.is_home_mode

    def _display_decision_counts(self) -> None:
        """Display the planning agent decision counts."""
        if self.decision_counts is not None:
            print_decision_counts(self.decision_counts)

    def invoke(self, messages: list[HumanMessage | AIMessage]) -> AIMessage:
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

        # Preprocessing pipeline
        query = preprocess_prompt(query, is_home_mode=self._context.is_home_mode)

        # Build agent type with model size suffix
        model_size_label = "BIG" if self.model_size == "big" else "LITTLE"
        agent_type_with_size = f"{self._context.agent_type} [{model_size_label}]"

        # Display decision counts before the prompt if available
        if not self._context.suppress_output:
            self._display_decision_counts()

        # Print prompt BEFORE execution (only if not suppressed)
        if not self._context.suppress_output:
            print_prompt_and_response(
                prompt=query,
                response="",
                agent_type=agent_type_with_size,
                iteration=self._context.iteration,
                show_prompt=True,
                show_response=False,
            )

        start_timestamp = self._context.timestamp or generate_timestamp()

        # Save prompt to artifacts before running agent
        if self._context.artifacts_dir:
            save_prompt_to_file(
                prompt=query,
                artifacts_dir=self._context.artifacts_dir,
                agent_type=self._context.agent_type,
                iteration=self._context.iteration,
            )

        try:
            response_content = self._provider.invoke_llm(
                query,
                model_size=self.model_size,
                suppress_output=self._context.suppress_output,
            )

            run_postprocessing(
                query=query,
                response=response_content,
                context=self._context,
                start_timestamp=start_timestamp,
            )

            return AIMessage(content=response_content)
        except LLMInvocationError as e:
            error_content = str(e)

            run_error_postprocessing(
                query=query,
                error_content=error_content,
                context=self._context,
                agent_type_with_size=agent_type_with_size,
                start_timestamp=start_timestamp,
            )

            return AIMessage(content=error_content)
        except Exception as e:
            error_content = f"Error: {str(e)}"

            run_error_postprocessing(
                query=query,
                error_content=error_content,
                context=self._context,
                agent_type_with_size=agent_type_with_size,
                start_timestamp=start_timestamp,
            )

            return AIMessage(content=error_content)
