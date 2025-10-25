import os
import sys
from typing import List, Optional, TypedDict

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from shared_utils import create_artifacts_directory, run_bam_command, run_shell_command
from workflow_base import BaseWorkflow


def file_exists_with_content(file_path: str) -> bool:
    """Check if a file exists and has non-whitespace content."""
    try:
        if not os.path.exists(file_path):
            return False
        with open(file_path, "r") as f:
            content = f.read()
            return bool(content.strip())
    except Exception:
        return False


class FixTestsState(TypedDict):
    test_cmd: str
    test_output_file: str
    blackboard_file: Optional[str]
    artifacts_dir: str
    current_iteration: int
    test_passed: bool
    failure_reason: Optional[str]
    lessons_exists: bool
    research_exists: bool
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

        # Copy and split blackboard file if provided
        lessons_exists = False
        research_exists = False

        if state.get("blackboard_file") and os.path.exists(state["blackboard_file"]):
            # Read the blackboard file content
            with open(state["blackboard_file"], "r") as f:
                blackboard_content = f.read()

            # Split content into lessons and research
            lessons_content = ""
            research_content = ""

            # Parse sections from blackboard file
            lines = blackboard_content.split("\n")
            current_section = None
            current_content = []

            for line in lines:
                if line.startswith("# Questions and Answers"):
                    # Save previous section
                    if current_section == "lessons" and current_content:
                        lessons_content = "\n".join(current_content).strip()
                    # Start research section
                    current_section = "research"
                    current_content = [line]
                elif line.startswith("# Lessons Learned"):
                    # Save previous section
                    if current_section == "research" and current_content:
                        research_content = "\n".join(current_content).strip()
                    # Start lessons section (but don't include the header since we want H1s for each lesson)
                    current_section = "lessons"
                    current_content = []
                elif line.startswith("## ") and current_section == "lessons":
                    # Convert H2 lessons to H1
                    current_content.append("# " + line[3:])
                else:
                    current_content.append(line)

            # Save final section
            if current_section == "lessons" and current_content:
                lessons_content = "\n".join(current_content).strip()
            elif current_section == "research" and current_content:
                research_content = "\n".join(current_content).strip()

            # Create lessons.md if there's content
            if lessons_content:
                lessons_artifact = os.path.join(artifacts_dir, "lessons.md")
                with open(lessons_artifact, "w") as f:
                    f.write(lessons_content)
                lessons_exists = True
                print(
                    f"  - {lessons_artifact} (lessons from {state['blackboard_file']})"
                )

            # Create research.md if there's content
            if research_content:
                research_artifact = os.path.join(artifacts_dir, "research.md")
                with open(research_artifact, "w") as f:
                    f.write(research_content)
                research_exists = True
                print(
                    f"  - {research_artifact} (research from {state['blackboard_file']})"
                )

        print(f"Created initial artifacts:")
        print(f"  - {test_output_artifact}")
        print(f"  - {cl_desc_artifact}")
        print(f"  - {cl_changes_artifact}")

        return {
            **state,
            "artifacts_dir": artifacts_dir,
            "current_iteration": 1,
            "test_passed": False,
            "lessons_exists": lessons_exists,
            "research_exists": research_exists,
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
- The workflow will handle running tests automatically after your changes
- You can only run shell commands if explicitly instructed to do so in the lessons.md file
- Focus on making minimal, targeted changes to fix the specific test failure

AVAILABLE CONTEXT FILES:
@{artifacts_dir}/cl_changes.diff - Current CL changes (branch_diff output)
@{artifacts_dir}/cl_desc.txt - Current CL description (hdesc output) 
@{artifacts_dir}/test_output.txt - Test failure output"""

    # Check if local_changes.diff exists and has content
    local_changes_path = os.path.join(artifacts_dir, "local_changes.diff")
    if file_exists_with_content(local_changes_path):
        prompt += f"\n@{artifacts_dir}/local_changes.diff - Changes made by previous editor agents"

    # Check if lessons.md exists and include it
    lessons_path = os.path.join(artifacts_dir, "lessons.md")
    if os.path.exists(lessons_path):
        prompt += (
            f"\n@{artifacts_dir}/lessons.md - Lessons learned from previous attempts"
        )
        state["lessons_exists"] = True

    prompt += f"""

YOUR TASK:
1. Analyze the test failure in test_output.txt
2. Review the current CL changes and description for context
3. If lessons.md exists, carefully review all lessons learned and follow them as strict rules"""

    if state["lessons_exists"]:
        prompt += """
4. Pay special attention to any shell commands mentioned in lessons.md - you MUST run these if instructed
5. Ensure you don't repeat any mistakes documented in the lessons"""

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

    prompt = f"""You are a research and context agent (iteration {iteration}). Your goal is to update the {artifacts_dir}/lessons.md and {artifacts_dir}/research.md files with new insights and lessons learned from the latest test failure.

CRITICAL INSTRUCTIONS:
- If you have nothing novel or useful to add to either file, respond with EXACTLY: "NO UPDATES"
- If you output "NO UPDATES", the workflow will abort
- If you don't output "NO UPDATES" but also don't update at least one of the files, you'll get up to 3 retries
- Focus on adding truly useful, actionable information that will help the next editor agent succeed
- NEVER recommend that the editor agent run test commands - the workflow handles all test execution automatically

AVAILABLE CONTEXT FILES:
@{artifacts_dir}/cl_changes.diff - Current CL changes (branch_diff output)
@{artifacts_dir}/cl_desc.txt - Current CL description (hdesc output)
@{artifacts_dir}/test_output.txt - Original test failure output
@{artifacts_dir}/agent_test_output.txt - Output from the most recent test run
@{artifacts_dir}/agent_reply.md - Full response from the last editor agent"""

    # Check if local_changes.diff exists and has content
    local_changes_path = os.path.join(artifacts_dir, "local_changes.diff")
    if file_exists_with_content(local_changes_path):
        prompt += f"\n@{artifacts_dir}/local_changes.diff - Changes made by the last editor agent"

    # Check if lessons.md and research.md exist
    lessons_path = os.path.join(artifacts_dir, "lessons.md")
    if os.path.exists(lessons_path):
        prompt += f"\n@{artifacts_dir}/lessons.md - Current lessons learned"

    research_path = os.path.join(artifacts_dir, "research.md")
    if os.path.exists(research_path):
        prompt += f"\n@{artifacts_dir}/research.md - Current research log and findings"

    prompt += f"""

FILE STRUCTURE AND PURPOSE:

LESSONS.MD:
- Contains H1 sections, each representing a specific lesson learned
- Each H1 section should have a descriptive title that captures the lesson
- Content should describe:
  - What went wrong in a previous attempt  
  - Clear actionable advice for the editor agent
  - Specific conditions when the advice applies
  - May include shell commands the editor MUST run
  - NEVER include recommendations to run test commands (workflow handles testing automatically)
- This file is shared with the editor agent and should contain only actionable lessons

RESEARCH.MD:
- Contains a detailed log of all research activities and findings
- Should include questions asked, answers found, and tool calls made
- Document both useful findings AND dead ends (what didn't work)
- Use clear structure with timestamps or iteration markers
- Include specific file paths, CL numbers, bug IDs, and other concrete references
- This file is ONLY for the context agent and should be reviewed thoroughly before each research session
- Use this to avoid repeating unsuccessful research approaches

YOUR TASK:
1. Analyze the latest test failure and editor attempt
2. Research relevant information using available tools (code search, etc.)
3. Update {artifacts_dir}/lessons.md with new actionable lessons for the editor agent
4. Update {artifacts_dir}/research.md with detailed research findings and dead ends
5. You MAY run `stash_local_changes` if you think the next editor agent would benefit from a fresh start
6. Respond "NO UPDATES" only if you have absolutely nothing useful to add to either file

RESPONSE FORMAT:
Either:
- "NO UPDATES" (if nothing new to add to either file)
- Explanation of updates made to the files with reasoning"""

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

    # Also save as agent_reply.md for context agent
    agent_reply_path = os.path.join(state["artifacts_dir"], "agent_reply.md")
    with open(agent_reply_path, "w") as f:
        f.write(response.content)

    # Print the response
    print("\n" + "=" * 80)
    print(f"EDITOR AGENT RESPONSE (ITERATION {iteration}):")
    print("=" * 80)
    print(response.content)
    print("=" * 80 + "\n")

    return {**state, "messages": messages + [response]}


def run_test(state: FixTestsState) -> FixTestsState:
    """Run the actual test command and check if it passes."""
    iteration = state["current_iteration"]
    test_cmd = state["test_cmd"]
    print(f"Running test command (iteration {iteration}): {test_cmd}")

    artifacts_dir = state["artifacts_dir"]

    # Run the actual test command
    print(f"Executing: {test_cmd}")
    result = run_shell_command(test_cmd, capture_output=True)

    # Check if test passed
    test_passed = result.returncode == 0

    if test_passed:
        print("✅ Test PASSED!")
    else:
        print("❌ Test failed")

    # Print test output
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"Test stderr: {result.stderr}")

    # Save test output for context agent
    agent_test_output_path = os.path.join(artifacts_dir, "agent_test_output.txt")
    with open(agent_test_output_path, "w") as f:
        f.write(f"Command: {test_cmd}\n")
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

    # Check if either lessons.md or research.md was actually updated
    lessons_path = os.path.join(state["artifacts_dir"], "lessons.md")
    research_path = os.path.join(state["artifacts_dir"], "research.md")

    lessons_updated = os.path.exists(lessons_path)
    research_updated = os.path.exists(research_path)
    files_updated = lessons_updated or research_updated

    if not files_updated:
        # Agent didn't say "NO UPDATES" but also didn't update either file
        retries = state["context_agent_retries"] + 1
        if retries >= state["max_context_retries"]:
            print(
                f"Context agent failed to update files after {retries} retries - workflow will abort"
            )
            return {
                **state,
                "test_passed": False,
                "failure_reason": f"Context agent failed to update files after {retries} retries",
                "context_agent_retries": retries,
                "messages": state["messages"] + messages + [response],
            }
        else:
            print(
                f"Context agent didn't update any files, retrying ({retries}/{state['max_context_retries']})"
            )
            return {
                **state,
                "context_agent_retries": retries,
                "messages": state["messages"] + messages + [response],
            }

    print("✅ Files updated successfully")
    return {
        **state,
        "lessons_exists": lessons_updated,
        "research_exists": research_updated,
        "context_agent_retries": 0,  # Reset retries on success
        "current_iteration": state["current_iteration"]
        + 1,  # Increment iteration for next cycle
        "messages": state["messages"] + messages + [response],
    }


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
    """A workflow for fixing failing tests using planning, editor, and research agents with persistent lessons and research logs."""

    def __init__(
        self,
        test_cmd: str,
        test_output_file: str,
        blackboard_file: Optional[str] = None,
    ):
        self.test_cmd = test_cmd
        self.test_output_file = test_output_file
        self.blackboard_file = blackboard_file

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

        return workflow.compile()

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
