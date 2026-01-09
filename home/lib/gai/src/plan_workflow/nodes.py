"""LangGraph node functions for the plan workflow."""

from pathlib import Path

from gemini_wrapper import invoke_agent
from rich.console import Console
from shared_utils import ensure_str_content

from .git_utils import PLANS_DIR, commit_plan, ensure_plans_directory
from .prompts import DESIGN_PROMPT, QA_PROMPT, REFINE_PROMPT, SECTIONS_PROMPT
from .state import PlanState


def initialize_plan_workflow(state: PlanState) -> PlanState:
    """Initialize the plan workflow state."""
    console = Console()
    console.print(
        f"\n[cyan]Initializing plan workflow for: {state['plan_name']}[/cyan]"
    )

    # Ensure plans directory exists
    ensure_plans_directory()

    # Set up the plan path
    plan_path = str(PLANS_DIR / f"{state['plan_name']}.md")

    return {
        **state,
        "plan_path": plan_path,
        "current_stage": "sections",
        "iteration": 0,
        "user_approved": False,
        "failure_reason": None,
    }


def generate_sections(state: PlanState) -> PlanState:
    """Generate section names for the design document using AI."""
    if state.get("sections_from_cli"):
        return state

    console = Console()
    console.print("\n[cyan]Generating section names...[/cyan]")

    prompt = SECTIONS_PROMPT.format(user_query=state["user_query"])

    response = invoke_agent(
        prompt,
        agent_type="plan-sections",
        model_size="little",
        workflow="plan",
    )

    sections = ensure_str_content(response.content)

    console.print("[green]Sections generated.[/green]")

    return {
        **state,
        "sections": sections,
        "current_stage": "qa",
    }


def generate_qa(state: PlanState) -> PlanState:
    """Generate Q&A content for the design document using AI."""
    if state.get("qa_from_cli"):
        return state

    console = Console()
    console.print("\n[cyan]Generating Q&A content...[/cyan]")

    prompt = QA_PROMPT.format(
        user_query=state["user_query"],
        sections=state["sections"],
    )

    response = invoke_agent(
        prompt,
        agent_type="plan-qa",
        model_size="little",
        workflow="plan",
    )

    qa_content = ensure_str_content(response.content)

    console.print("[green]Q&A generated.[/green]")

    return {
        **state,
        "qa_content": qa_content,
        "current_stage": "design",
    }


def generate_design(state: PlanState) -> PlanState:
    """Generate the initial design document using AI."""
    if state.get("design_from_cli"):
        return state

    console = Console()
    console.print("\n[cyan]Generating design document...[/cyan]")

    prompt = DESIGN_PROMPT.format(
        user_query=state["user_query"],
        sections=state["sections"],
        qa_content=state["qa_content"],
    )

    response = invoke_agent(
        prompt,
        agent_type="plan-design",
        model_size="big",
        workflow="plan",
    )

    design_doc = ensure_str_content(response.content)

    console.print("[green]Design document generated.[/green]")

    return {
        **state,
        "design_doc": design_doc,
        "current_stage": "refine",
    }


def write_and_commit_design(state: PlanState) -> PlanState:
    """Write the design document to file and commit to git."""
    console = Console()
    plan_path = state["plan_path"]
    plan_name = state["plan_name"]
    iteration = state["iteration"]

    # Write the design document
    Path(plan_path).write_text(state["design_doc"] or "")

    # Determine commit message based on stage
    if iteration == 0:
        commit_msg = f"plan({plan_name}): Initial design document created"
    else:
        commit_msg = f"plan({plan_name}): Refined design (iteration {iteration})"

    # Commit to git
    commit_plan(plan_path, commit_msg)

    console.print(f"[green]Design document written to: {plan_path}[/green]")

    return state


def prompt_for_refinement(state: PlanState) -> PlanState:
    """Prompt user to approve or provide refinement query."""
    console = Console()

    console.print(f"\n[cyan]Design document: {state['plan_path']}[/cyan]")
    console.print("[cyan]Enter 'y' to approve, or type your refinement request:[/cyan]")

    while True:
        try:
            user_input = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Workflow cancelled.[/yellow]")
            return {**state, "user_approved": False, "failure_reason": "User cancelled"}

        if user_input.lower() in ("y", "yes", "approve", "done"):
            return {**state, "user_approved": True, "refinement_query": None}
        elif user_input:
            return {
                **state,
                "user_approved": False,
                "refinement_query": user_input,
                "iteration": state["iteration"] + 1,
            }
        else:
            console.print(
                "[yellow]Please enter 'y' to approve or a refinement request[/yellow]"
            )


def refine_design(state: PlanState) -> PlanState:
    """Refine the design document based on user feedback."""
    console = Console()
    console.print(f"\n[cyan]Refining design (iteration {state['iteration']})...[/cyan]")

    prompt = REFINE_PROMPT.format(
        design_doc=state["design_doc"],
        refinement_query=state["refinement_query"],
    )

    response = invoke_agent(
        prompt,
        agent_type="plan-refine",
        model_size="big",
        iteration=state["iteration"],
        workflow="plan",
    )

    design_doc = ensure_str_content(response.content)

    console.print("[green]Design refined.[/green]")

    return {
        **state,
        "design_doc": design_doc,
    }


def handle_success(state: PlanState) -> PlanState:
    """Handle successful workflow completion."""
    console = Console()
    plan_path = state["plan_path"]
    plan_name = state["plan_name"]

    # Final commit marking approval
    commit_plan(plan_path, f"plan({plan_name}): Design approved by user")

    console.print(
        f"\n[green]Design document approved and saved to: {plan_path}[/green]"
    )

    return state


def handle_failure(state: PlanState) -> PlanState:
    """Handle workflow failure."""
    console = Console()
    reason = state.get("failure_reason", "Unknown error")
    console.print(f"\n[red]Plan workflow failed: {reason}[/red]")

    return state
