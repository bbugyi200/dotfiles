import hashlib
import os
from typing import List, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from .blackboard import BlackboardManager
from .agents import PlanningAgent, EditorAgent, ResearchAgent
from shared_utils import run_shell_command, run_bam_command
from workflow_base import BaseWorkflow


class FixTestsState(TypedDict):
    test_cmd: str
    test_output_file: str
    branch_name: str
    test_cmd_hash: str
    blackboard_dir: str
    blackboard_manager: BlackboardManager
    current_iteration: int
    max_iterations: int
    test_passed: bool
    should_stop: bool
    stop_reason: Optional[str]
    messages: List[HumanMessage | AIMessage]


def generate_test_cmd_hash(test_cmd: str) -> str:
    """Generate a 7-character alphanumeric hash of the test command."""
    return hashlib.sha256(test_cmd.encode()).hexdigest()[:7]


def get_branch_name() -> str:
    """Get the current branch name using the branch_name command."""
    result = run_shell_command("branch_name", capture_output=True)
    if result.returncode != 0:
        # Fallback to 'default' if branch_name command is not available
        print(f"Warning: branch_name command failed: {result.stderr}")
        print("Using 'default' as branch name")
        return "default"
    return result.stdout.strip()


def initialize_workflow(state: FixTestsState) -> FixTestsState:
    """Initialize the fix-tests workflow."""
    print(f"Initializing fix-tests workflow for test command: {state['test_cmd']}")

    # Get branch name and generate test command hash
    branch_name = get_branch_name()
    test_cmd_hash = generate_test_cmd_hash(state["test_cmd"])

    # Create blackboard directory
    blackboard_dir = f"bb/gai/fix_tests/{branch_name}/{test_cmd_hash}"
    os.makedirs(blackboard_dir, exist_ok=True)

    # Initialize blackboard manager
    blackboard_manager = BlackboardManager(blackboard_dir)

    print(f"Branch name: {branch_name}")
    print(f"Test command hash: {test_cmd_hash}")
    print(f"Blackboard directory: {blackboard_dir}")

    return {
        **state,
        "branch_name": branch_name,
        "test_cmd_hash": test_cmd_hash,
        "blackboard_dir": blackboard_dir,
        "blackboard_manager": blackboard_manager,
        "current_iteration": 1,
        "test_passed": False,
        "should_stop": False,
        "messages": [],
    }


def run_planning_agent(state: FixTestsState) -> FixTestsState:
    """Run the planning agent to determine next action."""
    print(f"\n{'='*60}")
    print(f"ITERATION {state['current_iteration']}: Running Planning Agent")
    print(f"{'='*60}")

    planning_agent = PlanningAgent(
        state["blackboard_manager"],
        state["test_cmd"],
        state["test_output_file"],
        state["current_iteration"],
    )

    # Run the planning agent
    result = planning_agent.run()

    # The planning agent creates one of the decision files
    # We'll check for them in the next step

    return {**state, "messages": state["messages"] + result.get("messages", [])}


def determine_next_action(state: FixTestsState) -> str:
    """Determine the next action based on planning agent output."""
    blackboard_dir = state["blackboard_dir"]

    # Check for decision files in priority order
    decision_files = [
        ("bb/gai_fix_tests/new_editor_prompt.md", "new_editor"),
        ("bb/gai_fix_tests/next_editor_prompt.md", "next_editor"),
        ("bb/gai_fix_tests/next_research_prompt.md", "research"),
        ("bb/gai_fix_tests/stop_workflow.md", "stop"),
    ]

    for file_path, action in decision_files:
        if os.path.exists(file_path):
            print(f"Planning agent created: {file_path}")
            print(f"Next action: {action}")
            return action

    # If no decision file was created, something went wrong
    print("ERROR: Planning agent did not create any decision file")
    return "stop"


def run_new_editor_agent(state: FixTestsState) -> FixTestsState:
    """Run a new editor agent (clearing previous editor state)."""
    print(f"\n{'='*60}")
    print("Running NEW Editor Agent")
    print(f"{'='*60}")

    # Clear editor blackboard and reset code changes
    state["blackboard_manager"].clear_editor_blackboard()
    run_shell_command("hg update --clean .", capture_output=False)

    # Read the prompt file
    with open("bb/gai_fix_tests/new_editor_prompt.md", "r") as f:
        prompt = f.read()

    editor_agent = EditorAgent(
        state["blackboard_manager"],
        state["test_cmd"],
        state["test_output_file"],
        is_new_session=True,
    )

    result = editor_agent.run(prompt)

    # Clean up the prompt file
    os.remove("bb/gai_fix_tests/new_editor_prompt.md")

    return {**state, "messages": state["messages"] + result.get("messages", [])}


