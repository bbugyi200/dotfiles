"""Agent implementations for the create-cl workflow."""

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import create_progress_tracker, print_status
from shared_utils import ensure_str_content

from .prompts import (
    build_architecture_research_prompt,
    build_coder_prompt,
    build_implementation_research_prompt,
    build_test_research_prompt,
)
from .state import CreateCLState


def _run_single_research_agent(
    state: CreateCLState, focus: str, title: str, prompt_builder: Any
) -> dict[str, Any]:
    """Run a single research agent and return its results."""
    # Build prompt using the provided builder
    prompt = prompt_builder(state)

    # Create Gemini wrapper with big model
    model = GeminiCommandWrapper(model_size="big")
    model.set_logging_context(
        agent_type=f"research_{focus}",
        iteration=1,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
        suppress_output=True,  # Suppress output during parallel execution
    )

    # Send prompt
    messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    # Return structured result including prompt for later display
    return {
        "focus": focus,
        "title": title,
        "content": ensure_str_content(response.content),
        "prompt": prompt,  # Include prompt for later display
        "messages": messages + [response],
    }


def run_research_agents(state: CreateCLState) -> CreateCLState:
    """Run 3 research agents in parallel to gather implementation insights."""
    print_status("Running 3 parallel research agents...", "progress")

    # Define the 3 research focuses
    research_focuses = [
        (
            "implementation",
            "Implementation Research",
            build_implementation_research_prompt,
        ),
        (
            "test_strategy",
            "Test Strategy Research",
            build_test_research_prompt,
        ),
        (
            "architecture",
            "Architecture Research",
            build_architecture_research_prompt,
        ),
    ]

    research_results = {}
    all_messages = state["messages"]

    # Run all 3 research agents in parallel
    with create_progress_tracker("Research agents", len(research_focuses)) as progress:
        task = progress.add_task(
            "Running research agents...", total=len(research_focuses)
        )

        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all research agent tasks
            future_to_focus = {}
            for focus, title, prompt_builder in research_focuses:
                future = executor.submit(
                    _run_single_research_agent, state, focus, title, prompt_builder
                )
                future_to_focus[future] = focus

            # Collect results as they complete
            completed_results = []  # Store completed results for display
            for future in as_completed(future_to_focus):
                focus = future_to_focus[future]
                try:
                    result = future.result()

                    # Store the result
                    research_results[result["focus"]] = {
                        "title": result["title"],
                        "content": result["content"],
                    }

                    # Store completed result for display
                    completed_results.append(result)

                    # Add messages to the overall message list
                    all_messages.extend(result["messages"])

                    print_status(
                        f"{focus.replace('_', ' ')} research agent completed successfully",
                        "success",
                    )

                except Exception as e:
                    print_status(
                        f"{focus.replace('_', ' ')} research agent failed: {e}", "error"
                    )
                    # Create placeholder result for failed agents
                    research_results[focus] = {
                        "title": f"{focus.replace('_', ' ').title()} Research (Failed)",
                        "content": f"Research agent failed with error: {str(e)}",
                    }

                progress.advance(task)

    print_status("All research agents completed", "success")

    # Now display all prompt/response pairs using Rich formatting
    from rich_utils import print_prompt_and_response

    print_status("Displaying research agent results...", "progress")
    for result in completed_results:
        if "prompt" in result:
            print_prompt_and_response(
                prompt=result["prompt"],
                response=result["content"],
                agent_type=f"research_{result['focus']}",
                iteration=1,
                show_prompt=True,
            )

    print_status("Research agent results display completed", "success")

    return {
        **state,
        "research_results": research_results,
        "messages": all_messages,
    }


def run_coder_agent(state: CreateCLState) -> CreateCLState:
    """Run the coder agent to implement the feature and tests."""
    print_status("Running coder agent to implement feature...", "progress")

    # Build prompt for coder
    prompt = build_coder_prompt(state)

    # Create Gemini wrapper with big model
    model = GeminiCommandWrapper(model_size="big")
    model.set_logging_context(
        agent_type="coder",
        iteration=1,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
    )

    # Send prompt
    messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    response_content = ensure_str_content(response.content)
    print_status("Coder agent response received", "success")

    # Save coder response to artifacts
    coder_response_path = os.path.join(
        state["artifacts_dir"], "coder_agent_response.txt"
    )
    with open(coder_response_path, "w") as f:
        f.write(response_content)
    print_status(f"Saved coder response to: {coder_response_path}", "info")

    # Check if coder agent succeeded (look for SUCCESS or FAILURE at the end)
    response_lines = response_content.strip().split("\n")
    coder_success = False

    # Check the last few lines for SUCCESS/FAILURE
    for line in reversed(response_lines[-10:]):  # Check last 10 lines
        line_stripped = line.strip()
        if line_stripped == "SUCCESS":
            coder_success = True
            break
        elif line_stripped == "FAILURE":
            coder_success = False
            break

    status_msg = "succeeded" if coder_success else "reported failures"
    print_status(f"Coder agent {status_msg}", "success" if coder_success else "warning")

    return {
        **state,
        "coder_response": response_content,
        "coder_success": coder_success,
        "messages": state["messages"] + messages + [response],
    }
