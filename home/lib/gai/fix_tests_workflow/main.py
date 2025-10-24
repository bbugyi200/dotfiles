import hashlib
import os
import sys
from typing import List, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from shared_utils import run_bam_command, run_shell_command
from workflow_base import BaseWorkflow

from .agents import EditorAgent, PlanningAgent, ResearchAgent
from .blackboard import BlackboardManager


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
    last_planning_response: Optional[str]
    decision_history: List[str]  # Track previous decisions to prevent loops


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


def parse_planning_response(
    response_content: str,
) -> tuple[Optional[str], Optional[str]]:
    """Parse planning agent response to extract decision type and content."""
    response_lines = response_content.split("\n")

    # Look for structured response format first
    decision_type = None
    content_lines = []
    in_content = False

    for line in response_lines:
        line = line.strip()

        # Look for DECISION: format
        if line.startswith("DECISION:"):
            decision_type = line.split("DECISION:", 1)[1].strip().lower()
            continue

        # Look for CONTENT: format
        if line.startswith("CONTENT:"):
            in_content = True
            continue

        if in_content:
            content_lines.append(line)

    # If structured format found, return it
    if decision_type and content_lines:
        content = "\n".join(content_lines).strip()
        return decision_type, content

    # Fallback: Look for decision indicators in unstructured response
    response_lower = response_content.lower()

    if "bb/gai_fix_tests/new_editor_prompt.md" in response_content:
        decision_type = "new_editor"
    elif "bb/gai_fix_tests/next_editor_prompt.md" in response_content:
        decision_type = "next_editor"
    elif "bb/gai_fix_tests/next_research_prompt.md" in response_content:
        decision_type = "research"
    elif "bb/gai_fix_tests/stop_workflow.md" in response_content:
        decision_type = "stop"
    else:
        # Try to infer from keywords
        if "new editor" in response_lower or "start fresh" in response_lower:
            decision_type = "new_editor"
        elif "continue" in response_lower and "editor" in response_lower:
            decision_type = "next_editor"
        elif "research" in response_lower or "more information" in response_lower:
            decision_type = "research"
        elif "stop" in response_lower or "cannot" in response_lower:
            decision_type = "stop"

    if decision_type:
        # Extract content from the response (everything after decision indicators)
        content = extract_content_for_decision(response_content, decision_type)
        return decision_type, content

    return None, None


def extract_content_for_decision(response_content: str, decision_type: str) -> str:
    """Extract the content for a specific decision type from the response."""
    lines = response_content.split("\n")
    content_lines = []
    in_prompt_section = False

    for line in lines:
        # Skip metadata and decision announcements
        if any(
            indicator in line.lower()
            for indicator in [
                "i have created",
                "decision:",
                "bb/gai_fix_tests/",
                "planning agent",
                "next action",
            ]
        ):
            continue

        # Look for prompt content
        if decision_type in ["new_editor", "next_editor"]:
            if any(
                keyword in line.lower()
                for keyword in ["prompt", "task", "fix", "error"]
            ):
                in_prompt_section = True
            if in_prompt_section:
                content_lines.append(line)
        elif decision_type == "research":
            if any(
                keyword in line.lower()
                for keyword in ["research", "investigate", "search"]
            ):
                in_prompt_section = True
            if in_prompt_section:
                content_lines.append(line)
        elif decision_type == "stop":
            if any(
                keyword in line.lower()
                for keyword in ["stop", "reason", "cannot", "unable"]
            ):
                in_prompt_section = True
            if in_prompt_section:
                content_lines.append(line)

    # If no specific content found, use a default based on the original response
    if not content_lines:
        if decision_type in ["new_editor", "next_editor"]:
            content_lines = [
                f"Based on the test failure, please analyze and fix the issues.",
                f"Original planning response: {response_content[:500]}...",
            ]
        elif decision_type == "research":
            content_lines = [
                "Please conduct research to gather more information about the test failure.",
                f"Context: {response_content[:300]}...",
            ]
        elif decision_type == "stop":
            content_lines = [
                "The planning agent determined that the workflow should stop.",
                f"Reason: {response_content[:300]}...",
            ]

    return "\n".join(content_lines).strip()


