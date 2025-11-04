"""Main workflow class for pre-mail-cl workflow."""

import os
import sys
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from langgraph.graph import END, START, StateGraph
from shared_utils import LANGGRAPH_RECURSION_LIMIT, finalize_gai_log
from workflow_base import BaseWorkflow

from .agents import run_feature_coder_agent, run_research_agents
from .state import PreMailCLState
from .workflow_nodes import (
    amend_cl,
    handle_failure,
    handle_success,
    initialize_pre_mail_cl_workflow,
    verify_tests_pass,
    write_feature_coder_to_log,
    write_research_to_log,
)


class PreMailCLWorkflow(BaseWorkflow):
    """A workflow for implementing features to make tests pass and amending the CL."""

    def __init__(
        self,
        project_name: str,
        design_docs_dir: str,
        changespec_text: str,
        cl_number: str,
        test_output_file: str,
    ) -> None:
        """
        Initialize the pre-mail-cl workflow.

        Args:
            project_name: Name of the project (used for clsurf query and CL commit message)
            design_docs_dir: Directory containing markdown design documents
            changespec_text: The ChangeSpec text
            cl_number: The CL number created by create-test-cl
            test_output_file: Path to file containing trimmed test output
        """
        self.project_name = project_name
        self.design_docs_dir = design_docs_dir
        self.changespec_text = changespec_text
        self.cl_number = cl_number
        self.test_output_file = test_output_file
        self.final_state: PreMailCLState | None = None

    @property
    def name(self) -> str:
        """Return the workflow name."""
        return "pre-mail-cl"

    @property
    def description(self) -> str:
        """Return the workflow description."""
        return "Implement features to make tests pass and amend the CL"

    def create_workflow(self) -> Any:
        """Create and return the LangGraph workflow."""
        workflow = StateGraph(PreMailCLState)

        # Add nodes
        workflow.add_node("initialize", initialize_pre_mail_cl_workflow)
        workflow.add_node("run_research", run_research_agents)
        workflow.add_node("write_research_to_log", write_research_to_log)
        workflow.add_node("run_feature_coder", run_feature_coder_agent)
        workflow.add_node("write_feature_coder_to_log", write_feature_coder_to_log)
        workflow.add_node("verify_tests_pass", verify_tests_pass)
        workflow.add_node("amend_cl", amend_cl)
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
        workflow.add_edge("write_research_to_log", "run_feature_coder")

        # Feature coder agent flow
        workflow.add_edge("run_feature_coder", "write_feature_coder_to_log")
        workflow.add_edge("write_feature_coder_to_log", "verify_tests_pass")

        # After verifying tests pass, decide whether to amend CL
        workflow.add_conditional_edges(
            "verify_tests_pass",
            lambda state: "amend_cl" if state.get("tests_passed") else "failure",
            {"amend_cl": "amend_cl", "failure": "failure"},
        )

        # CL amendment flow
        workflow.add_conditional_edges(
            "amend_cl",
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

        # Validate test output file exists
        if not os.path.isfile(self.test_output_file):
            print(f"Error: Test output file '{self.test_output_file}' does not exist")
            return False

        try:
            # Create and run the workflow
            app = self.create_workflow()

            initial_state: PreMailCLState = {
                "project_name": self.project_name,
                "design_docs_dir": self.design_docs_dir,
                "changespec_text": self.changespec_text,
                "cl_number": self.cl_number,
                "test_output_file": self.test_output_file,
                "cl_name": "",  # Will be set during initialization
                "cl_description": "",  # Will be set during initialization
                "cl_parent": None,  # Will be set during initialization
                "cl_status": "",  # Will be set during initialization
                "test_output_content": "",  # Will be set during initialization
                "artifacts_dir": "",
                "workflow_tag": "",
                "clsurf_output_file": None,
                "log_file": "",
                "research_results": None,
                "feature_coder_response": None,
                "feature_coder_success": False,
                "tests_passed": False,
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
                finalize_gai_log(artifacts_dir, "pre-mail-cl", workflow_tag, success)

            return success
        except Exception as e:
            print(f"Error running pre-mail-cl workflow: {e}")
            return False
