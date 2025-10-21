import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional, TypedDict

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from workflow_base import BaseWorkflow


class TestFixState(TypedDict):
    test_file_path: str
    artifacts_dir: str
    test_command: str
    current_agent: int
    max_agents: int
    test_passed: bool
    failure_reason: Optional[str]
    agent_artifacts: List[str]
    research_completed: bool
    research_artifacts: List[str]
    messages: List[HumanMessage | AIMessage]


def run_shell_command(
    cmd: str, capture_output: bool = True
) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    return subprocess.run(
        cmd,
        shell=True,
        capture_output=capture_output,
        text=True,
    )


def create_artifacts_directory() -> str:
    """Create a timestamped artifacts directory."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    artifacts_dir = f"bb/gai/{timestamp}"
    Path(artifacts_dir).mkdir(parents=True, exist_ok=True)
    return artifacts_dir


def extract_test_command(test_file_path: str) -> str:
    """Extract test command from the first line of the test file."""
    cmd = f"cat {test_file_path} | head -n 1 | cut -d' ' -f2-"
    result = run_shell_command(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to extract test command: {result.stderr}")
    return result.stdout.strip()


def create_test_output_artifact(
    test_file_path: str, artifacts_dir: str, suffix: str = ""
) -> str:
    """Create artifact with test failure output."""
    # First check if "There was 1 failure" exists in the file
    check_cmd = f"grep -q 'There was 1 failure' {test_file_path}"
    check_result = run_shell_command(check_cmd)

    if check_result.returncode == 0:
        # "There was 1 failure" found, use trimmed output
        cmd = f"tac {test_file_path} | grep -m1 'There was 1 failure' -B1000 | tac"
        result = run_shell_command(cmd)
        content = result.stdout
    else:
        # "There was 1 failure" not found, use full output
        with open(test_file_path, "r") as f:
            content = f.read()

    artifact_name = f"test_output{suffix}.txt"
    artifact_path = os.path.join(artifacts_dir, artifact_name)

    with open(artifact_path, "w") as f:
        f.write(content)

    return artifact_path


def create_hdesc_artifact(artifacts_dir: str) -> str:
    """Create artifact with hdesc output."""
    result = run_shell_command("hdesc")

    artifact_path = os.path.join(artifacts_dir, "cl_description.txt")
    with open(artifact_path, "w") as f:
        f.write(result.stdout)

    return artifact_path


def create_diff_artifact(artifacts_dir: str) -> str:
    """Create artifact with hg pdiff output."""
    cmd = "hg pdiff $(branch_changes | grep -v -E 'png$|fingerprint$|BUILD$')"
    result = run_shell_command(cmd)

    artifact_path = os.path.join(artifacts_dir, "current_diff.txt")
    with open(artifact_path, "w") as f:
        f.write(result.stdout)

    return artifact_path


def run_test_and_check(
    test_command: str, artifacts_dir: str, agent_num: int
) -> tuple[bool, str]:
    """Run the test command and check if it passes."""

    # Run the test command once
    result = run_shell_command(test_command, capture_output=True)

    # Check for skipped tests that indicate build failure
    skipped_test_indicators = [
        "NO STATUS",
        "was skipped",
        "Executed 0 out of",
        "0 tests executed",
    ]

    has_skipped_tests = any(
        indicator in result.stdout for indicator in skipped_test_indicators
    )

    if has_skipped_tests:
        print(
            f"⚠️  Detected skipped test for Agent {agent_num} - this indicates a build failure"
        )
        # Log the skipped test case with all STDOUT and STDERR
        skipped_output_path = os.path.join(
            artifacts_dir, f"agent_{agent_num}_test_failure.txt"
        )
        with open(skipped_output_path, "w") as f:
            f.write("Test was skipped (indicates build failure)\n")
            f.write(f"Return code: {result.returncode}\n")
            f.write(f"STDOUT:\n{result.stdout}\n")
            f.write(f"STDERR:\n{result.stderr}\n")

        return False, skipped_output_path

    # Store full test output
    full_output_path = os.path.join(
        artifacts_dir, f"agent_{agent_num}_test_full_output.txt"
    )
    with open(full_output_path, "w") as f:
        f.write(f"Return code: {result.returncode}\n")
        f.write(f"STDOUT:\n{result.stdout}\n")
        f.write(f"STDERR:\n{result.stderr}\n")

    # Check if test passed (return code 0)
    if result.returncode == 0:
        return True, full_output_path

    # Test failed, check for build errors and potentially retry
    def process_test_failure(test_result, attempt_suffix=""):
        """Process a test failure and create appropriate artifacts."""
        # Write stdout to temp file first to avoid argument list too long error
        temp_output_path = os.path.join(
            artifacts_dir, f"agent_{agent_num}_temp_output{attempt_suffix}.txt"
        )
        with open(temp_output_path, "w") as f:
            f.write(test_result.stdout)

        # Check if "There was 1 failure" exists in the output
        check_cmd = f"grep -q 'There was 1 failure' {temp_output_path}"
        check_result = run_shell_command(check_cmd)

        if check_result.returncode == 0:
            # "There was 1 failure" found, use trimmed output
            trimmed_cmd = (
                f"tac {temp_output_path} | grep -m1 'There was 1 failure' -B1000 | tac"
            )
            trimmed_result = run_shell_command(trimmed_cmd)
            output_content = trimmed_result.stdout
        else:
            # "There was 1 failure" not found, use full output
            output_content = test_result.stdout

        final_output_path = os.path.join(
            artifacts_dir, f"agent_{agent_num}_test_failure{attempt_suffix}.txt"
        )
        with open(final_output_path, "w") as f:
            f.write(output_content)

        # Clean up temp file
        try:
            os.remove(temp_output_path)
        except OSError:
            pass

        return output_content, final_output_path

    # Process the initial failure
    output_content, failure_path = process_test_failure(result)

    # Check for build errors - if 'cannot find symbol' found in stderr
    has_build_error = "cannot find symbol" in result.stderr

    if has_build_error:
        print(f"Build error detected for Agent {agent_num}, running build_cleaner...")

        # Run build_cleaner
        build_clean_result = run_shell_command("build_cleaner", capture_output=True)
        print(
            f"build_cleaner completed with return code: {build_clean_result.returncode}"
        )

        # Store build_cleaner output
        build_clean_path = os.path.join(
            artifacts_dir, f"agent_{agent_num}_build_cleaner_output.txt"
        )
        with open(build_clean_path, "w") as f:
            f.write(f"Return code: {build_clean_result.returncode}\n")
            f.write(f"STDOUT:\n{build_clean_result.stdout}\n")
            f.write(f"STDERR:\n{build_clean_result.stderr}\n")

        # Retry the test ONCE
        print(f"Retrying test for Agent {agent_num} after build_cleaner...")
        retry_result = run_shell_command(test_command, capture_output=True)

        # Store retry test output
        retry_full_output_path = os.path.join(
            artifacts_dir, f"agent_{agent_num}_test_retry_full_output.txt"
        )
        with open(retry_full_output_path, "w") as f:
            f.write(f"Return code: {retry_result.returncode}\n")
            f.write(f"STDOUT:\n{retry_result.stdout}\n")
            f.write(f"STDERR:\n{retry_result.stderr}\n")

        # Check if retry passed
        if retry_result.returncode == 0:
            print(f"✅ Test PASSED for Agent {agent_num} after build_cleaner!")
            return True, retry_full_output_path
        else:
            print(
                f"❌ Test still failing for Agent {agent_num} after build_cleaner, proceeding..."
            )
            # Process the retry failure
            retry_output_content, retry_failure_path = process_test_failure(
                retry_result, "_retry"
            )
            return False, retry_failure_path

    # Regular test failure without build errors
    return False, failure_path


def save_agent_changes(artifacts_dir: str, agent_num: int) -> str:
    """Save current changes made by an agent."""
    result = run_shell_command("hg diff")

    changes_path = os.path.join(artifacts_dir, f"agent_{agent_num}_changes.diff")
    with open(changes_path, "w") as f:
        f.write(result.stdout)

    return changes_path


def rollback_changes():
    """Rollback any uncommitted changes."""
    run_shell_command("hg update --clean .", capture_output=False)


def run_research_workflow(artifacts_dir: str) -> tuple[bool, List[str]]:
    """Run the failed-test-research workflow and return success status and research artifacts."""
    try:
        # Import here to avoid circular imports
        from failed_test_research_workflow import FailedTestResearchWorkflow

        print("Running failed-test-research workflow after 5 failed attempts...")
        research_workflow = FailedTestResearchWorkflow(artifacts_dir)
        research_success = research_workflow.run()

        research_artifacts = []
        if research_success:
            print("✅ Research workflow completed successfully!")
            # Add research artifacts
            research_summary_path = os.path.join(artifacts_dir, "research_summary.md")
            research_resources_path = os.path.join(
                artifacts_dir, "research_resources.txt"
            )

            if os.path.exists(research_summary_path):
                research_artifacts.append(research_summary_path)
            if os.path.exists(research_resources_path):
                research_artifacts.append(research_resources_path)
        else:
            print("❌ Research workflow failed")

        return research_success, research_artifacts

    except Exception as e:
        print(f"Error running research workflow: {e}")
        return False, []


def build_agent_prompt(state: TestFixState, initial_artifacts: List[str]) -> str:
    """Build the prompt for the current agent."""
    agent_num = state["current_agent"]

    prompt = f"""You are Agent {agent_num} in a test-fixing workflow. Your goal is to analyze and fix a failing test.

