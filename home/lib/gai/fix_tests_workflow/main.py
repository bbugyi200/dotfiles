import os
import signal
import sys
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from langgraph.graph import END, START, StateGraph
from shared_utils import LANGGRAPH_RECURSION_LIMIT, run_shell_command
from workflow_base import BaseWorkflow

from .agents import (
    run_context_agent,
    run_editor_agent,
    run_test,
    run_verification_agent,
    run_parallel_research_agents,
    run_judge_agent,
    run_research_agents,
    run_synthesis_agent,
    run_test_failure_comparison_agent,
)
from .state import FixTestsState
from .workflow_nodes import (
    backup_and_update_artifacts_after_test_failure,
    handle_failure,
    handle_success,
    initialize_fix_tests_workflow,
    should_continue_workflow,
    should_continue_verification,
)


class FixTestsWorkflow(BaseWorkflow):
    """A workflow for fixing failing tests using research agents, planner agents, and editor agents with persistent lessons and research logs."""

    def __init__(
        self,
        test_cmd: str,
        test_output_file: str,
        user_instructions_file: Optional[str] = None,
        max_iterations: int = 10,
        num_parallel_research_agents: int = 3,
    ):
        self.test_cmd = test_cmd
        self.test_output_file = test_output_file
        self.user_instructions_file = user_instructions_file
        self.max_iterations = max_iterations
        self.num_parallel_research_agents = num_parallel_research_agents
        self._verification_succeeded = False
        self._safe_to_unamend = False
        self._original_sigint_handler = None

    @property
    def name(self) -> str:
        return "fix-tests"

    @property
    def description(self) -> str:
        return "Fix failing tests using planning, editor, and research agents with persistent lessons and research logs"

    def _setup_signal_handler(self):
        """Set up signal handler to run hg unamend on Ctrl+C if verification succeeded."""

        def signal_handler(signum, frame):
            print("\n⚠️ Workflow interrupted by user (Ctrl+C)")
            if self._safe_to_unamend:
                print(
                    "🔄 Safe to run unamend (successful amend occurred) - reverting commits..."
                )
                try:
                    result = run_shell_command("hg unamend", capture_output=True)
                    if result.returncode == 0:
                        print("✅ Successfully reverted commits with unamend")
                    else:
                        print(f"⚠️ Warning: unamend failed: {result.stderr}")
                except Exception as e:
                    print(f"⚠️ Warning: Error running unamend: {e}")
            elif self._verification_succeeded:
                print(
                    "⚠️ Cannot safely run unamend - no successful amend recorded or last amend failed"
                )

            # Restore original handler and re-raise
            if self._original_sigint_handler:
                signal.signal(signal.SIGINT, self._original_sigint_handler)
            raise KeyboardInterrupt()

        self._original_sigint_handler = signal.signal(signal.SIGINT, signal_handler)

    def _cleanup_signal_handler(self):
        """Restore the original signal handler."""
        if self._original_sigint_handler:
            signal.signal(signal.SIGINT, self._original_sigint_handler)

    def _mark_verification_succeeded(self):
        """Mark that verification has succeeded at least once."""
        self._verification_succeeded = True

    def _mark_amend_successful(self):
        """Mark that a successful amend has occurred, making unamend safe."""
        self._safe_to_unamend = True

    def create_workflow(self):
        """Create and return the LangGraph workflow."""
        workflow = StateGraph(FixTestsState)

        # Add nodes
        workflow.add_node("initialize", initialize_fix_tests_workflow)
        workflow.add_node("run_editor", run_editor_agent)
        workflow.add_node("run_verification", run_verification_agent)
        workflow.add_node("run_test", run_test)
        workflow.add_node(
            "backup_and_update_artifacts",
            backup_and_update_artifacts_after_test_failure,
        )
        workflow.add_node(
            "run_test_failure_comparison", run_test_failure_comparison_agent
        )
        workflow.add_node("run_research", run_research_agents)
        workflow.add_node("run_synthesis", run_synthesis_agent)
        workflow.add_node("run_parallel_research", run_parallel_research_agents)
        workflow.add_node("run_judge", run_judge_agent)
        workflow.add_node("run_context", run_context_agent)  # Keep as fallback
        workflow.add_node("success", handle_success)
        workflow.add_node("failure", handle_failure)

        # Add edges
        workflow.add_edge(START, "initialize")
        workflow.add_edge("run_editor", "run_verification")

        # Handle initialization failure
        workflow.add_conditional_edges(
            "initialize",
            lambda state: "failure" if state.get("failure_reason") else "continue",
            {"failure": "failure", "continue": "run_research"},
        )

        # Main workflow control
        workflow.add_conditional_edges(
            "run_test",
            should_continue_workflow,
            {
                "success": "success",
                "continue": "backup_and_update_artifacts",
                "failure": "failure",
            },
        )

        # Verification agent control
        workflow.add_conditional_edges(
            "run_verification",
            should_continue_verification,
            {
                "verification_passed": "run_test",
                "retry_editor": "run_editor",
                "failure": "failure",
            },
        )

        # Backup and update artifacts - first run test failure comparison for non-initial iterations
        workflow.add_conditional_edges(
            "backup_and_update_artifacts",
            lambda state: (
                "run_test_failure_comparison"
                if state["current_iteration"] > 1
                else "run_research"
            ),
            {
                "run_test_failure_comparison": "run_test_failure_comparison",
                "run_research": "run_research",
            },
        )

        # Test failure comparison - conditionally run research or skip to existing research
        workflow.add_conditional_edges(
            "run_test_failure_comparison",
            lambda state: (
                "run_research"
                if state.get("meaningful_test_failure_change", True)
                else "run_parallel_research"
            ),
            {
                "run_research": "run_research",
                "run_parallel_research": "run_parallel_research",
            },
        )

        # Research agents proceed to synthesis agent
        workflow.add_edge("run_research", "run_synthesis")

        # Synthesis agent proceeds to parallel planner agents
        workflow.add_edge("run_synthesis", "run_parallel_research")

        # Parallel planner agents always proceed to judge
        workflow.add_edge("run_parallel_research", "run_judge")

        # Judge agent control
        workflow.add_conditional_edges(
            "run_judge",
            should_continue_workflow,
            {
                "failure": "failure",
                "continue": "run_editor",
                "retry_context_agent": "run_context",  # Fallback to single context agent
            },
        )

        # Context agent control (fallback)
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

        # Setup signal handler for Ctrl+C
        self._setup_signal_handler()

        try:
            # Create and run the workflow
            app = self.create_workflow()

            initial_state: FixTestsState = {
                "test_cmd": self.test_cmd,
                "test_output_file": self.test_output_file,
                "user_instructions_file": self.user_instructions_file,
                "artifacts_dir": "",
                "workflow_tag": "",  # Will be set during initialization
                "commit_iteration": 1,
                "current_iteration": 1,
                "max_iterations": self.max_iterations,
                "test_passed": False,
                "failure_reason": None,
                "requirements_exists": False,
                "research_exists": False,
                "todos_created": False,
                "research_updated": False,
                "context_agent_retries": 0,
                "max_context_retries": 3,
                "verification_retries": 0,
                "max_verification_retries": 5,
                "verification_passed": False,
                "needs_editor_retry": False,
                "first_verification_success": False,
                "messages": [],
                "workflow_instance": self,  # Pass workflow instance to state
                "num_parallel_research_agents": self.num_parallel_research_agents,
                "research_agent_plans": [],
                "selected_plan_path": None,
                "judge_agent_retries": 0,
                "max_judge_agent_retries": 3,
                "last_amend_successful": False,
                "safe_to_unamend": False,
                "research_results": None,
                "research_md_created": False,
                "raw_research_created": False,
                "synthesis_completed": False,
                "meaningful_test_failure_change": True,  # Default to True for first iteration
                "comparison_completed": False,
                "distinct_test_outputs": [],  # Start with empty list of distinct test outputs
            }

            final_state = app.invoke(
                initial_state, config={"recursion_limit": LANGGRAPH_RECURSION_LIMIT}
            )

            return final_state["test_passed"]
        except KeyboardInterrupt:
            print("\n❌ Workflow cancelled by user")
            return False
        except Exception as e:
            print(f"Error running fix-tests workflow: {e}")
            return False
        finally:
            # Always cleanup signal handler
            self._cleanup_signal_handler()
