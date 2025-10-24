import os
from typing import List, Optional, TypedDict

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from shared_utils import (
    collect_all_artifacts,
    create_artifacts_directory,
    create_diff_artifact,
    create_hdesc_artifact,
    run_bam_command,
    run_shell_command,
)
from workflow_base import BaseWorkflow


class TestFixState(TypedDict):
    test_file_path: str
    artifacts_dir: str
    test_command: str
    spec: str
    num_test_runs: int
    agent_cycles: List[int]  # [2, 2, 2] for "2+2+2"
    current_cycle: int  # Which cycle we're in (0, 1, 2...)
    current_agent_in_cycle: int  # Which agent in current cycle (1, 2...)
    current_agent: int  # Global agent number
    max_agents: int
    test_passed: bool
    failure_reason: Optional[str]
    agent_artifacts: List[str]
    research_cycles: List[List[str]]  # Artifacts for each research cycle
    current_research_cycle: int  # Which research cycle we're in
    messages: List[HumanMessage | AIMessage]
    current_agent_response_path: Optional[str]


def parse_spec(spec: str) -> List[int]:
    """Parse the spec string into a list of agent cycle counts."""
    try:
        parts = spec.split("+")
        cycles = [int(part.strip()) for part in parts]
        if not cycles or any(c <= 0 for c in cycles):
            raise ValueError("All cycle counts must be positive integers")
        return cycles
    except (ValueError, AttributeError) as e:
        raise ValueError(
            f"Invalid spec format '{spec}'. Expected format: M[+N[+P[+...]]] where all values are positive integers"
        ) from e


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


def run_test_with_gai_test(artifacts_dir: str, agent_num: int) -> tuple[bool, str]:
    """Run the test using gai_test script and check if it passes."""

    # Use "fix-test" as agent name for workflow-controlled test runs
    agent_name = "fix-test"

    # Run gai_test for the workflow
    gai_test_cmd = f"gai_test {artifacts_dir} {agent_name}"
    print(f"Running: {gai_test_cmd}")

    result = run_shell_command(gai_test_cmd, capture_output=True)

    # gai_test manages all the test output and diff checking
    # We just need to check if it passed (return code 0) or failed
    test_passed = result.returncode == 0

    if test_passed:
        print(f"✅ Test PASSED for Agent {agent_num}!")
    else:
        print(f"❌ Test failed for Agent {agent_num}")

    # Print the gai_test output which includes the test results
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"gai_test stderr: {result.stderr}")

    # Create a summary file for this agent's test run
    summary_path = os.path.join(artifacts_dir, f"agent_{agent_num}_test_summary.txt")
    with open(summary_path, "w") as f:
        f.write(f"gai_test command: {gai_test_cmd}\n")
        f.write(f"Return code: {result.returncode}\n")
        f.write(f"STDOUT:\n{result.stdout}\n")
        f.write(f"STDERR:\n{result.stderr}\n")

    return test_passed, summary_path


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


def run_research_workflow_with_filtering(state: TestFixState) -> TestFixState:
    """Run research workflow with proper artifact filtering and cycle management."""
    current_cycle = state["current_cycle"]
    current_research_cycle = state["current_research_cycle"]
    artifacts_dir = state["artifacts_dir"]

    print(f"Running research workflow for cycle {current_cycle + 1}...")

    # Get artifacts created since the last research workflow
    # This includes artifacts from the current cycle only
    current_cycle_artifacts = []

    # Calculate the starting agent number for current cycle
    agents_before_current_cycle = sum(state["agent_cycles"][:current_cycle])
    agents_in_current_cycle = state["agent_cycles"][current_cycle]

    for agent_num in range(
        agents_before_current_cycle + 1,
        agents_before_current_cycle + agents_in_current_cycle + 1,
    ):
        # Add agent artifacts for this cycle
        for suffix in [
            "_response.txt",
            "_changes.diff",
            "_test_failure.txt",
            "_test_failure_retry.txt",
        ]:
            artifact_file = f"agent_{agent_num}{suffix}"
            artifact_path = os.path.join(artifacts_dir, artifact_file)
            if os.path.exists(artifact_path):
                current_cycle_artifacts.append(artifact_path)

    # Create a filtered research workflow
    research_success, new_research_artifacts = run_research_workflow_filtered(
        artifacts_dir,
        current_cycle_artifacts,
        state["research_cycles"],
        state["agent_cycles"],
        current_cycle,
    )

    # Update research cycles
    new_research_cycles = state["research_cycles"].copy()
    if research_success:
        new_research_cycles.append(new_research_artifacts)

    return {
        **state,
        "research_cycles": new_research_cycles,
        "current_research_cycle": current_research_cycle + 1,
        "current_cycle": current_cycle + 1,
        "current_agent_in_cycle": 1,  # Reset to first agent in new cycle
        "agent_artifacts": [],  # Clear agent artifacts for new cycle
    }