def run_next_editor_agent(state: FixTestsState) -> FixTestsState:
    """Run the next editor agent (continuing from previous editor state)."""
    print(f"\n{'='*60}")
    print("Running NEXT Editor Agent")
    print(f"{'='*60}")

    # Read the prompt file
    with open("bb/gai_fix_tests/next_editor_prompt.md", "r") as f:
        prompt = f.read()

    editor_agent = EditorAgent(
        state["blackboard_manager"],
        state["test_cmd"],
        state["test_output_file"],
        is_new_session=False,
    )

    result = editor_agent.run(prompt)

    # Clean up the prompt file
    os.remove("bb/gai_fix_tests/next_editor_prompt.md")

    return {**state, "messages": state["messages"] + result.get("messages", [])}


def run_research_agent(state: FixTestsState) -> FixTestsState:
    """Run the research agent."""
    print(f"\n{'='*60}")
    print("Running Research Agent")
    print(f"{'='*60}")

    # Read the prompt file
    with open("bb/gai_fix_tests/next_research_prompt.md", "r") as f:
        prompt = f.read()

    research_agent = ResearchAgent(
        state["blackboard_manager"], state["test_cmd"], state["test_output_file"]
    )

    result = research_agent.run(prompt)

    # Clean up the prompt file
    os.remove("bb/gai_fix_tests/next_research_prompt.md")

    return {**state, "messages": state["messages"] + result.get("messages", [])}


def run_tests_and_check(state: FixTestsState) -> FixTestsState:
    """Run tests after editor agent and check if they pass."""
    print(f"\n{'='*60}")
    print("Running Tests")
    print(f"{'='*60}")

    # Create gai_test directory path
    gai_test_dir = f"bb/gai/fix_tests/{state['branch_name']}/{state['test_cmd_hash']}"

    # Run gai_test
    gai_test_cmd = f"gai_test {gai_test_dir} fix-tests"
    print(f"Running: {gai_test_cmd}")

    result = run_shell_command(gai_test_cmd, capture_output=True)

    test_passed = result.returncode == 0

    if test_passed:
        print("✅ Tests PASSED! The fix was successful!")
    else:
        print("❌ Tests still failing")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)

    return {**state, "test_passed": test_passed}


def handle_stop_workflow(state: FixTestsState) -> FixTestsState:
    """Handle stop workflow decision from planning agent."""
    print(f"\n{'='*60}")
    print("WORKFLOW STOPPED by Planning Agent")
    print(f"{'='*60}")

    # Read the stop reason
    stop_reason = ""
    if os.path.exists("bb/gai_fix_tests/stop_workflow.md"):
        with open("bb/gai_fix_tests/stop_workflow.md", "r") as f:
            stop_reason = f.read()
        os.remove("bb/gai_fix_tests/stop_workflow.md")

    print("Stop reason:")
    print(stop_reason)

    # TODO: Implement user interaction for next steps
    # For now, just mark as stopped

    return {
        **state,
        "should_stop": True,
        "stop_reason": stop_reason,
    }


def should_continue_workflow(state: FixTestsState) -> str:
    """Determine if workflow should continue."""
    if state["test_passed"]:
        return "success"
    elif state["should_stop"]:
        return "stopped"
    elif state["current_iteration"] >= state["max_iterations"]:
        return "max_iterations"
    else:
        return "continue"


def increment_iteration(state: FixTestsState) -> FixTestsState:
    """Increment the iteration counter."""
    return {**state, "current_iteration": state["current_iteration"] + 1}


def handle_success(state: FixTestsState) -> FixTestsState:
    """Handle successful test fix."""
    print(
        f"""
🎉 SUCCESS! Test has been fixed!

Test command: {state['test_cmd']}
Blackboard directory: {state['blackboard_dir']}
Iterations completed: {state['current_iteration']}
"""
    )

    run_bam_command("Fix-Tests Workflow Complete - Test Fixed!")
    return state