CONTEXT:
- Test command: {state["test_command"]}
- This is attempt {agent_num} of {state["max_agents"]} to fix the test"""

    # Add special context for agents 6-10 if research was completed
    if agent_num > 5 and state["research_completed"]:
        prompt += """
- IMPORTANT: The first 5 agents failed to fix this test, so a research workflow was run to discover new insights and resources
- You now have access to research findings that should help you succeed where previous agents failed"""

    prompt += """

AVAILABLE ARTIFACTS:
"""

    # Add initial artifacts
    for artifact in initial_artifacts:
        prompt += f"- {artifact}\n"

    # Add artifacts from previous agents
    if state["agent_artifacts"]:
        prompt += "\nPREVIOUS AGENT ARTIFACTS:\n"
        for artifact in state["agent_artifacts"]:
            prompt += f"- {artifact}\n"

    # Add research artifacts for agents 6-10
    if agent_num > 5 and state["research_artifacts"]:
        prompt += "\nRESEARCH FINDINGS (NEW - USE THESE TO GUIDE YOUR APPROACH):\n"
        for artifact in state["research_artifacts"]:
            prompt += f"- {artifact}\n"

    prompt += """
INSTRUCTIONS:
1. Analyze the test failure and the provided context
2. Identify the root cause of the test failure
3. Make the necessary code changes to fix the test
4. Be specific about what files you're modifying and why
5. Focus on making minimal, targeted changes"""

    # Add special instructions for agents 6-10
    if agent_num > 5 and state["research_completed"]:
        prompt += """
