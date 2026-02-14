"""Provider-agnostic agent invocation function."""

import os
from typing import cast

from gai_utils import generate_timestamp
from langchain_core.messages import AIMessage
from rich_utils import print_prompt_and_response

from .config import load_llm_provider_config
from .postprocessing import (
    run_error_postprocessing,
    run_postprocessing,
    save_prompt_to_file,
)
from .preprocessing import preprocess_prompt
from .registry import get_provider
from .types import LLMInvocationError, LoggingContext, ModelTier


def invoke_agent(
    prompt: str,
    *,
    agent_type: str,
    model_tier: ModelTier = "big",
    iteration: int | None = None,
    workflow_tag: str | None = None,
    artifacts_dir: str | None = None,
    workflow: str | None = None,
    suppress_output: bool = False,
    timestamp: str | None = None,
    is_home_mode: bool = False,
) -> AIMessage:
    """Invoke an LLM agent with standard logging context.

    The provider is selected via the ``llm_provider.provider`` key in
    ``gai.yml`` (defaults to ``"gemini"``).

    Args:
        prompt: The prompt to send to the agent.
        agent_type: Type of agent (e.g., "editor", "planner", "research").
        model_tier: Model tier ("little" or "big").
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
    # Apply global model tier override from environment
    override = os.environ.get("GAI_MODEL_TIER_OVERRIDE") or os.environ.get(
        "GAI_MODEL_SIZE_OVERRIDE"
    )
    effective_tier: ModelTier = cast(ModelTier, override) if override else model_tier

    context = LoggingContext(
        agent_type=agent_type,
        model_tier=effective_tier,
        iteration=iteration,
        workflow_tag=workflow_tag,
        artifacts_dir=artifacts_dir,
        workflow=workflow,
        timestamp=timestamp,
        suppress_output=suppress_output,
        is_home_mode=is_home_mode,
    )

    config = load_llm_provider_config()
    provider = get_provider(config.provider)

    # Preprocessing pipeline
    query = preprocess_prompt(prompt, is_home_mode=is_home_mode)

    # Build agent type with model tier suffix
    tier_label = "BIG" if effective_tier == "big" else "LITTLE"
    agent_type_with_tier = f"{agent_type} [{tier_label}]"

    # Print prompt BEFORE execution (only if not suppressed)
    if not suppress_output:
        print_prompt_and_response(
            prompt=query,
            response="",
            agent_type=agent_type_with_tier,
            iteration=iteration,
            show_prompt=True,
            show_response=False,
        )

    start_timestamp = timestamp or generate_timestamp()

    # Save prompt to artifacts before running agent
    if artifacts_dir:
        save_prompt_to_file(
            prompt=query,
            artifacts_dir=artifacts_dir,
            agent_type=agent_type,
            iteration=iteration,
        )

    try:
        response_content = provider.invoke_llm(
            query,
            model_size=effective_tier,
            suppress_output=suppress_output,
        )

        run_postprocessing(
            query=query,
            response=response_content,
            context=context,
            start_timestamp=start_timestamp,
        )

        return AIMessage(content=response_content)
    except LLMInvocationError as e:
        error_content = str(e)

        run_error_postprocessing(
            query=query,
            error_content=error_content,
            context=context,
            agent_type_with_size=agent_type_with_tier,
            start_timestamp=start_timestamp,
        )

        return AIMessage(content=error_content)
    except Exception as e:
        error_content = f"Error: {str(e)}"

        run_error_postprocessing(
            query=query,
            error_content=error_content,
            context=context,
            agent_type_with_size=agent_type_with_tier,
            start_timestamp=start_timestamp,
        )

        return AIMessage(content=error_content)