def handle_failure(state: FixTestsState) -> FixTestsState:
    """Handle workflow failure (max iterations reached)."""
    print(
        f"""
❌ FAILURE! Unable to fix test after {state['max_iterations']} iterations.

Test command: {state['test_cmd']}
Blackboard directory: {state['blackboard_dir']}
"""
    )

    run_bam_command("Fix-Tests Workflow Complete - Max Iterations Reached")
    return state


def handle_stopped(state: FixTestsState) -> FixTestsState:
    """Handle workflow stopped by planning agent."""
    print(
        f"""
⏹️ WORKFLOW STOPPED by Planning Agent

Test command: {state['test_cmd']}
Blackboard directory: {state['blackboard_dir']}
Iterations completed: {state['current_iteration']}

Stop reason:
{state.get('stop_reason', 'No reason provided')}
"""
    )

    run_bam_command("Fix-Tests Workflow Stopped by Planning Agent")
    return state


class FixTestsWorkflow(BaseWorkflow):
    """A workflow for fixing failing tests using planning, editor, and research agents."""

    def __init__(self, test_cmd: str, test_output_file: str, max_iterations: int = 10):
        self.test_cmd = test_cmd
        self.test_output_file = test_output_file
        self.max_iterations = max_iterations

    @property
    def name(self) -> str:
        return "fix-tests"

    @property
    def description(self) -> str:
        return "Fix failing tests using planning, editor, and research agents with persistent blackboards"

    def create_workflow(self):
        """Create and return the LangGraph workflow."""
        workflow = StateGraph(FixTestsState)

        # Add nodes
        workflow.add_node("initialize", initialize_workflow)
        workflow.add_node("planning", run_planning_agent)
        workflow.add_node("new_editor", run_new_editor_agent)
        workflow.add_node("next_editor", run_next_editor_agent)
        workflow.add_node("research", run_research_agent)
        workflow.add_node("test_and_check", run_tests_and_check)
        workflow.add_node("stop_workflow", handle_stop_workflow)
        workflow.add_node("increment", increment_iteration)
        workflow.add_node("success", handle_success)
        workflow.add_node("failure", handle_failure)
        workflow.add_node("stopped", handle_stopped)

        # Add edges
        workflow.add_edge(START, "initialize")
        workflow.add_edge("initialize", "planning")

        # After planning, determine next action
        workflow.add_conditional_edges(
            "planning",
            determine_next_action,
            {
                "new_editor": "new_editor",
                "next_editor": "next_editor",
                "research": "research",
                "stop": "stop_workflow",
            },
        )

        # After editor agents, run tests
        workflow.add_edge("new_editor", "test_and_check")
        workflow.add_edge("next_editor", "test_and_check")

        # After research, go back to planning
        workflow.add_edge("research", "increment")

        # After test check, determine if we should continue
        workflow.add_conditional_edges(
            "test_and_check",
            should_continue_workflow,
            {
                "success": "success",
                "continue": "increment",
                "max_iterations": "failure",
                "stopped": "stopped",
            },
        )

        # After incrementing, go back to planning
        workflow.add_edge("increment", "planning")

        # Terminal nodes
        workflow.add_edge("stop_workflow", "stopped")
        workflow.add_edge("success", END)
        workflow.add_edge("failure", END)
        workflow.add_edge("stopped", END)

        return workflow.compile()

    def run(self) -> bool:
        """Run the workflow and return True if successful, False otherwise."""
        if not os.path.exists(self.test_output_file):
            print(f"Error: Test output file '{self.test_output_file}' does not exist")
            return False

        # Create the bb/gai_fix_tests directory if it doesn't exist
        os.makedirs("bb/gai_fix_tests", exist_ok=True)

        # Create and run the workflow
        app = self.create_workflow()

        initial_state: FixTestsState = {
            "test_cmd": self.test_cmd,
            "test_output_file": self.test_output_file,
            "branch_name": "",
            "test_cmd_hash": "",
            "blackboard_dir": "",
            "blackboard_manager": None,
            "current_iteration": 1,
            "max_iterations": self.max_iterations,
            "test_passed": False,
            "should_stop": False,
            "stop_reason": None,
            "messages": [],
        }

        try:
            final_state = app.invoke(initial_state)
            return final_state["test_passed"]
        except Exception as e:
            print(f"Error running fix-tests workflow: {e}")
            return False