6. CRITICAL: Review the research findings carefully - they contain new insights and resources discovered after the first 5 attempts failed
7. Use the research findings to guide your approach and avoid repeating the same mistakes as previous agents
8. Pay special attention to any new resources, similar issues, or alternative approaches identified in the research"""

    prompt += """

Your response should include:
- Analysis of the test failure
- Explanation of your fix approach"""

    if agent_num > 5 and state["research_completed"]:
        prompt += """
- How you're incorporating insights from the research findings"""

    return prompt


def initialize_workflow(state: TestFixState) -> TestFixState:
    """Initialize the workflow by setting up artifacts and extracting test info."""
    print(f"Initializing workflow for test file: {state['test_file_path']}")

    # Create artifacts directory
    artifacts_dir = create_artifacts_directory()
    print(f"Created artifacts directory: {artifacts_dir}")

    # Extract test command
    test_command = extract_test_command(state["test_file_path"])
    print(f"Extracted test command: {test_command}")

    # Create initial artifacts
    test_output_artifact = create_test_output_artifact(
        state["test_file_path"], artifacts_dir
    )
    hdesc_artifact = create_hdesc_artifact(artifacts_dir)
    diff_artifact = create_diff_artifact(artifacts_dir)

    initial_artifacts = [test_output_artifact, hdesc_artifact, diff_artifact]
    print(f"Created initial artifacts: {initial_artifacts}")

    return {
        **state,
        "artifacts_dir": artifacts_dir,
        "test_command": test_command,
        "current_agent": 1,
        "max_agents": 10,
        "test_passed": False,
        "agent_artifacts": [],
        "research_completed": False,
        "research_artifacts": [],
        "messages": [],
    }


