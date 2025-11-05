"""Main workflow class for new-change workflow."""

import os
import sys
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from langgraph.graph import END, START, StateGraph
from shared_utils import LANGGRAPH_RECURSION_LIMIT
from workflow_base import BaseWorkflow

from .agents import run_editor_agent
from .state import NewChangeState
from .workflow_nodes import (
    handle_failure,
    handle_success,
    initialize_new_change_workflow,
)


class NewChangeWorkflow(BaseWorkflow):
    """A workflow for implementing changes that do not require tests."""

    def __init__(
        self,
        project_name: str,
        design_docs_dir: str,
        changespec_text: str,
        research_file: str | None = None,
    ) -> None:
        """
        Initialize the new-change workflow.

        Args:
            project_name: Name of the project
            design_docs_dir: Directory containing markdown design documents
            changespec_text: The ChangeSpec text
            research_file: Optional path to research file (from work-projects workflow)
        """
        self.project_name = project_name
        self.design_docs_dir = design_docs_dir
        self.changespec_text = changespec_text
        self.research_file = research_file
        self.final_state: NewChangeState | None = None

    @property
    def name(self) -> str:
        """Return the workflow name."""
        return "new-change"

    @property
    def description(self) -> str:
        """Return the workflow description."""
        return "Implement changes that do not require tests"

    def create_workflow(self) -> Any:
        """Create and return the LangGraph workflow."""
        workflow = StateGraph(NewChangeState)

        # Add nodes
        workflow.add_node("initialize", initialize_new_change_workflow)
        workflow.add_node("run_editor", run_editor_agent)
        workflow.add_node("success", handle_success)
        workflow.add_node("failure", handle_failure)

        # Add edges
        workflow.add_edge(START, "initialize")

        # Handle initialization failure
        workflow.add_conditional_edges(
            "initialize",
            lambda state: "failure" if state.get("failure_reason") else "run_editor",
            {
                "failure": "failure",
                "run_editor": "run_editor",
            },
        )

        # Editor agent flow
        workflow.add_conditional_edges(
            "run_editor",
            lambda state: "failure" if state.get("failure_reason") else "success",
            {
                "failure": "failure",
                "success": "success",
            },
        )

        # Terminal nodes
        workflow.add_edge("success", END)
        workflow.add_edge("failure", END)

        return workflow.compile()

    def get_initial_state(self) -> NewChangeState:
        """Get the initial state for the workflow."""
        return NewChangeState(
            project_name=self.project_name,
            design_docs_dir=self.design_docs_dir,
            changespec_text=self.changespec_text,
            research_file=self.research_file,
        )

    def run(self) -> bool:
        """
        Execute the new-change workflow.

        Returns:
            bool: True if successful, False otherwise
        """
        workflow = self.create_workflow()
        initial_state = self.get_initial_state()

        try:
            # Run the workflow
            final_state = workflow.invoke(
                initial_state,
                {"recursion_limit": LANGGRAPH_RECURSION_LIMIT},
            )

            # Store final state
            self.final_state = final_state

            # Return success status
            return final_state.get("success", False) and not final_state.get(
                "failure_reason"
            )

        except KeyboardInterrupt:
            print("\n\nWorkflow interrupted by user (Ctrl+C)")
            return False
        except Exception as e:
            print(f"Workflow execution failed: {e}")
            return False
