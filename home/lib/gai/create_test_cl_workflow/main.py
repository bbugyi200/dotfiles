"""Main workflow class for create-test-cl workflow."""

import os
import sys
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from langgraph.graph import END, START, StateGraph
from shared_utils import LANGGRAPH_RECURSION_LIMIT, finalize_gai_log
from workflow_base import BaseWorkflow

from .agents import run_research_agents, run_test_coder_agent
from .state import CreateTestCLState
from .workflow_nodes import (
    create_cl_commit,
    handle_failure,
    handle_success,
    initialize_create_test_cl_workflow,
    verify_tests_fail,
    write_research_to_log,
    write_test_coder_to_log,
)


class CreateTestCLWorkflow(BaseWorkflow):
    """A workflow for creating a test CL using TDD - adds failing tests before implementing the feature."""

    def __init__(
        self,
        project_name: str,
        design_docs_dir: str,
        changespec_text: str,
        research_file: str | None = None,
    ) -> None:
        """
        Initialize the create-test-cl workflow.

        Args:
            project_name: Name of the project (used for clsurf query and CL commit message)
            design_docs_dir: Directory containing markdown design documents
            changespec_text: The ChangeSpec text read from STDIN
            research_file: Optional path to research file (from work-project workflow)
        """
        self.project_name = project_name
        self.design_docs_dir = design_docs_dir
        self.changespec_text = changespec_text
        self.research_file = research_file
        self.final_state: CreateTestCLState | None = None

    @property
    def name(self) -> str:
        """Return the workflow name."""
        return "create-test-cl"

    @property
    def description(self) -> str:
        """Return the workflow description."""
        return "Create a test CL using TDD - adds failing tests before implementing the feature"

    def create_workflow(self) -> Any:
        """Create and return the LangGraph workflow."""
        workflow = StateGraph(CreateTestCLState)

        # Add nodes
        workflow.add_node("initialize", initialize_create_test_cl_workflow)
        workflow.add_node("run_research", run_research_agents)
        workflow.add_node("write_research_to_log", write_research_to_log)
        workflow.add_node("run_test_coder", run_test_coder_agent)
        workflow.add_node("write_test_coder_to_log", write_test_coder_to_log)
        workflow.add_node("verify_tests_fail", verify_tests_fail)
        workflow.add_node("create_cl", create_cl_commit)
        workflow.add_node("success", handle_success)
        workflow.add_node("failure", handle_failure)

        # Add edges
        workflow.add_edge(START, "initialize")

        # Handle initialization failure and conditionally skip research if file provided
        workflow.add_conditional_edges(
            "initialize",
            lambda state: (
                "failure"
                if state.get("failure_reason")
                else (
                    "run_test_coder" if state.get("research_file") else "run_research"
                )
            ),
            {
                "failure": "failure",
                "run_research": "run_research",
                "run_test_coder": "run_test_coder",
            },
        )

        # Research agents flow (only if no research_file provided)
        workflow.add_edge("run_research", "write_research_to_log")
        workflow.add_edge("write_research_to_log", "run_test_coder")

        # Test coder agent flow
        workflow.add_edge("run_test_coder", "write_test_coder_to_log")
        workflow.add_edge("write_test_coder_to_log", "verify_tests_fail")

        # After verifying tests fail, decide whether to create CL
        workflow.add_conditional_edges(
            "verify_tests_fail",
            lambda state: (
                "create_cl" if state.get("tests_failed_as_expected") else "failure"
            ),
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

            initial_state: CreateTestCLState = {
                "project_name": self.project_name,
                "design_docs_dir": self.design_docs_dir,
                "changespec_text": self.changespec_text,
                "research_file": self.research_file,
                "cl_name": "",  # Will be set during initialization
                "cl_description": "",  # Will be set during initialization
                "cl_parent": None,  # Will be set during initialization
                "cl_status": "",  # Will be set during initialization
                "artifacts_dir": "",
                "workflow_tag": "",
                "clsurf_output_file": None,
                "log_file": "",
                "research_results": None,
                "test_coder_response": None,
                "test_coder_success": False,
                "test_cmd": None,  # Will be set during initialization
                "tests_failed_as_expected": False,
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
                finalize_gai_log(artifacts_dir, "create-test-cl", workflow_tag, success)

            return success
        except Exception as e:
            print(f"Error running create-test-cl workflow: {e}")
            return False
