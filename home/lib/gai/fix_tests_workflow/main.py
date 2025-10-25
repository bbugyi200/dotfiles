import os
import sys
from typing import List, Optional, TypedDict

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from shared_utils import create_artifacts_directory, run_bam_command, run_shell_command
from workflow_base import BaseWorkflow


class FixTestsState(TypedDict):
    test_cmd: str
    test_output_file: str
    artifacts_dir: str
    current_iteration: int
    test_passed: bool
    failure_reason: Optional[str]
    blackboard_exists: bool
    context_agent_retries: int
    max_context_retries: int
    messages: List[HumanMessage | AIMessage]


def initialize_fix_tests_workflow(state: FixTestsState) -> FixTestsState:
    """Initialize the fix-tests workflow by creating artifacts and copying files."""
    print(f"Initializing fix-tests workflow...")
    print(f"Test command: {state['test_cmd']}")
    print(f"Test output file: {state['test_output_file']}")

    # Verify test output file exists
    if not os.path.exists(state["test_output_file"]):
        return {
            **state,
            "test_passed": False,
            "failure_reason": f"Test output file '{state['test_output_file']}' does not exist",
        }

    # Create artifacts directory
    artifacts_dir = create_artifacts_directory()
    print(f"Created artifacts directory: {artifacts_dir}")

    # Create initial artifacts
    try:
        # Copy test output file
        test_output_artifact = os.path.join(artifacts_dir, "test_output.txt")
        result = run_shell_command(
            f"cp '{state['test_output_file']}' '{test_output_artifact}'"
        )
        if result.returncode != 0:
            return {
                **state,
                "test_passed": False,
                "failure_reason": f"Failed to copy test output file: {result.stderr}",
            }

        # Create cl_desc.txt using hdesc
        cl_desc_artifact = os.path.join(artifacts_dir, "cl_desc.txt")
        result = run_shell_command("hdesc")
        with open(cl_desc_artifact, "w") as f:
            f.write(result.stdout)

        # Create cl_changes.diff using branch_diff
        cl_changes_artifact = os.path.join(artifacts_dir, "cl_changes.diff")
        result = run_shell_command("branch_diff")
        with open(cl_changes_artifact, "w") as f:
            f.write(result.stdout)

        print(f"Created initial artifacts:")
        print(f"  - {test_output_artifact}")
        print(f"  - {cl_desc_artifact}")
        print(f"  - {cl_changes_artifact}")

        return {
            **state,
            "artifacts_dir": artifacts_dir,
            "current_iteration": 1,
            "test_passed": False,
            "blackboard_exists": False,
            "context_agent_retries": 0,
            "max_context_retries": 3,
            "messages": [],
        }

    except Exception as e:
        return {
            **state,
            "test_passed": False,
            "failure_reason": f"Error during initialization: {str(e)}",
        }


def build_editor_prompt(state: FixTestsState) -> str:
    """Build the prompt for the editor/fixer agent."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]

    prompt = f"""You are an expert test-fixing agent (iteration {iteration}). Your goal is to analyze test failures and make targeted code changes to fix them.

IMPORTANT INSTRUCTIONS:
- You should make code changes to fix the failing test, but do NOT run the test command yourself
- The workflow will handle running tests using gai_test after your changes
- You can only run shell commands if explicitly instructed to do so in the blackboard.md file
- Focus on making minimal, targeted changes to fix the specific test failure

AVAILABLE CONTEXT FILES:
@cl_changes.diff - Current CL changes (branch_diff output)
@cl_desc.txt - Current CL description (hdesc output) 
@test_output.txt - Test failure output"""

    # Check if blackboard exists and include it
    blackboard_path = os.path.join(artifacts_dir, "blackboard.md")
    if os.path.exists(blackboard_path):
        prompt += (
            "\n@blackboard.md - Blackboard with research findings and lessons learned"
        )
        state["blackboard_exists"] = True

    prompt += f"""

YOUR TASK:
1. Analyze the test failure in test_output.txt
2. Review the current CL changes and description for context
3. If blackboard.md exists, carefully review all lessons learned and follow them as strict rules"""

    if state["blackboard_exists"]:
        prompt += """
4. Pay special attention to any shell commands mentioned in blackboard.md - you MUST run these if instructed
5. Apply insights from Questions and Answers section to guide your fix approach
6. Ensure you don't repeat any mistakes documented in Lessons Learned"""

    prompt += """
4. Make targeted code changes to fix the test failure
5. Explain your reasoning and changes clearly

RESPONSE FORMAT:
- Provide analysis of the test failure
- Explain your fix approach and reasoning
- Show the specific code changes you're making
- Do NOT run the test command - the workflow handles testing"""

    return prompt


