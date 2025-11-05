"""Agent implementations for the new-change workflow."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import print_status
from shared_utils import ensure_str_content

from .prompts import build_editor_prompt
from .state import NewChangeState


def run_editor_agent(state: NewChangeState) -> NewChangeState:
    """
    Run the editor agent to implement the changes.

    Uses Gemini big model for high-quality code generation.
    """
    print_status("Running editor agent to implement changes...", "progress")

    # Build the prompt
    prompt = build_editor_prompt(state)

    # Send prompt to Gemini with big model for best code quality
    model = GeminiCommandWrapper(model_size="big")
    model.set_logging_context(
        agent_type="editor",
        iteration=1,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
    )

    try:
        # Run the agent
        messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
        response = model.invoke(messages)

        # Extract the response content
        if isinstance(response, AIMessage):
            editor_response = ensure_str_content(response.content)
        else:
            editor_response = str(response)

        return {
            **state,
            "editor_response": editor_response,
        }

    except Exception as e:
        print_status(f"Error running editor agent: {e}", "error")
        return {
            **state,
            "failure_reason": f"Editor agent failed: {e}",
        }