def create_decision_file(decision_type: str, content: str) -> str:
    """Create the appropriate decision file with the given content."""
    decision_files = {
        "new_editor": "bb/gai_fix_tests/new_editor_prompt.md",
        "next_editor": "bb/gai_fix_tests/next_editor_prompt.md",
        "research": "bb/gai_fix_tests/next_research_prompt.md",
        "stop": "bb/gai_fix_tests/stop_workflow.md",
    }

    file_path = decision_files.get(decision_type)
    if not file_path:
        raise ValueError(f"Unknown decision type: {decision_type}")

    # Ensure directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Write content to file
    with open(file_path, "w") as f:
        f.write(content)

    print(f"Created decision file: {file_path}")
    return file_path


def check_decision_loop(state: FixTestsState, decision_type: str) -> bool:
    """Check if we're in a decision loop and should escalate."""
    decision_history = state.get("decision_history", [])

    # If same decision repeated 3+ times in recent history, escalate
    recent_decisions = (
        decision_history[-5:] if len(decision_history) > 5 else decision_history
    )
    same_decision_count = recent_decisions.count(decision_type)

    if same_decision_count >= 2:
        print(
            f"Warning: Decision '{decision_type}' repeated {same_decision_count} times recently"
        )
        if decision_type == "new_editor" and same_decision_count >= 3:
            print("Escalating to research due to repeated editor failures")
            return True
        elif decision_type == "next_editor" and same_decision_count >= 2:
            print("Escalating to new editor due to repeated continuation failures")
            return True

    return False


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
        "last_planning_response": None,
        "decision_history": [],
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

    # Store the agent's response for parsing
    agent_response = (
        result.get("messages", [])[-1].content if result.get("messages") else ""
    )

    return {
        **state,
        "messages": state["messages"] + result.get("messages", []),
        "last_planning_response": agent_response,
    }


def determine_next_action(state: FixTestsState) -> str:
    """Determine the next action based on planning agent output."""

    # First try to parse the agent's response
    response = state.get("last_planning_response", "")
    if response:
        decision_type, content = parse_planning_response(response)

        if decision_type and content:
            # Check for decision loops and escalate if needed
            if check_decision_loop(state, decision_type):
                if decision_type == "new_editor":
                    decision_type = "research"
                    content = f"Previous editor approaches have failed repeatedly. Please research alternative solutions or similar issues.\n\nOriginal context: {content[:300]}..."
                elif decision_type == "next_editor":
                    decision_type = "new_editor"
                    content = f"Continuing with previous editor work has failed. Starting fresh approach.\n\nPrevious context: {content[:300]}..."
                print(f"Escalated decision from loop: {decision_type}")

            # Create the decision file programmatically
            try:
                create_decision_file(decision_type, content)

                # Update decision history
                decision_history = state.get("decision_history", [])
                decision_history.append(decision_type)
                state["decision_history"] = decision_history

                print(f"Planning agent decision: {decision_type}")
                print(f"Decision history: {decision_history[-5:]}")  # Show last 5
                return decision_type
            except Exception as e:
                print(f"Error creating decision file: {e}")
                return "stop"

    # Fallback: check for manually created files (backward compatibility)
    decision_files = [
        ("bb/gai_fix_tests/new_editor_prompt.md", "new_editor"),
        ("bb/gai_fix_tests/next_editor_prompt.md", "next_editor"),
        ("bb/gai_fix_tests/next_research_prompt.md", "research"),
        ("bb/gai_fix_tests/stop_workflow.md", "stop"),
    ]

    for file_path, action in decision_files:
        if os.path.exists(file_path):
            print(f"Found existing decision file: {file_path}")
            print(f"Next action: {action}")

            # Update decision history
            decision_history = state.get("decision_history", [])
            decision_history.append(action)
            state["decision_history"] = decision_history

            return action

    # If no decision could be determined, stop with error
    print("ERROR: Could not determine next action from planning agent response")
    print(f"Response was: {response[:200]}..." if response else "No response received")

    # Create a stop file with error details
    error_content = f"""
Planning Agent Response Parse Error

The planning agent did not provide a clear decision in the expected format.

Original Response:
{response}

Expected format:
DECISION: new_editor|next_editor|research|stop
CONTENT:
[Detailed prompt content here]

The workflow is stopping due to this communication error.
"""
    create_decision_file("stop", error_content)
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
            "last_planning_response": None,
            "decision_history": [],
        }

        try:
            final_state = app.invoke(initial_state)
            return final_state["test_passed"]
        except Exception as e:
            print(f"Error running fix-tests workflow: {e}")
            return False