def run_agent(state: TestFixState) -> TestFixState:
    """Run the current agent to attempt fixing the test."""
    agent_num = state["current_agent"]
    print(f"Running Agent {agent_num}")

    # Build prompt for this agent - include initial artifacts for ALL agents
    initial_artifacts = []
    artifacts_dir = state["artifacts_dir"]
    for filename in ["test_output.txt", "cl_description.txt", "current_diff.txt"]:
        artifact_path = os.path.join(artifacts_dir, filename)
        if os.path.exists(artifact_path):
            initial_artifacts.append(artifact_path)

    prompt = build_agent_prompt(state, initial_artifacts)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print(f"Agent {agent_num} response received")

    # Save the agent's response as an artifact
    response_path = os.path.join(
        state["artifacts_dir"], f"agent_{agent_num}_response.txt"
    )
    with open(response_path, "w") as f:
        f.write(response.content)

    return {**state, "messages": messages + [response]}


def test_and_evaluate(state: TestFixState) -> TestFixState:
    """Run the test and evaluate if it passes."""
    agent_num = state["current_agent"]
    print(f"Testing changes from Agent {agent_num}")

    # Run the test
    test_passed, test_output_path = run_test_and_check(
        state["test_command"], state["artifacts_dir"], agent_num
    )

    if test_passed:
        print(f"✅ Test PASSED after Agent {agent_num}!")
        return {**state, "test_passed": True}
    else:
        print(f"❌ Test still failing after Agent {agent_num}")

        # Save current changes before rolling back
        changes_path = save_agent_changes(state["artifacts_dir"], agent_num)
        print(f"Saved changes to: {changes_path}")

        # Add artifacts from this agent
        new_artifacts = state["agent_artifacts"] + [changes_path, test_output_path]

        # Check if we should run research workflow after 5th failure
        research_completed = state["research_completed"]
        research_artifacts = state["research_artifacts"]

        if agent_num == 5 and not research_completed:
            # Run research workflow after 5th failed attempt
            research_success, new_research_artifacts = run_research_workflow(
                state["artifacts_dir"]
            )
            research_completed = research_success
            research_artifacts = new_research_artifacts

        # Rollback changes if this isn't the last agent
        if agent_num < state["max_agents"]:
            print("Rolling back changes...")
            rollback_changes()

        return {
            **state,
            "test_passed": False,
            "agent_artifacts": new_artifacts,
            "research_completed": research_completed,
            "research_artifacts": research_artifacts,
            "current_agent": agent_num + 1,
        }


