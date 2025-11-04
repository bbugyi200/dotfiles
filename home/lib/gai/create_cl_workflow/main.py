"""Main workflow class for create-cl workflow."""

import os
import sys
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from langgraph.graph import END, START, StateGraph
from shared_utils import LANGGRAPH_RECURSION_LIMIT, finalize_gai_log
from workflow_base import BaseWorkflow

from .agents import run_coder_agent, run_research_agents
from .state import CreateCLState
from .workflow_nodes import (
    create_cl_commit,
    handle_failure,
    handle_success,
    initialize_create_cl_workflow,
    write_coder_to_log,
    write_research_to_log,
)


class CreateCLWorkflow(BaseWorkflow):
    """A workflow for creating a CL from a ChangeSpec with deep research and implementation."""

    def __init__(
        self, project_name: str, design_docs_dir: str, changespec_text: str
    ) -> None:
        """
        Initialize the create-cl workflow.

        Args:
            project_name: Name of the project (used for clsurf query and CL commit message)
            design_docs_dir: Directory containing markdown design documents
            changespec_text: The ChangeSpec text read from STDIN
        """
        self.project_name = project_name
        self.design_docs_dir = design_docs_dir
        self.changespec_text = changespec_text
        self.final_state: CreateCLState | None = None

    @property
    def name(self) -> str:
        """Return the workflow name."""
        return "create-cl"

    @property
    def description(self) -> str:
        """Return the workflow description."""
        return "Create a CL from a ChangeSpec with deep research and implementation"

    def create_workflow(self) -> Any:
        """Create and return the LangGraph workflow."""
        workflow = StateGraph(CreateCLState)

        # Add nodes
        workflow.add_node("initialize", initialize_create_cl_workflow)
        workflow.add_node("run_research", run_research_agents)
        workflow.add_node("write_research_to_log", write_research_to_log)
        workflow.add_node("run_coder", run_coder_agent)
        workflow.add_node("write_coder_to_log", write_coder_to_log)
        workflow.add_node("create_cl", create_cl_commit)
        workflow.add_node("success", handle_success)
        workflow.add_node("failure", handle_failure)

        # Add edges
        workflow.add_edge(START, "initialize")

        # Handle initialization failure
        workflow.add_conditional_edges(
            "initialize",
            lambda state: "failure" if state.get("failure_reason") else "continue",
            {"failure": "failure", "continue": "run_research"},
        )

        # Research agents flow
        workflow.add_edge("run_research", "write_research_to_log")
        workflow.add_edge("write_research_to_log", "run_coder")

        # Coder agent flow
        workflow.add_edge("run_coder", "write_coder_to_log")

        # After writing coder output, decide whether to create CL
        workflow.add_conditional_edges(
            "write_coder_to_log",
            lambda state: "create_cl" if state.get("coder_success") else "failure",
            {"create_cl": "create_cl", "failure": "failure"},
        )

        # CL creation flow
        workflow.add_conditional_edges(
            "create_cl",
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

            initial_state: CreateCLState = {
                "project_name": self.project_name,
                "design_docs_dir": self.design_docs_dir,
                "changespec_text": self.changespec_text,
                "cl_name": "",  # Will be set during initialization
                "cl_description": "",  # Will be set during initialization
                "cl_parent": None,  # Will be set during initialization
                "cl_status": "",  # Will be set during initialization
                "artifacts_dir": "",
                "workflow_tag": "",
                "clsurf_output_file": None,
                "log_file": "",
                "research_results": None,
                "coder_response": None,
                "coder_success": False,
                "cl_id": None,  # Will be set after successful commit
                "success": False,
                "failure_reason": None,
                "messages": [],
                "workflow_instance": self,
            }

            final_state = app.invoke(
                initial_state, config={"recursion_limit": LANGGRAPH_RECURSION_LIMIT}
            )

            # Store final state for external access
            self.final_state = final_state

            success = final_state["success"]

            # Finalize the gai.md log
            workflow_tag = final_state.get("workflow_tag", "UNKNOWN")
            artifacts_dir = final_state.get("artifacts_dir", "")
            if artifacts_dir:
                finalize_gai_log(artifacts_dir, "create-cl", workflow_tag, success)

            return success
        except Exception as e:
            print(f"Error running create-cl workflow: {e}")
            return False