def build_context_prompt(state: FixTestsState) -> str:
    """Build the prompt for the context/research agent."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]

    prompt = f"""You are a research and context agent (iteration {iteration}). Your goal is to update the blackboard.md file with new insights, questions/answers, and lessons learned from the latest test failure.

CRITICAL INSTRUCTIONS:
- If you have nothing novel or useful to add to blackboard.md, respond with EXACTLY: "NO UPDATES"
- If you output "NO UPDATES", the workflow will abort
- If you don't output "NO UPDATES" but also don't update blackboard.md, you'll get up to 3 retries
- Focus on adding truly useful, actionable information that will help the next editor agent succeed

AVAILABLE CONTEXT FILES:
@cl_changes.diff - Current CL changes (branch_diff output)
@cl_desc.txt - Current CL description (hdesc output)
@test_output.txt - Original test failure output
@agent_test_output.txt - Output from the most recent gai_test run
@local_changes.diff - Changes made by the last editor agent (branch_local_diff output)"""

    # Check if blackboard exists
    blackboard_path = os.path.join(artifacts_dir, "blackboard.md")
    if os.path.exists(blackboard_path):
        prompt += "\n@blackboard.md - Current blackboard contents"

    prompt += """

BLACKBOARD.MD STRUCTURE:
The blackboard.md file should contain these H1 sections (only include sections with content):

# Questions and Answers
Contains H2 sections titled Q1, Q2, Q3, etc. Each H2 has:
## Q1
### Question
[Full question text]
### Answer  
[Full answer from research using code search, Buganizer, CL search, Moma, etc.]

# Lessons Learned
Contains H2 sections with descriptive titles. Each H2 describes:
- What went wrong in a previous attempt
- Clear actionable advice for the editor agent
- Specific conditions when the advice applies
- May include shell commands the editor MUST run

YOUR TASK:
1. Analyze the latest test failure and editor attempt
2. Research relevant information using available tools (code search, etc.)
3. Update blackboard.md with new insights, or respond "NO UPDATES" if nothing useful to add
4. Remember: the next editor agent won't see changes from the previous editor (stash_local_changes will be run)