def run_research_workflow_filtered(
    artifacts_dir: str,
    current_cycle_artifacts: List[str],
    previous_research_cycles: List[List[str]],
    agent_cycles: List[int],
    current_cycle: int,
) -> tuple[bool, List[str]]:
    """Run the failed-test-research workflow and return success status and research artifacts."""
    try:
        # Import here to avoid circular imports
        from failed_test_research_workflow import FailedTestResearchWorkflow

        print("Running failed-test-research workflow with filtered artifacts...")
        research_workflow = FailedTestResearchWorkflow(
            artifacts_dir,
            current_cycle_artifacts,
            previous_research_cycles,
            agent_cycles,
            current_cycle,
        )
        research_success = research_workflow.run()

        research_artifacts = []
        if research_success:
            print("✅ Research workflow completed successfully!")
            # Add research artifacts with cycle number
            cycle_num = len(previous_research_cycles) + 1
            research_summary_path = os.path.join(
                artifacts_dir, f"research_summary_cycle_{cycle_num}.md"
            )
            research_resources_path = os.path.join(
                artifacts_dir, f"research_resources_cycle_{cycle_num}.txt"
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
* This is attempt {agent_num} of {state["max_agents"]} to fix the test"""

    # Add special context if we're in a cycle after research
    current_cycle = state["current_cycle"]
    if current_cycle > 0:
        prompt += f"""
* IMPORTANT: Previous agent cycles failed to fix this test, so research workflows were run to discover new insights and resources
* You are in cycle {current_cycle + 1} and have access to research findings that should help you succeed"""

    prompt += """

AVAILABLE ARTIFACTS (ALL PREVIOUS WORK AND RESEARCH):
"""

    # Use comprehensive artifact collection to get ALL artifacts
    artifacts_summary = collect_all_artifacts(
        state["artifacts_dir"], exclude_full_outputs=True
    )
    prompt += artifacts_summary

    prompt += f"""

INSTRUCTIONS:
* Analyze the test failure and the provided context
* Identify the root cause of the test failure
* Make the necessary code changes to fix the test
* Be specific about what files you're modifying and why
* Focus on making minimal, targeted changes
* IMPORTANT TEST REQUIREMENTS:
  - You SHOULD run the test using the gai_test command, but ONLY AFTER you attempt to fix the test.
  - Use this exact command: `gai_test {state["artifacts_dir"]} agent_{agent_num}`
  - After the gai_test command finishes running, if it failed, you should make changes to attempt to fix the test, reply to
    the user (see the response requirements above), and terminate so the agent controller / master can run the test
    command on its own and then spin up more agents if necessary.
  - Do NOT run gai_test multiple times - it has built-in rate limiting and duplicate detection.
  - Do NOT run the raw test command directly - always use gai_test.
"""

    # Add special instructions if we have research artifacts
    research_cycles = state["research_cycles"]
    if research_cycles:
        prompt += """
* CRITICAL: Review the research findings carefully - they contain new insights and resources discovered after previous cycles failed
* Use the research findings to guide your approach and avoid repeating the same mistakes as previous agents
* Pay special attention to any new resources, similar issues, or alternative approaches identified in the research
"""

    prompt += """

YOUR RESPONSE SHOULD INCLUDE:
* Analysis of the test failure
* Explanation of your fix approach"""

    current_agent_in_cycle = state["current_agent_in_cycle"]
    if current_agent_in_cycle > 1:
        prompt += """
* Reflection on why previous agents in this cycle may have failed and how your approach differs"""

    if research_cycles:
        prompt += """
* How you're incorporating insights from the research findings"""

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

    # Parse the spec and calculate total max agents
    agent_cycles = parse_spec(state["spec"])
    max_agents = sum(agent_cycles)

    # Create test runs limit file
    test_runs_limit_file = os.path.join(artifacts_dir, "test_runs_limit.txt")
    with open(test_runs_limit_file, "w") as f:
        f.write(str(state["num_test_runs"]))

    return {
        **state,
        "artifacts_dir": artifacts_dir,
        "test_command": test_command,
        "agent_cycles": agent_cycles,
        "current_cycle": 0,
        "current_agent_in_cycle": 1,
        "current_agent": 1,
        "max_agents": max_agents,
        "test_passed": False,
        "agent_artifacts": [],
        "research_cycles": [],
        "current_research_cycle": 0,
        "messages": [],
        "current_agent_response_path": None,
    }


def run_agent(state: TestFixState) -> TestFixState:
    """Run the current agent to attempt fixing the test."""
    agent_num = state["current_agent"]
    print(f"Running Agent {agent_num}")

    # Build prompt for this agent - comprehensive artifact collection is handled in build_agent_prompt
    prompt = build_agent_prompt(state, [])

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

    # Print the agent's response to stdout
    print("\n" + "=" * 80)
    print(f"AGENT {agent_num} RESPONSE:")
    print("=" * 80)
    print(response.content)
    print("=" * 80 + "\n")

    return {
        **state,
        "messages": messages + [response],
        "current_agent_response_path": response_path,
    }


def test_and_evaluate(state: TestFixState) -> TestFixState:
    """Run the test and evaluate if it passes."""
    agent_num = state["current_agent"]
    print(f"Testing changes from Agent {agent_num}")

    # Run the test using gai_test
    test_passed, test_output_path = run_test_with_gai_test(
        state["artifacts_dir"], agent_num
    )

    if test_passed:
        print(f"✅ Test PASSED after Agent {agent_num}!")

        # Show the successful changes made by this agent
        changes_path = save_agent_changes(state["artifacts_dir"], agent_num)
        print(f"Successful changes saved to: {changes_path}")

        # Print the diff of successful changes
        try:
            with open(changes_path, "r") as f:
                diff_content = f.read()

            print("\n" + "=" * 80)
            print(f"AGENT {agent_num} SUCCESSFUL CHANGES DIFF:")
            print("=" * 80)
            if diff_content.strip():
                print(diff_content)
            else:
                print(
                    "No changes detected (test may have passed without code modifications)"
                )
            print("=" * 80 + "\n")
        except Exception as e:
            print(f"Warning: Could not read diff file {changes_path}: {e}")

        return {**state, "test_passed": True}
    else:
        print(f"❌ Test still failing after Agent {agent_num}")

        # Save current changes before rolling back
        changes_path = save_agent_changes(state["artifacts_dir"], agent_num)
        print(f"Saved changes to: {changes_path}")

        # Print the diff of changes made by this agent
        try:
            with open(changes_path, "r") as f:
                diff_content = f.read()

            print("\n" + "=" * 80)
            print(f"AGENT {agent_num} CHANGES DIFF:")
            print("=" * 80)
            if diff_content.strip():
                print(diff_content)
            else:
                print(
                    "No changes detected (agent may not have made any code modifications)"
                )
            print("=" * 80 + "\n")
        except Exception as e:
            print(f"Warning: Could not read diff file {changes_path}: {e}")

        # Add artifacts from this agent (including the response file)
        artifacts_to_add = [changes_path, test_output_path]
        if state.get("current_agent_response_path"):
            artifacts_to_add.append(state["current_agent_response_path"])
        new_artifacts = state["agent_artifacts"] + artifacts_to_add

        # Update cycle tracking
        current_cycle = state["current_cycle"]
        current_agent_in_cycle = state["current_agent_in_cycle"]
        agent_cycles = state["agent_cycles"]

        # Check if we've completed the current cycle
        if current_agent_in_cycle >= agent_cycles[current_cycle]:
            # Move to next cycle but don't increment current_agent_in_cycle yet
            # This will be handled in the research workflow transition
            next_agent_in_cycle = current_agent_in_cycle + 1
        else:
            next_agent_in_cycle = current_agent_in_cycle + 1

        return {
            **state,
            "test_passed": False,
            "agent_artifacts": new_artifacts,
            "current_agent_in_cycle": next_agent_in_cycle,
            "current_agent": agent_num + 1,
            "current_agent_response_path": None,
        }


def should_continue(state: TestFixState) -> str:
    """Determine if the workflow should continue or end."""
    if state["test_passed"]:
        return "success"
    elif state["current_agent"] > state["max_agents"]:
        return "failure"
    else:
        # Check if we need to run research workflow
        current_cycle = state["current_cycle"]
        current_agent_in_cycle = state["current_agent_in_cycle"]
        agent_cycles = state["agent_cycles"]

        # If we've completed the current cycle and there are more cycles
        if (
            current_agent_in_cycle > agent_cycles[current_cycle]
            and current_cycle < len(agent_cycles) - 1
        ):
            return "research"
        else:
            return "continue"


def handle_success(state: TestFixState) -> TestFixState:
    """Handle successful test fix."""
    print(
        f"""
🎉 SUCCESS! Test has been fixed by Agent {state['current_agent']}!

Artifacts saved in: {state['artifacts_dir']}
Test command: {state['test_command']}
"""
    )

    # Run bam command to signal workflow completion
    run_bam_command("LangGraph Workflow is Complete!")

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

    # Rollback any remaining changes before generating YAQs question
    print("Rolling back any remaining changes from final agent attempts...")
    rollback_changes()

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
    run_bam_command("LangGraph Workflow is Complete!")

    return state


class FixTestWorkflow(BaseWorkflow):
    """A workflow for fixing failing tests using AI agents."""

    def __init__(
        self, test_file_path: str, spec: str = "2+2+2", num_test_runs: int = 1
    ):
        self.test_file_path = test_file_path
        self.spec = spec
        self.num_test_runs = num_test_runs
        self.agent_cycles = parse_spec(spec)

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
        workflow.add_node("run_research", run_research_workflow_with_filtering)
        workflow.add_node("success", handle_success)
        workflow.add_node("failure", handle_failure)

        # Add edges
        workflow.add_edge(START, "initialize")
        workflow.add_edge("initialize", "run_agent")
        workflow.add_edge("run_agent", "test_and_evaluate")
        workflow.add_edge("run_research", "run_agent")

        # Add conditional edges
        workflow.add_conditional_edges(
            "test_and_evaluate",
            should_continue,
            {
                "continue": "run_agent",
                "research": "run_research",
                "success": "success",
                "failure": "failure",
            },
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
            "spec": self.spec,
            "num_test_runs": self.num_test_runs,
            "agent_cycles": [],
            "current_cycle": 0,
            "current_agent_in_cycle": 1,
            "current_agent": 1,
            "max_agents": 0,
            "test_passed": False,
            "failure_reason": None,
            "agent_artifacts": [],
            "research_cycles": [],
            "current_research_cycle": 0,
            "messages": [],
            "current_agent_response_path": None,
        }

        try:
            final_state = app.invoke(initial_state)
            return final_state["test_passed"]
        except Exception as e:
            print(f"Error running workflow: {e}")
            return False
