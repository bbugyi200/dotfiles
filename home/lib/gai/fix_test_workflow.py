import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional, TypedDict

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
    messages: List[HumanMessage | AIMessage]


class GeminiCommandWrapper:
    def invoke(self, messages):
        query = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                query = msg.content
                break

        if not query:
            return AIMessage(content="No query found in messages")

        try:
            result = subprocess.run(
                [
                    "/google/bin/releases/gemini-cli/tools/gemini",
                    "--gfg",
                    "--yolo",
                    query,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return AIMessage(content=result.stdout.strip())
        except subprocess.CalledProcessError as e:
            return AIMessage(content=f"Error running gemini command: {e.stderr}")
        except Exception as e:
            return AIMessage(content=f"Error: {str(e)}")


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
    cmd = f"tac {test_file_path} | grep -m1 'There was 1 failure' -B1000 | tac"
    result = run_shell_command(cmd)

    artifact_name = f"test_output{suffix}.txt"
    artifact_path = os.path.join(artifacts_dir, artifact_name)

    with open(artifact_path, "w") as f:
        f.write(result.stdout)

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
    result = run_shell_command(test_command, capture_output=True)

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

    # Test failed, create trimmed output artifact
    # Write stdout to temp file first to avoid argument list too long error
    temp_output_path = os.path.join(artifacts_dir, f"agent_{agent_num}_temp_output.txt")
    with open(temp_output_path, "w") as f:
        f.write(result.stdout)

    trimmed_cmd = (
        f"tac {temp_output_path} | grep -m1 'There was 1 failure' -B1000 | tac"
    )
    trimmed_result = run_shell_command(trimmed_cmd)

    trimmed_output_path = os.path.join(
        artifacts_dir, f"agent_{agent_num}_test_failure.txt"
    )
    with open(trimmed_output_path, "w") as f:
        f.write(trimmed_result.stdout)

    # Clean up temp file
    try:
        os.remove(temp_output_path)
    except OSError:
        pass

    return False, trimmed_output_path


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


def build_agent_prompt(state: TestFixState, initial_artifacts: List[str]) -> str:
    """Build the prompt for the current agent."""
    agent_num = state["current_agent"]

    prompt = f"""You are Agent {agent_num} in a test-fixing workflow. Your goal is to analyze and fix a failing test.

CONTEXT:
- Test command: {state["test_command"]}
- This is attempt {agent_num} of {state["max_agents"]} to fix the test

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

    prompt += """
INSTRUCTIONS:
1. Analyze the test failure and the provided context
2. Identify the root cause of the test failure
3. Make the necessary code changes to fix the test
4. Be specific about what files you're modifying and why
5. Focus on making minimal, targeted changes

Your response should include:
- Analysis of the test failure
- Explanation of your fix approach

IMPORTANT: Do NOT attempt to run the test or verify the fix yourself; that will
be handled by the workflow.
"""

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
        "max_agents": 7,
        "test_passed": False,
        "agent_artifacts": [],
        "messages": [],
    }


def run_agent(state: TestFixState) -> TestFixState:
    """Run the current agent to attempt fixing the test."""
    agent_num = state["current_agent"]
    print(f"Running Agent {agent_num}")

    # Build prompt for this agent
    initial_artifacts = []
    if agent_num == 1:
        # Get initial artifacts from artifacts directory
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

        # Rollback changes if this isn't the last agent
        if agent_num < state["max_agents"]:
            print("Rolling back changes...")
            rollback_changes()

        return {
            **state,
            "test_passed": False,
            "agent_artifacts": new_artifacts,
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
    from fix_test_yaqs_workflow import FixTestYAQsWorkflow

    # Run the YAQs workflow to generate a question
    try:
        print("Running fix-test-yaqs workflow...")
        yaqs_workflow = FixTestYAQsWorkflow(state["artifacts_dir"])
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
            "max_agents": 7,
            "test_passed": False,
            "failure_reason": None,
            "agent_artifacts": [],
            "messages": [],
        }

        try:
            final_state = app.invoke(initial_state)
            return final_state["test_passed"]
        except Exception as e:
            print(f"Error running workflow: {e}")
            return False