RESPONSE FORMAT:
Either:
- "NO UPDATES" (if nothing new to add)
- Explanation of updates made to blackboard.md with reasoning"""

    return prompt


def run_editor_agent(state: FixTestsState) -> FixTestsState:
    """Run the editor/fixer agent to attempt fixing the test."""
    iteration = state["current_iteration"]
    print(f"Running editor agent (iteration {iteration})...")

    # Build prompt for editor
    prompt = build_editor_prompt(state)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print("Editor agent response received")

    # Save the agent's response
    response_path = os.path.join(
        state["artifacts_dir"], f"editor_response_iter_{iteration}.txt"
    )
    with open(response_path, "w") as f:
        f.write(response.content)

    # Print the response
    print("\n" + "=" * 80)
    print(f"EDITOR AGENT RESPONSE (ITERATION {iteration}):")
    print("=" * 80)
    print(response.content)
    print("=" * 80 + "\n")

    return {**state, "messages": messages + [response]}


def run_test_with_gai_test(state: FixTestsState) -> FixTestsState:
    """Run the test using gai_test and check if it passes."""
    iteration = state["current_iteration"]
    print(f"Running test with gai_test (iteration {iteration})...")

    artifacts_dir = state["artifacts_dir"]
    agent_name = f"fix_tests_iter_{iteration}"

    # Run gai_test
    gai_test_cmd = f"gai_test {artifacts_dir} {agent_name}"
    print(f"Executing: {gai_test_cmd}")

    result = run_shell_command(gai_test_cmd, capture_output=True)

    # Check if test passed
    test_passed = result.returncode == 0

    if test_passed:
        print("✅ Test PASSED!")
    else:
        print("❌ Test failed")

    # Print gai_test output
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"gai_test stderr: {result.stderr}")

    # Save gai_test output for context agent
    agent_test_output_path = os.path.join(artifacts_dir, "agent_test_output.txt")
    with open(agent_test_output_path, "w") as f:
        f.write(f"Command: {gai_test_cmd}\n")
        f.write(f"Return code: {result.returncode}\n")
        f.write(f"STDOUT:\n{result.stdout}\n")
        f.write(f"STDERR:\n{result.stderr}\n")

    # Save local changes diff for context agent
    local_changes_path = os.path.join(artifacts_dir, "local_changes.diff")
    local_diff_result = run_shell_command("branch_local_diff")
    with open(local_changes_path, "w") as f:
        f.write(local_diff_result.stdout)

    return {**state, "test_passed": test_passed}


def run_context_agent(state: FixTestsState) -> FixTestsState:
    """Run the context/research agent to update blackboard.md."""
    iteration = state["current_iteration"]
    print(f"Running context agent (iteration {iteration})...")

    # Build prompt for context agent
    prompt = build_context_prompt(state)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print("Context agent response received")

    # Save the agent's response
    response_path = os.path.join(
        state["artifacts_dir"], f"context_response_iter_{iteration}.txt"
    )
    with open(response_path, "w") as f:
        f.write(response.content)

    # Print the response
    print("\n" + "=" * 80)
    print(f"CONTEXT AGENT RESPONSE (ITERATION {iteration}):")
    print("=" * 80)
    print(response.content)
    print("=" * 80 + "\n")

    # Check if agent responded with "NO UPDATES"
    if response.content.strip() == "NO UPDATES":
        print("Context agent indicated no updates - workflow will abort")
        return {
            **state,
            "test_passed": False,
            "failure_reason": "Context agent found no new insights to add",
            "messages": state["messages"] + messages + [response],
        }

    # Check if blackboard.md was actually updated
    blackboard_path = os.path.join(state["artifacts_dir"], "blackboard.md")
    blackboard_updated = os.path.exists(blackboard_path)

    if not blackboard_updated:
        # Agent didn't say "NO UPDATES" but also didn't update blackboard
        retries = state["context_agent_retries"] + 1
        if retries >= state["max_context_retries"]:
            print(f"Context agent failed to update blackboard after {retries} retries")
            return {
                **state,
                "test_passed": False,
                "failure_reason": f"Context agent failed to update blackboard after {retries} retries",
                "context_agent_retries": retries,
                "messages": state["messages"] + messages + [response],
            }
        else:
            print(
                f"Context agent didn't update blackboard, retrying ({retries}/{state['max_context_retries']})"
            )
            return {
                **state,
                "context_agent_retries": retries,
                "messages": state["messages"] + messages + [response],
            }

    print("✅ Blackboard updated successfully")
    return {
        **state,
        "blackboard_exists": True,
        "context_agent_retries": 0,  # Reset retries on success
        "messages": state["messages"] + messages + [response],
    }


def stash_local_changes(state: FixTestsState) -> FixTestsState:
    """Stash local changes before the next editor iteration."""
    print("Stashing local changes...")

    result = run_shell_command("stash_local_changes", capture_output=True)
    if result.returncode != 0:
        print(f"Warning: stash_local_changes failed: {result.stderr}")
    else:
        print("✅ Local changes stashed")

    # Increment iteration for next cycle
    return {**state, "current_iteration": state["current_iteration"] + 1}


def should_continue_workflow(state: FixTestsState) -> str:
    """Determine the next step in the workflow."""
    if state["test_passed"]:
        return "success"
    elif state.get("failure_reason"):
        return "failure"
    elif state["context_agent_retries"] > 0:
        return "retry_context_agent"
    else:
        return "continue"


def handle_success(state: FixTestsState) -> FixTestsState:
    """Handle successful test fix."""
    print(
        f"""
🎉 SUCCESS! Test has been fixed in iteration {state['current_iteration']}!

Test command: {state['test_cmd']}
Artifacts saved in: {state['artifacts_dir']}
"""
    )

    run_bam_command("Fix-Tests Workflow Complete!")
    return state


def handle_failure(state: FixTestsState) -> FixTestsState:
    """Handle workflow failure."""
    reason = state.get("failure_reason", "Unknown error")
    print(
        f"""
❌ FAILURE! Unable to fix test.

Reason: {reason}
Test command: {state['test_cmd']}
Artifacts saved in: {state['artifacts_dir']}
"""
    )

    run_bam_command("Fix-Tests Workflow Failed")
    return state


class FixTestsWorkflow(BaseWorkflow):
    """A workflow for fixing failing tests using planning, editor, and research agents with persistent blackboards."""

    def __init__(self, test_cmd: str, test_output_file: str):
        self.test_cmd = test_cmd
        self.test_output_file = test_output_file

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
        workflow.add_node("initialize", initialize_fix_tests_workflow)
        workflow.add_node("run_editor", run_editor_agent)
        workflow.add_node("run_test", run_test_with_gai_test)
        workflow.add_node("run_context", run_context_agent)
        workflow.add_node("stash_changes", stash_local_changes)
        workflow.add_node("success", handle_success)
        workflow.add_node("failure", handle_failure)

        # Add edges
        workflow.add_edge(START, "initialize")
        workflow.add_edge("run_editor", "run_test")
        workflow.add_edge("run_context", "stash_changes")
        workflow.add_edge("stash_changes", "run_editor")

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
                "continue": "stash_changes",
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

        # Create and run the workflow
        app = self.create_workflow()

        initial_state: FixTestsState = {
            "test_cmd": self.test_cmd,
            "test_output_file": self.test_output_file,
            "artifacts_dir": "",
            "current_iteration": 1,
            "test_passed": False,
            "failure_reason": None,
            "blackboard_exists": False,
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
