"""Main workflow class for new-ez-feature workflow."""

import os
import sys
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from langgraph.graph import END, START, StateGraph
from shared_utils import LANGGRAPH_RECURSION_LIMIT
from workflow_base import BaseWorkflow

from .agents import run_editor_agent
from .state import NewEzFeatureState
from .workflow_nodes import (
    handle_failure,
    handle_success,
    initialize_new_ez_feature_workflow,
)


class NewEzFeatureWorkflow(BaseWorkflow):
    """A workflow for implementing simple changes that do not require tests."""

    def __init__(
        self,
        project_name: str,
        design_docs_dir: str,
        changespec_text: str,
        context_file_directory: str | None = None,
    ) -> None:
        """
        Initialize the new-ez-feature workflow.

        Args:
            project_name: Name of the project
            design_docs_dir: Directory containing markdown design documents
            changespec_text: The ChangeSpec text
            context_file_directory: Optional directory containing additional context files
        """
        self.project_name = project_name
        self.design_docs_dir = design_docs_dir
        self.changespec_text = changespec_text
        self.context_file_directory = context_file_directory
        self.final_state: NewEzFeatureState | None = None

    @property
    def name(self) -> str:
        """Return the workflow name."""
        return "new-ez-feature"

    @property
    def description(self) -> str:
        """Return the workflow description."""
        return "Implement simple changes that do not require tests"

    def create_workflow(self) -> Any:
        """Create and return the LangGraph workflow."""
        workflow = StateGraph(NewEzFeatureState)

        # Add nodes
        workflow.add_node("initialize", initialize_new_ez_feature_workflow)
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

    def get_initial_state(self) -> NewEzFeatureState:
        """Get the initial state for the workflow."""
        return NewEzFeatureState(
            project_name=self.project_name,
            design_docs_dir=self.design_docs_dir,
            changespec_text=self.changespec_text,
            context_file_directory=self.context_file_directory,
            artifacts_dir="",
            workflow_tag="",
            cl_name="",
            cl_description="",
            editor_response=None,
            failure_reason=None,
            success=False,
            messages=[],
            workflow_instance=self,
        )

    def run(self) -> bool:
        """
        Execute the new-ez-feature workflow.

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
