import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import (
    create_progress_tracker,
    print_iteration_header,
    print_prompt_and_response,
    print_status,
)
from shared_utils import (
    add_research_to_log,
    ensure_str_content,
    run_shell_command,
)

from ..prompts import (
    build_research_prompt,
)
from ..state import (
    FixTestsState,
)


def _run_single_research_agent(
    state: FixTestsState, focus: str, title: str, description: str
) -> dict[str, Any]:
    """Run a single research agent and return its results."""
    iteration = state["current_iteration"]
    artifacts_dir = state["artifacts_dir"]
    print(f"Running {focus.replace('_', ' ')} research agent...")
    prompt = build_research_prompt(state, focus)
    model = GeminiCommandWrapper()
    model.set_logging_context(
        agent_type=f"research_{focus}",
        iteration=iteration,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
        suppress_output=True,
    )
    messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
    response = model.invoke(messages)
    print(f"{focus.replace('_', ' ')} research agent response received")
    research_response_path = os.path.join(
        artifacts_dir, f"research_{focus}_iter_{iteration}_response.txt"
    )
    with open(research_response_path, "w") as f:
        f.write(ensure_str_content(response.content))
    return {
        "focus": focus,
        "title": title,
        "description": description,
        "content": ensure_str_content(response.content),
        "prompt": prompt,
        "messages": messages + [response],
    }


def run_research_agents(state: FixTestsState) -> FixTestsState:
    """Run research agents with different focus areas in parallel and combine results into research.md."""
    iteration = state["current_iteration"]
    print_iteration_header(iteration, "research")
    initial_research_file = state.get("initial_research_file")
    if initial_research_file and os.path.exists(initial_research_file):
        print_status(
            f"Using initial research from file: {initial_research_file}", "info"
        )
        try:
            with open(initial_research_file) as f:
                initial_research_content = f.read()
        except Exception as e:
            print(f"⚠️ Warning: Could not read initial research file: {e}")
            print_status("Falling back to running research agents", "info")
            initial_research_content = None
        if initial_research_content:
            research_results = {
                "initial": {
                    "title": "Initial Research (from file)",
                    "description": f"Research loaded from {initial_research_file}",
                    "content": initial_research_content,
                }
            }
            add_research_to_log(
                artifacts_dir=state["artifacts_dir"],
                iteration=iteration,
                research_results=research_results,
            )
            print_status("Initial research loaded and added to log.md", "success")
            return {
                **state,
                "research_results": research_results,
                "research_md_created": True,
                "messages": state["messages"],
            }
    print_status(
        f"Running research agents in parallel (iteration {iteration})...", "progress"
    )
    research_focuses = [
        (
            "cl_scope",
            "CL Scope Analysis",
            "Analyzing the change list scope and impact on the broader codebase",
        ),
        (
            "similar_tests",
            "Similar Tests Analysis",
            "Finding similar test patterns and examples in the codebase",
        ),
        (
            "test_failure",
            "Test Failure Analysis",
            "Deep analysis of the specific test failure and error messages",
        ),
        (
            "prior_work_analysis",
            "Prior Work Analysis",
            "Investigating previous work and potential issues with prior implementations",
        ),
    ]
    clsurf_output_file = state.get("clsurf_output_file")
    if (
        state.get("clquery")
        and clsurf_output_file
        and os.path.exists(clsurf_output_file)
    ):
        research_focuses.append(
            (
                "cl_analysis",
                "Previous CL Analysis",
                "Analyzing previous CLs submitted by the author to understand patterns and solutions",
            )
        )
        print_status(
            f"Added CL analysis research agent due to clquery: {state['clquery']}",
            "info",
        )
    research_results = {}
    all_messages = state["messages"]
    max_workers = len(research_focuses)
    with create_progress_tracker("Research agents", len(research_focuses)) as progress:
        task = progress.add_task(
            "Running research agents...", total=len(research_focuses)
        )
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_focus = {}
            for focus, title, description in research_focuses:
                future = executor.submit(
                    _run_single_research_agent, state, focus, title, description
                )
                future_to_focus[future] = focus
            completed_results = []
            for future in as_completed(future_to_focus):
                focus = future_to_focus[future]
                try:
                    result = future.result()
                    research_results[result["focus"]] = {
                        "title": result["title"],
                        "description": result["description"],
                        "content": result["content"],
                    }
                    completed_results.append(result)
                    all_messages.extend(result["messages"])
                    print_status(
                        f"{focus.replace('_', ' ')} research agent completed successfully",
                        "success",
                    )
                except Exception as e:
                    print_status(
                        f"{focus.replace('_', ' ')} research agent failed: {e}", "error"
                    )
                    research_results[focus] = {
                        "title": f"{focus.replace('_', ' ').title()} (Failed)",
                        "description": f"Research agent failed with error: {e}",
                        "content": f"Error running {focus} research agent: {str(e)}",
                    }
                progress.advance(task)
    print_status("All research agents completed", "success")
    print_status("Displaying research agent results...", "progress")
    for result in completed_results:
        if "prompt" in result:
            print_prompt_and_response(
                prompt=result["prompt"],
                response=result["content"],
                agent_type=f"research_{result['focus']}",
                iteration=iteration,
                show_prompt=True,
            )
    print_status("Research agent results display completed", "success")
    print("Cleaning up any local changes made by research agents...")
    cleanup_result = run_shell_command("hg update --clean .", capture_output=True)
    if cleanup_result.returncode == 0:
        print("✅ Successfully cleaned up local changes from research agents")
    else:
        print(f"⚠️ Warning: Failed to clean up local changes: {cleanup_result.stderr}")
    print_status(
        f"Running synthesis research agent (iteration {iteration})...", "progress"
    )
    synthesis_result = _run_synthesis_research_agent(state, research_results)
    if synthesis_result:
        research_results["synthesis"] = {
            "title": "Research Synthesis",
            "description": "Synthesized, de-duplicated, verified, and enhanced research findings from all agents",
            "content": synthesis_result["content"],
        }
        print_prompt_and_response(
            prompt=synthesis_result["prompt"],
            response=synthesis_result["content"],
            agent_type="research_synthesis",
            iteration=iteration,
            show_prompt=True,
        )
        all_messages.extend(synthesis_result["messages"])
        add_research_to_log(
            artifacts_dir=state["artifacts_dir"],
            iteration=iteration,
            research_results={"synthesis": research_results["synthesis"]},
        )
        print_status("Synthesis research agent completed successfully", "success")
    return {
        **state,
        "research_results": research_results,
        "research_md_created": True,
        "messages": all_messages,
    }


def _run_synthesis_research_agent(state: FixTestsState, research_results: dict) -> dict:
    """Run the synthesis research agent to aggregate and enhance all research findings."""
    iteration = state["current_iteration"]
    artifacts_dir = state["artifacts_dir"]
    from ..prompts import build_synthesis_research_prompt

    prompt = build_synthesis_research_prompt(state, research_results)
    model = GeminiCommandWrapper(model_size="big")
    model.set_logging_context(
        agent_type="research_synthesis",
        iteration=iteration,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
    )
    messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
    response = model.invoke(messages)
    synthesis_response_path = os.path.join(
        artifacts_dir, f"research_synthesis_iter_{iteration}_response.txt"
    )
    with open(synthesis_response_path, "w") as f:
        f.write(ensure_str_content(response.content))
    return {
        "content": ensure_str_content(response.content),
        "prompt": prompt,
        "messages": messages + [response],
    }
