"""Main invoke_agent() orchestrator for the LLM provider abstraction layer.

This replaces the old ``gemini_wrapper.invoke_agent()`` and
``GeminiCommandWrapper.invoke()`` with a provider-agnostic orchestration
layer that delegates the actual LLM call to a pluggable provider.
"""

import os
import subprocess
from typing import Any, Literal, cast

from gai_utils import generate_timestamp
from langchain_core.messages import AIMessage
from rich_utils import print_decision_counts, print_prompt_and_response

from .postprocessing import (
    postprocess_error,
    postprocess_success,
    save_prompt_to_file,
)
from .preprocessing import preprocess_prompt
from .registry import get_provider
from .types import (
    _MODEL_SIZE_TO_TIER,
    _MODEL_TIER_TO_LABEL,
    LoggingContext,
    ModelTier,
)


def invoke_agent(
    prompt: str,
    *,
    agent_type: str,
    model_tier: ModelTier = "large",
    model_size: Literal["little", "big"] | None = None,
    iteration: int | None = None,
    workflow_tag: str | None = None,
    artifacts_dir: str | None = None,
    workflow: str | None = None,
    suppress_output: bool = False,
    timestamp: str | None = None,
    is_home_mode: bool = False,
    decision_counts: dict[str, Any] | None = None,
    provider_name: str | None = None,
) -> AIMessage:
    """Invoke an LLM agent with standard preprocessing, logging, and postprocessing.

    This is the main entry point for sending prompts to any configured LLM
    backend. It handles the full lifecycle:

    1. Preprocess the prompt (xprompt, file refs, jinja2, prettier).
    2. Display decision counts and prompt (if not suppressed).
    3. Save prompt to artifacts directory.
    4. Get provider from registry and invoke.
    5. Postprocess response (logging, chat history, audio).
    6. Return AIMessage.

    Args:
        prompt: The raw prompt to send to the agent.
        agent_type: Type of agent (e.g., "editor", "planner", "research").
        model_tier: Model tier ("large" or "small").
        model_size: Deprecated. Use ``model_tier`` instead. Maps "big" to
            "large" and "little" to "small".
        iteration: Optional iteration number.
        workflow_tag: Optional workflow tag.
        artifacts_dir: Optional artifacts directory for logging.
        workflow: Optional workflow name for chat history.
        suppress_output: If True, suppress output display.
        timestamp: Optional timestamp for chat file naming (YYmmdd_HHMMSS).
        is_home_mode: If True, skip file copying for ``@`` file references.
        decision_counts: Optional planning agent decision counts for display.
        provider_name: Optional provider name override (default from config).

    Returns:
        The AIMessage response from the agent.
    """
    # Handle deprecated model_size parameter
    if model_size is not None:
        model_tier = _MODEL_SIZE_TO_TIER[model_size]

    # Check for global model tier override (env var)
    tier_override = os.environ.get("GAI_MODEL_TIER_OVERRIDE") or os.environ.get(
        "GAI_MODEL_SIZE_OVERRIDE"
    )
    if tier_override:
        # Accept both old ("big"/"little") and new ("large"/"small") values
        if tier_override in _MODEL_SIZE_TO_TIER:
            model_tier = _MODEL_SIZE_TO_TIER[tier_override]
        elif tier_override in ("large", "small"):
            model_tier = cast(ModelTier, tier_override)

    # Build logging context
    context = LoggingContext(
        agent_type=agent_type,
        iteration=iteration,
        workflow_tag=workflow_tag,
        artifacts_dir=artifacts_dir,
        suppress_output=suppress_output,
        workflow=workflow,
        timestamp=timestamp,
        is_home_mode=is_home_mode,
        decision_counts=decision_counts,
    )

    # 1. Preprocess prompt
    query = preprocess_prompt(prompt, is_home_mode=is_home_mode)

    # 2. Build display label
    model_tier_label = _MODEL_TIER_TO_LABEL[model_tier]
    agent_type_with_tier = f"{agent_type} [{model_tier_label}]"

    # 3. Display decision counts (if not suppressed)
    if not suppress_output and decision_counts is not None:
        print_decision_counts(decision_counts)

    # 4. Print prompt BEFORE execution (if not suppressed)
    if not suppress_output:
        print_prompt_and_response(
            prompt=query,
            response="",
            agent_type=agent_type_with_tier,
            iteration=iteration,
            show_prompt=True,
            show_response=False,
        )

    # 5. Generate or use provided timestamp
    start_timestamp = timestamp or generate_timestamp()

    # 6. Save prompt to artifacts
    if artifacts_dir:
        save_prompt_to_file(
            prompt=query,
            artifacts_dir=artifacts_dir,
            agent_type=agent_type,
            iteration=iteration,
        )

    # 7. Get provider and invoke
    try:
        provider = get_provider(provider_name)
        response_content = provider.invoke(
            query,
            model_tier=model_tier,
            suppress_output=suppress_output,
        )

        # 8. Postprocess success
        postprocess_success(
            prompt=query,
            response=response_content,
            context=context,
            model_tier=model_tier,
            start_timestamp=start_timestamp,
        )

        return AIMessage(content=response_content)

    except subprocess.CalledProcessError as e:
        error_content = f"Error running gemini command: {e.stderr}"

        postprocess_error(
            prompt=query,
            error_content=error_content,
            context=context,
            model_tier=model_tier,
            start_timestamp=start_timestamp,
        )

        return AIMessage(content=error_content)

    except Exception as e:
        error_content = f"Error: {str(e)}"

        postprocess_error(
            prompt=query,
            error_content=error_content,
            context=context,
            model_tier=model_tier,
            start_timestamp=start_timestamp,
        )

        return AIMessage(content=error_content)
