import os
import sys
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from langgraph.graph import END, START, StateGraph
from shared_utils import LANGGRAPH_RECURSION_LIMIT
from workflow_base import BaseWorkflow

from .agents import (
    run_context_agent,
    run_editor_agent,
    run_judge_agent,
    run_test,
    run_verification_agent,
)
from .state import FixTestsState
from .workflow_nodes import (
    handle_failure,
    handle_judge_result,
    handle_success,
    initialize_fix_tests_workflow,
    restart_workflow_after_judge,
    should_continue_workflow,
    should_continue_verification,
)


class FixTestsWorkflow(BaseWorkflow):
    """A workflow for fixing failing tests using planning, editor, and research agents with persistent lessons and research logs."""

    def __init__(
        self,
        test_cmd: str,
        test_output_file: str,
        user_instructions_file: Optional[str] = None,
        max_iterations: int = 10,
        max_judges: int = 3,
        no_human_approval: bool = False,
        comment_out_lines: bool = False,
    ):
        self.test_cmd = test_cmd
        self.test_output_file = test_output_file
        self.user_instructions_file = user_instructions_file
        self.max_iterations = max_iterations
        self.max_judges = max_judges
        self.no_human_approval = no_human_approval
        self.comment_out_lines = comment_out_lines

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
        workflow.add_node("run_verification", run_verification_agent)
        workflow.add_node("run_test", run_test)
        workflow.add_node("run_context", run_context_agent)
        workflow.add_node("run_judge", run_judge_agent)
        workflow.add_node("restart_workflow", restart_workflow_after_judge)
        workflow.add_node("success", handle_success)
        workflow.add_node("failure", handle_failure)

        # Add edges
        workflow.add_edge(START, "initialize")
        workflow.add_edge("run_editor", "run_verification")

        # Handle initialization failure
        workflow.add_conditional_edges(
            "initialize",
            lambda state: "failure" if state.get("failure_reason") else "continue",
            {"failure": "failure", "continue": "run_context"},
        )

        # Main workflow control
        workflow.add_conditional_edges(
            "run_test",
            should_continue_workflow,
            {
                "success": "success",
                "continue": "run_context",
                "run_judge": "run_judge",
            },
        )

        # Verification agent control
        workflow.add_conditional_edges(
            "run_verification",
            should_continue_verification,
            {
                "verification_passed": "run_test",
                "retry_editor": "run_editor",
                "run_judge": "run_judge",
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
                "run_judge": "run_judge",
            },
        )

        # Judge agent control
        workflow.add_conditional_edges(
            "run_judge",
            handle_judge_result,
            {
                "failure": "failure",
                "restart_workflow": "restart_workflow",
            },
        )

        # Restart workflow control
        workflow.add_conditional_edges(
            "restart_workflow",
            should_continue_workflow,
            {
                "success": "success",
                "failure": "failure",
                "run_judge": "run_judge",
            },
        )

        workflow.add_edge("success", END)
        workflow.add_edge("failure", END)

        return workflow.compile()

    def run(self) -> bool:
        """Run the workflow and return True if successful, False otherwise."""
        if not os.path.exists(self.test_output_file):
            print(f"Error: Test output file '{self.test_output_file}' does not exist")
            return False

        # Validate requirements file if provided
        if self.user_instructions_file and not os.path.exists(
            self.user_instructions_file
        ):
            print(
                f"Error: User instructions file '{self.user_instructions_file}' does not exist"
            )
            return False

        # Create and run the workflow
        app = self.create_workflow()

        initial_state: FixTestsState = {
            "test_cmd": self.test_cmd,
            "test_output_file": self.test_output_file,
            "user_instructions_file": self.user_instructions_file,
            "artifacts_dir": "",
            "current_iteration": 1,
            "max_iterations": self.max_iterations,
            "current_judge_iteration": 1,
            "max_judges": self.max_judges,
            "test_passed": False,
            "failure_reason": None,
            "requirements_exists": False,
            "research_exists": False,
            "todos_created": False,
            "research_updated": False,
            "context_agent_retries": 0,
            "max_context_retries": 3,
            "judge_applied_changes": 0,
            "no_human_approval": self.no_human_approval,
            "comment_out_lines": self.comment_out_lines,
            "verification_retries": 0,
            "max_verification_retries": 3,
            "verification_passed": False,
            "needs_editor_retry": False,
            "messages": [],
        }

        try:
            final_state = app.invoke(
                initial_state, config={"recursion_limit": LANGGRAPH_RECURSION_LIMIT}
            )

            # If workflow failed and not in comment-out mode, try with comment-out mode
            if not final_state["test_passed"] and not self.comment_out_lines:
                failure_reason = final_state.get("failure_reason", "")

                # Check if failure was due to max iterations/judges or user rejection
                should_retry_with_comment_out = (
                    "Maximum iterations" in failure_reason
                    or "Maximum judge iterations" in failure_reason
                    or "User declined to apply" in failure_reason
                    or "judge's selected changes" in failure_reason
                )

                if should_retry_with_comment_out:
                    print("\n" + "=" * 80)
                    print("🔄 RETRYING WITH COMMENT-OUT STRATEGY")
                    print("=" * 80)
                    print("The standard fix-tests workflow was unsuccessful.")
                    print(
                        "Automatically retrying with comment-out strategy (-C option)..."
                    )
                    print("=" * 80 + "\n")

                    # Create new workflow with comment-out strategy enabled
                    comment_out_workflow = FixTestsWorkflow(
                        self.test_cmd,
                        self.test_output_file,
                        self.user_instructions_file,
                        self.max_iterations,  # Use same max iterations
                        self.max_judges,  # Use same max judges
                        self.no_human_approval,
                        comment_out_lines=True,  # Enable comment-out strategy
                    )

                    return comment_out_workflow.run()

            return final_state["test_passed"]
        except Exception as e:
            print(f"Error running fix-tests workflow: {e}")
            return False
