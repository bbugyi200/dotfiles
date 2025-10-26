import os
import sys
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from langgraph.graph import END, START, StateGraph
from shared_utils import LANGGRAPH_RECURSION_LIMIT
from workflow_base import BaseWorkflow

from .agents import run_context_agent, run_editor_agent, run_test
from .state import FixTestsState
from .workflow_nodes import (
    handle_failure,
    handle_success,
    initialize_fix_tests_workflow,
    should_continue_workflow,
)


class FixTestsWorkflow(BaseWorkflow):
    """A workflow for fixing failing tests using planning, editor, and research agents with persistent lessons and research logs."""

    def __init__(
        self,
        test_cmd: str,
        test_output_file: str,
        blackboard_file: Optional[str] = None,
        max_iterations: int = 10,
    ):
        self.test_cmd = test_cmd
        self.test_output_file = test_output_file
        self.blackboard_file = blackboard_file
        self.max_iterations = max_iterations

    @property
    def name(self) -> str:
        return "fix-tests"

    @property
    def description(self) -> str:
        return "Fix failing tests using planning, editor, and research agents with persistent lessons and research logs"

    def create_workflow(self):
        """Create and return the LangGraph workflow."""
        workflow = StateGraph(FixTestsState)

        # Add nodes
        workflow.add_node("initialize", initialize_fix_tests_workflow)
        workflow.add_node("run_editor", run_editor_agent)
        workflow.add_node("run_test", run_test)
        workflow.add_node("run_context", run_context_agent)
        workflow.add_node("success", handle_success)
        workflow.add_node("failure", handle_failure)

        # Add edges
        workflow.add_edge(START, "initialize")
        workflow.add_edge("run_editor", "run_test")

        # Handle initialization failure
        workflow.add_conditional_edges(
            "initialize",
            lambda state: "failure" if state.get("failure_reason") else "continue",
            {"failure": "failure", "continue": "run_editor"},
        )

        # Main workflow control
        workflow.add_conditional_edges(
            "run_test",
            should_continue_workflow,
            {
                "success": "success",
                "continue": "run_context",
            },
        )

        # Context agent control
        workflow.add_conditional_edges(
            "run_context",
            should_continue_workflow,
            {
                "failure": "failure",
                "continue": "run_editor",
                "retry_context_agent": "run_context",
            },
        )

        workflow.add_edge("success", END)
        workflow.add_edge("failure", END)

        return workflow.compile(config={"recursion_limit": LANGGRAPH_RECURSION_LIMIT})

    def run(self) -> bool:
        """Run the workflow and return True if successful, False otherwise."""
        if not os.path.exists(self.test_output_file):
            print(f"Error: Test output file '{self.test_output_file}' does not exist")
            return False

        # Validate blackboard file if provided
        if self.blackboard_file and not os.path.exists(self.blackboard_file):
            print(f"Error: Blackboard file '{self.blackboard_file}' does not exist")
            return False

        # Create and run the workflow
        app = self.create_workflow()

        initial_state: FixTestsState = {
            "test_cmd": self.test_cmd,
            "test_output_file": self.test_output_file,
            "blackboard_file": self.blackboard_file,
            "artifacts_dir": "",
            "current_iteration": 1,
            "max_iterations": self.max_iterations,
            "test_passed": False,
            "failure_reason": None,
            "lessons_exists": False,
            "research_exists": False,
            "context_agent_retries": 0,
            "max_context_retries": 3,
            "messages": [],
        }

        try:
            final_state = app.invoke(initial_state)
            return final_state["test_passed"]
        except Exception as e:
            print(f"Error running fix-tests workflow: {e}")
            return False
