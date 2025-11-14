"""Main workflow class for new-failing-tests workflow."""

import os
import sys
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from langgraph.graph import END, START, StateGraph
from shared_utils import LANGGRAPH_RECURSION_LIMIT, finalize_gai_log
from workflow_base import BaseWorkflow

from .agents import run_test_coder_agent
from .state import NewFailingTestState
from .workflow_nodes import (
    handle_failure,
    handle_success,
    initialize_new_failing_test_workflow,
    verify_tests_fail,
    write_test_coder_to_log,
)


class NewFailingTestWorkflow(BaseWorkflow):
    """A workflow for adding failing tests using TDD - adds failing tests before implementing the feature."""

    def __init__(
        self,
        project_name: str,
        changespec_text: str,
        test_targets: list[str],
        context_file_directory: str | None = None,
        research_file: str | None = None,
        guidance: str | None = None,
    ) -> None:
        """
        Initialize the new-failing-tests workflow.

        Args:
            project_name: Name of the project (used for clsurf query and log message)
            changespec_text: The ChangeSpec text read from STDIN
            test_targets: List of test targets to run (from ChangeSpec TEST TARGETS field)
            context_file_directory: Optional file or directory containing markdown context
            research_file: Optional path to research file (from work-project workflow)
            guidance: Optional guidance text to append to the agent prompt
        """
        self.project_name = project_name
        self.changespec_text = changespec_text
        self.test_targets = test_targets
        self.context_file_directory = context_file_directory
        self.research_file = research_file
        self.guidance = guidance
        self.final_state: NewFailingTestState | None = None

    @property
    def name(self) -> str:
        """Return the workflow name."""
        return "new-failing-tests"

    @property
    def description(self) -> str:
        """Return the workflow description."""
        return "Add failing tests using TDD - adds failing tests before implementing the feature"

    def create_workflow(self) -> Any:
        """Create and return the LangGraph workflow."""
        workflow = StateGraph(NewFailingTestState)

        # Add nodes
        workflow.add_node("initialize", initialize_new_failing_test_workflow)
        workflow.add_node("run_test_coder", run_test_coder_agent)
        workflow.add_node("write_test_coder_to_log", write_test_coder_to_log)
        workflow.add_node("verify_tests_fail", verify_tests_fail)
        # NOTE: CL creation has been moved to work-project workflow
        # workflow.add_node("create_cl", create_cl_commit)
        workflow.add_node("success", handle_success)
        workflow.add_node("failure", handle_failure)

        # Add edges
        workflow.add_edge(START, "initialize")

        # Handle initialization failure
        workflow.add_conditional_edges(
            "initialize",
            lambda state: (
                "failure" if state.get("failure_reason") else "run_test_coder"
            ),
            {
                "failure": "failure",
                "run_test_coder": "run_test_coder",
            },
        )

        # Test coder agent flow
        workflow.add_edge("run_test_coder", "write_test_coder_to_log")

        # After test coder, check if successful
        workflow.add_conditional_edges(
            "write_test_coder_to_log",
            lambda state: (
                "verify_tests_fail" if state.get("test_coder_success") else "failure"
            ),
            {"verify_tests_fail": "verify_tests_fail", "failure": "failure"},
        )

        # After verifying tests fail, succeed (CL creation moved to work-project workflow)
        workflow.add_conditional_edges(
            "verify_tests_fail",
            lambda state: (
                "success" if state.get("tests_failed_as_expected") else "failure"
            ),
            {"success": "success", "failure": "failure"},
        )

        workflow.add_edge("success", END)
        workflow.add_edge("failure", END)

        return workflow.compile()

    def run(self) -> bool:
        """Run the workflow and return True if successful, False otherwise."""
        try:
            # Create and run the workflow
            app = self.create_workflow()

            initial_state: NewFailingTestState = {
                "project_name": self.project_name,
                "context_file_directory": self.context_file_directory,
                "changespec_text": self.changespec_text,
                "research_file": self.research_file,
                "guidance": self.guidance,
                "test_targets": self.test_targets,  # Passed in from ChangeSpec
                "cl_name": "",  # Will be set during initialization
                "cl_description": "",  # Will be set during initialization
                "cl_parent": None,  # Will be set during initialization
                "cl_status": "",  # Will be set during initialization
                "artifacts_dir": "",
                "workflow_tag": "",
                "clsurf_output_file": None,
                "log_file": "",
                "cl_description_file": None,  # Will be set during initialization
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
                finalize_gai_log(
                    artifacts_dir, "new-failing-tests", workflow_tag, success
                )

            return success
        except Exception as e:
            print(f"Error running new-failing-tests workflow: {e}")
            return False
