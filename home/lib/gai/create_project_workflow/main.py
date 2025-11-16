"""Main workflow class for create-project workflow."""

import os
import sys
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from langgraph.graph import END, START, StateGraph
from shared_utils import LANGGRAPH_RECURSION_LIMIT, finalize_gai_log
from workflow_base import BaseWorkflow

from .agents import run_planner_agent
from .state import CreateProjectState
from .workflow_nodes import (
    handle_failure,
    handle_success,
    initialize_create_project_workflow,
)


class CreateProjectWorkflow(BaseWorkflow):
    """A workflow for creating project plans with proposed CLs based on design documents and prior work."""

    def __init__(
        self,
        bug_id: str,
        clquery: str,
        design_docs_dir: str,
        filename: str,
        dry_run: bool = False,
    ):
        """
        Initialize the create-project workflow.

        Args:
            bug_id: Bug ID to track this project
            clquery: Critique query for clsurf to analyze prior work
            design_docs_dir: Directory containing markdown design documents
            filename: Filename (basename) for the project. File will be created at ~/.gai/projects/<filename>/<filename>.gp (.gp extension added automatically if not present)
            dry_run: If True, print the project file contents to STDOUT instead of writing to file
        """
        self.bug_id = bug_id
        self.clquery = clquery
        self.design_docs_dir = design_docs_dir
        self.filename = filename
        self.dry_run = dry_run

    @property
    def name(self) -> str:
        """Return the workflow name."""
        return "create-project"

    @property
    def description(self) -> str:
        """Return the workflow description."""
        return "Create a project plan with proposed CLs based on design documents and prior work"

    def create_workflow(self) -> Any:
        """Create and return the LangGraph workflow."""
        workflow = StateGraph(CreateProjectState)

        # Add nodes
        workflow.add_node("initialize", initialize_create_project_workflow)
        workflow.add_node("run_planner", run_planner_agent)
        workflow.add_node("success", handle_success)
        workflow.add_node("failure", handle_failure)

        # Add edges
        workflow.add_edge(START, "initialize")

        # Handle initialization failure
        workflow.add_conditional_edges(
            "initialize",
            lambda state: "failure" if state.get("failure_reason") else "continue",
            {"failure": "failure", "continue": "run_planner"},
        )

        # Handle planner completion
        workflow.add_conditional_edges(
            "run_planner",
            lambda state: "success" if state.get("success") else "failure",
            {"success": "success", "failure": "failure"},
        )

        workflow.add_edge("success", END)
        workflow.add_edge("failure", END)

        return workflow.compile()

    def run(self) -> bool:
        """Run the workflow and return True if successful, False otherwise."""
        # Validate design docs directory exists
        if not os.path.isdir(self.design_docs_dir):
            print(
                f"Error: Design docs directory '{self.design_docs_dir}' does not exist or is not a directory"
            )
            return False

        try:
            # Create and run the workflow
            app = self.create_workflow()

            initial_state: CreateProjectState = {
                "bug_id": self.bug_id,
                "clquery": self.clquery,
                "design_docs_dir": self.design_docs_dir,
                "filename": self.filename,
                "dry_run": self.dry_run,
                "project_name": "",  # Will be set during initialization
                "artifacts_dir": "",
                "workflow_tag": "",
                "clsurf_output_file": None,
                "projects_file": "",
                "success": False,
                "failure_reason": None,
                "messages": [],
                "workflow_instance": self,
            }

            final_state = app.invoke(
                initial_state, config={"recursion_limit": LANGGRAPH_RECURSION_LIMIT}
            )

            success = final_state["success"]

            # Finalize the gai.md log
            workflow_tag = final_state.get("workflow_tag", "UNKNOWN")
            artifacts_dir = final_state.get("artifacts_dir", "")
            if artifacts_dir:
                finalize_gai_log(artifacts_dir, "create-project", workflow_tag, success)

            return success
        except Exception as e:
            print(f"Error running create-project workflow: {e}")
            return False
