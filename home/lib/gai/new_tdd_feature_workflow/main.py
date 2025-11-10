"""new-tdd-feature workflow implementation."""

import os
import sys
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from langgraph.graph import END, START, StateGraph
from shared_utils import LANGGRAPH_RECURSION_LIMIT
from workflow_base import BaseWorkflow

from .agents import run_implementation_agent, run_test
from .state import NewTddFeatureState
from .workflow_nodes import (
    handle_failure,
    handle_success,
    initialize_workflow,
    should_continue_workflow,
)


class NewTddFeatureWorkflow(BaseWorkflow):
    """A workflow for implementing TDD features based on failing tests."""

    def __init__(
        self,
        test_output_file: str,
        test_targets: str,
        user_instructions_file: str | None = None,
        max_iterations: int = 10,
        context_file_directory: str | None = None,
    ):
        self.test_output_file = test_output_file
        self.test_targets = test_targets
        self.user_instructions_file = user_instructions_file
        self.max_iterations = max_iterations
        self.context_file_directory = context_file_directory

    @property
    def name(self) -> str:
        return "new-tdd-feature"

    @property
    def description(self) -> str:
        return "Implement new features using TDD based on failing tests"

    def create_workflow(self) -> Any:
        """Create and return the LangGraph workflow."""
        workflow = StateGraph(NewTddFeatureState)

        # Add nodes
        workflow.add_node("initialize", initialize_workflow)
        workflow.add_node("run_implementation", run_implementation_agent)
        workflow.add_node("run_test", run_test)
        workflow.add_node("success", handle_success)
        workflow.add_node("failure", handle_failure)

        # Add edges
        workflow.add_edge(START, "initialize")

        # Handle initialization
        workflow.add_conditional_edges(
            "initialize",
            lambda state: "failure" if state.get("failure_reason") else "continue",
            {"failure": "failure", "continue": "run_implementation"},
        )

        # After implementation, run tests
        workflow.add_edge("run_implementation", "run_test")

        # After tests, check if we should continue or complete
        workflow.add_conditional_edges(
            "run_test",
            should_continue_workflow,
            {
                "success": "success",
                "failure": "failure",
                "continue": "run_implementation",
            },
        )

        # Terminal states
        workflow.add_edge("success", END)
        workflow.add_edge("failure", END)

        return workflow.compile()

    def run(self) -> bool:
        """Run the workflow and return success/failure."""
        app = self.create_workflow()

        initial_state: NewTddFeatureState = {
            "test_output_file": self.test_output_file,
            "test_targets": self.test_targets,
            "user_instructions_file": self.user_instructions_file,
            "context_file_directory": self.context_file_directory,
            "artifacts_dir": "",  # Will be set by initialize
            "current_iteration": 0,
            "max_iterations": self.max_iterations,
            "test_passed": False,
            "failure_reason": None,
            "messages": [],
            "workflow_instance": self,
            "workflow_tag": "",  # Will be set by initialize
        }

        final_state = app.invoke(
            initial_state, config={"recursion_limit": LANGGRAPH_RECURSION_LIMIT}
        )

        return not final_state.get("failure_reason")
