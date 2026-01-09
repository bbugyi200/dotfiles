"""Main PlanWorkflow class for creating design documents."""

from typing import Any

from langgraph.graph import END, START, StateGraph
from rich.console import Console
from shared_utils import LANGGRAPH_RECURSION_LIMIT
from workflow_base import BaseWorkflow

from .nodes import (
    generate_design,
    generate_qa,
    generate_sections,
    handle_failure,
    handle_success,
    initialize_plan_workflow,
    prompt_for_refinement,
    refine_design,
    write_and_commit_design,
)
from .state import PlanState


class PlanWorkflow(BaseWorkflow):
    """A workflow for creating design documents through iterative AI assistance."""

    def __init__(
        self,
        name: str,
        query: str,
        sections_input: str | None = None,
        qa_input: str | None = None,
        design_input: str | None = None,
    ) -> None:
        """Initialize the plan workflow.

        Args:
            name: Name for the plan (becomes filename ~/.gai/plans/<name>.md)
            query: User query describing the feature to design
            sections_input: Optional pre-provided section names
            qa_input: Optional pre-provided Q&A content
            design_input: Optional pre-provided initial design
        """
        self._name = name
        self._query = query
        self._sections_input = sections_input
        self._qa_input = qa_input
        self._design_input = design_input

    @property
    def name(self) -> str:
        """Return the name of this workflow."""
        return "plan"

    @property
    def description(self) -> str:
        """Return a description of what this workflow does."""
        return "Create a design document through iterative AI assistance"

    def create_workflow(self) -> Any:
        """Create and return the LangGraph workflow."""
        workflow = StateGraph(PlanState)

        # Add nodes
        workflow.add_node("initialize", initialize_plan_workflow)
        workflow.add_node("generate_sections", generate_sections)
        workflow.add_node("generate_qa", generate_qa)
        workflow.add_node("generate_design", generate_design)
        workflow.add_node("write_and_commit", write_and_commit_design)
        workflow.add_node("prompt_for_refinement", prompt_for_refinement)
        workflow.add_node("refine_design", refine_design)
        workflow.add_node("success", handle_success)
        workflow.add_node("failure", handle_failure)

        # Add edges - linear flow for initial generation
        workflow.add_edge(START, "initialize")
        workflow.add_edge("initialize", "generate_sections")
        workflow.add_edge("generate_sections", "generate_qa")
        workflow.add_edge("generate_qa", "generate_design")
        workflow.add_edge("generate_design", "write_and_commit")
        workflow.add_edge("write_and_commit", "prompt_for_refinement")

        # Conditional edge for refinement loop
        workflow.add_conditional_edges(
            "prompt_for_refinement",
            self._should_continue_refinement,
            {
                "approved": "success",
                "refine": "refine_design",
                "failure": "failure",
            },
        )

        # After refinement, write and loop back to prompt
        workflow.add_edge("refine_design", "write_and_commit")

        # Terminal nodes
        workflow.add_edge("success", END)
        workflow.add_edge("failure", END)

        return workflow.compile()

    def _should_continue_refinement(self, state: PlanState) -> str:
        """Determine the next step after prompting for refinement."""
        if state.get("failure_reason"):
            return "failure"
        if state.get("user_approved"):
            return "approved"
        return "refine"

    def run(self) -> bool:
        """Run the workflow and return True if successful, False otherwise."""
        console = Console()

        try:
            # Create and run the workflow
            app = self.create_workflow()

            initial_state: PlanState = {
                "plan_name": self._name,
                "user_query": self._query,
                "plan_path": "",  # Set during initialization
                "sections": self._sections_input,
                "qa_content": self._qa_input,
                "design_doc": self._design_input,
                "sections_from_cli": self._sections_input is not None,
                "qa_from_cli": self._qa_input is not None,
                "design_from_cli": self._design_input is not None,
                "refinement_query": None,
                "user_approved": False,
                "current_stage": "initialize",
                "iteration": 0,
                "failure_reason": None,
            }

            final_state = app.invoke(
                initial_state, config={"recursion_limit": LANGGRAPH_RECURSION_LIMIT}
            )

            return final_state.get("user_approved", False)

        except KeyboardInterrupt:
            console.print("\n[yellow]Workflow cancelled by user[/yellow]")
            return False
        except Exception as e:
            console.print(f"\n[red]Error running plan workflow: {e}[/red]")
            return False