def should_continue(state: TestFixState) -> str:
    """Determine if the workflow should continue or end."""
    if state["test_passed"]:
        return "success"
    elif state["current_agent"] > state["max_agents"]:
        return "failure"
    else:
        return "continue"


def handle_success(state: TestFixState) -> TestFixState:
    """Handle successful test fix."""
    print(
        f"""
🎉 SUCCESS! Test has been fixed by Agent {state['current_agent'] - 1}!

Artifacts saved in: {state['artifacts_dir']}
Test command: {state['test_command']}
"""
    )

    # Run bam command to signal workflow completion
    try:
        run_shell_command(
            'bam 3 0.1 "LangGraph Workflow is Complete!"', capture_output=False
        )
    except Exception as e:
        print(f"Warning: Failed to run bam command: {e}")

    return state


def handle_failure(state: TestFixState) -> TestFixState:
    """Handle workflow failure."""
    print(
        f"""
❌ FAILURE! Unable to fix test after {state['max_agents']} attempts.

Artifacts saved in: {state['artifacts_dir']}
Test command: {state['test_command']}

Now generating a YAQs question to help get community assistance...
"""
    )

    # Import here to avoid circular imports
    from failed_test_summary_workflow import FailedTestSummaryWorkflow

    # Run the YAQs workflow to generate a question
    try:
        print("Running failed-test-summary workflow...")
        yaqs_workflow = FailedTestSummaryWorkflow(state["artifacts_dir"])
        yaqs_success = yaqs_workflow.run()

        if yaqs_success:
            print("✅ YAQs question generated successfully!")
        else:
            print("❌ Failed to generate YAQs question")

    except Exception as e:
        print(f"Error running YAQs workflow: {e}")

    # Run bam command to signal workflow completion
    try:
        run_shell_command(
            'bam 3 0.1 "LangGraph Workflow is Complete!"', capture_output=False
        )
    except Exception as e:
        print(f"Warning: Failed to run bam command: {e}")

    return state


class FixTestWorkflow(BaseWorkflow):
    """A workflow for fixing failing tests using AI agents."""

    def __init__(self, test_file_path: str):
        self.test_file_path = test_file_path

    @property
    def name(self) -> str:
        return "fix-test"

    @property
    def description(self) -> str:
        return "Fix failing tests using AI agents"

    def create_workflow(self):
        """Create and return the LangGraph workflow."""
        workflow = StateGraph(TestFixState)

        # Add nodes
        workflow.add_node("initialize", initialize_workflow)
        workflow.add_node("run_agent", run_agent)
        workflow.add_node("test_and_evaluate", test_and_evaluate)
        workflow.add_node("success", handle_success)
        workflow.add_node("failure", handle_failure)

        # Add edges
        workflow.add_edge(START, "initialize")
        workflow.add_edge("initialize", "run_agent")
        workflow.add_edge("run_agent", "test_and_evaluate")

        # Add conditional edges
        workflow.add_conditional_edges(
            "test_and_evaluate",
            should_continue,
            {"continue": "run_agent", "success": "success", "failure": "failure"},
        )

        workflow.add_edge("success", END)
        workflow.add_edge("failure", END)

        return workflow.compile()

    def run(self) -> bool:
        """Run the workflow and return True if successful, False otherwise."""
        if not os.path.exists(self.test_file_path):
            print(f"Error: Test file '{self.test_file_path}' does not exist")
            return False

        # Create and run the workflow
        app = self.create_workflow()

        initial_state: TestFixState = {
            "test_file_path": self.test_file_path,
            "artifacts_dir": "",
            "test_command": "",
            "current_agent": 1,
            "max_agents": 10,
            "test_passed": False,
            "failure_reason": None,
            "agent_artifacts": [],
            "research_completed": False,
            "research_artifacts": [],
            "messages": [],
        }

        try:
            final_state = app.invoke(initial_state)
            return final_state["test_passed"]
        except Exception as e:
            print(f"Error running workflow: {e}")
            return False
