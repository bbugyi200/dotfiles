import os
from typing import List, Optional, TypedDict

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from shared_utils import (
    create_artifacts_directory,
    create_boxed_header,
    create_diff_artifact,
    create_hdesc_artifact,
    read_artifact_file,
    run_bam_command,
    run_shell_command,
)
from workflow_base import BaseWorkflow


class AddTestsState(TypedDict):
    test_file: str
    test_cmd: str
    query: Optional[str]
    spec: str
    num_test_runs: int
    artifacts_dir: str
    initial_artifacts: List[str]
    tests_added: bool
    tests_passed: bool
    failure_reason: Optional[str]
    messages: List[HumanMessage | AIMessage]
    test_output_file: Optional[str]


def read_test_file(test_file: str) -> str:
    """Read the content of the test file."""
    try:
        with open(test_file, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error reading {test_file}: {str(e)}"


def build_add_tests_prompt(state: AddTestsState) -> str:
    """Build the prompt for adding new tests."""
    test_file_content = read_test_file(state["test_file"])

    prompt = f"""You are an expert test engineer tasked with adding new tests to an existing test file. Your goal is to add comprehensive, well-designed tests that follow the existing patterns and conventions in the test file.

CONTEXT:
* Test file: {state["test_file"]}"""

    if state.get("query"):
        prompt += f"""
* Additional requirements: {state["query"]}"""

    # Add information about available artifacts
    initial_artifacts = state.get("initial_artifacts", [])
    if initial_artifacts:
        prompt += """

AVAILABLE CONTEXT ARTIFACTS:"""
        for artifact_path in initial_artifacts:
            artifact_name = os.path.basename(artifact_path)
            artifact_content = read_artifact_file(artifact_path)
            prompt += f"""
{create_boxed_header(artifact_name)}
{artifact_content}
"""

    prompt += f"""

EXISTING TEST FILE CONTENT:
```
{test_file_content}
```

YOUR TASK:
1. Analyze the existing test file to understand:
   - The testing framework being used
   - Naming conventions for test methods/functions
   - Code style and patterns
   - Types of tests already present
   - What functionality is being tested

2. Add new, meaningful tests that:
   - Follow the same patterns and conventions as existing tests
   - Test different scenarios, edge cases, or functionality not already covered
   - Are well-named and self-documenting
   - Include appropriate assertions and test data
   - Complement the existing test suite

3. IMPORTANT TEST EXECUTION REQUIREMENTS:
   - You should run the test using gai_test after adding your tests
   - Use this exact command: `gai_test {state["artifacts_dir"]} add_tests_agent`
   - If the test fails, analyze the failure and make necessary fixes to your new tests
   - gai_test has built-in rate limiting (controlled by -T option) and duplicate detection
   - Do NOT run the raw test command directly - always use gai_test
   - After fixing any issues, you should return your response and let the workflow handle further testing

INSTRUCTIONS:
* Make targeted, focused additions - don't rewrite the entire file
* Ensure your new tests are syntactically correct and follow best practices
* Add meaningful test cases that increase coverage or test important scenarios
* Be mindful of the existing test structure and don't break existing functionality
* If the test command fails after your additions, debug and fix the issues with your new tests

YOUR RESPONSE SHOULD INCLUDE:
* Analysis of the existing test file and testing patterns
* Description of what new tests you're adding and why
* The actual code changes you're making
* Results of running gai_test (subject to rate limiting)
* Any fixes you made if the initial test run failed

Focus on quality over quantity - a few well-designed tests are better than many poorly written ones.
"""

    return prompt


def initialize_add_tests_workflow(state: AddTestsState) -> AddTestsState:
    """Initialize the add-tests workflow."""
    print(f"Initializing add-tests workflow for test file: {state['test_file']}")

    # Verify test file exists
    if not os.path.exists(state["test_file"]):
        return {
            **state,
            "tests_added": False,
            "failure_reason": f"Test file '{state['test_file']}' does not exist",
        }

    # Create artifacts directory
    artifacts_dir = create_artifacts_directory()
    print(f"Created artifacts directory: {artifacts_dir}")

    # Create test runs limit file
    test_runs_limit_file = os.path.join(artifacts_dir, "test_runs_limit.txt")
    with open(test_runs_limit_file, "w") as f:
        f.write(str(state["num_test_runs"]))

    # Create initial artifacts (same as fix-test workflow)
    hdesc_artifact = create_hdesc_artifact(artifacts_dir)
    diff_artifact = create_diff_artifact(artifacts_dir)

    # Create test_output.txt with the test command for gai_test to read
    test_output_artifact = os.path.join(artifacts_dir, "test_output.txt")
    with open(test_output_artifact, "w") as f:
        f.write(f"# {state['test_cmd']}\n")
        f.write("Initial test output placeholder\n")

    initial_artifacts = [hdesc_artifact, diff_artifact, test_output_artifact]
    print(f"Created initial artifacts: {initial_artifacts}")

    return {
        **state,
        "artifacts_dir": artifacts_dir,
        "initial_artifacts": initial_artifacts,
        "tests_added": False,
        "tests_passed": False,
        "messages": [],
    }


def add_tests_with_agent(state: AddTestsState) -> AddTestsState:
    """Use Gemini agent to add new tests to the test file."""
    print("Running Gemini agent to add new tests...")

    # Build prompt for adding tests
    prompt = build_add_tests_prompt(state)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print("Gemini agent response received")

    # Save the agent's response as an artifact
    response_path = os.path.join(state["artifacts_dir"], "add_tests_agent_response.txt")
    with open(response_path, "w") as f:
        f.write(response.content)

    # Print the agent's response to stdout
    print("\n" + "=" * 80)
    print("ADD-TESTS AGENT RESPONSE:")
    print("=" * 80)
    print(response.content)
    print("=" * 80 + "\n")

    return {**state, "tests_added": True, "messages": messages + [response]}


def run_tests_with_gai_test(state: AddTestsState) -> AddTestsState:
    """Run the test using gai_test script."""
    print("Running tests with gai_test...")

    agent_name = "add_tests_agent"

    # Run gai_test with the artifacts directory and agent name
    gai_test_cmd = f"gai_test {state['artifacts_dir']} {agent_name}"
    print(f"Executing: {gai_test_cmd}")

    # Run the test command
    result = run_shell_command(gai_test_cmd, capture_output=True)

    # Save test output to artifacts
    test_output_path = os.path.join(state["artifacts_dir"], "gai_test_output.txt")
    with open(test_output_path, "w") as f:
        f.write(f"Command: {gai_test_cmd}\n")
        f.write(f"Return code: {result.returncode}\n")
        f.write(f"STDOUT:\n{result.stdout}\n")
        f.write(f"STDERR:\n{result.stderr}\n")

    # Check if tests passed
    tests_passed = result.returncode == 0

    if tests_passed:
        print("✅ Tests PASSED!")
    else:
        print("❌ Tests FAILED")

    # Print the gai_test output
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"gai_test stderr: {result.stderr}")

    # Get the output file from last_test_file command for potential fix-tests workflow
    test_output_file = None
    try:
        last_test_result = run_shell_command("last_test_file", capture_output=True)
        if last_test_result.returncode == 0:
            test_output_file = last_test_result.stdout.strip()
            print(
                f"Test output file for potential fix-tests workflow: {test_output_file}"
            )
    except Exception as e:
        print(f"Warning: Could not get last_test_file: {e}")

    return {**state, "tests_passed": tests_passed, "test_output_file": test_output_file}


def should_run_fix_tests(state: AddTestsState) -> str:
    """Determine if we should run fix-tests workflow or end successfully."""
    if state["tests_passed"]:
        return "success"
    else:
        return "run_fix_test"


def run_fix_tests_workflow(state: AddTestsState) -> AddTestsState:
    """Run the fix-tests workflow to fix failing tests."""
    print("Tests failed, running fix-tests workflow...")

    if not state.get("test_output_file"):
        return {
            **state,
            "failure_reason": "No test output file available for fix-tests workflow",
        }

    # Commit the new tests before running fix-tests workflow
    test_file = state["test_file"]
    filename = os.path.basename(test_file)
    commit_msg = f"@AI New tests added to {filename}"
    commit_cmd = f'hg amend -n "{commit_msg}"'

    print(f"Committing new tests with message: {commit_msg}")
    try:
        commit_result = run_shell_command(commit_cmd, capture_output=True)
        if commit_result.returncode != 0:
            print(f"Warning: Failed to commit new tests: {commit_result.stderr}")
            # Continue anyway, as this shouldn't block the fix-tests workflow
        else:
            print("✅ New tests committed successfully")
    except Exception as e:
        print(f"Warning: Error committing new tests: {e}")
        # Continue anyway, as this shouldn't block the fix-tests workflow

    # Import here to avoid circular imports
    from fix_tests_workflow.main import FixTestsWorkflow

    try:
        # Create fix-tests workflow with the test command and output file
        fix_workflow = FixTestsWorkflow(state["test_cmd"], state["test_output_file"])
        fix_success = fix_workflow.run()

        if fix_success:
            print("✅ Fix-tests workflow succeeded! Tests are now passing.")
            return {**state, "tests_passed": True}
        else:
            print("❌ Fix-tests workflow failed to fix the tests.")
            return {
                **state,
                "tests_passed": False,
                "failure_reason": "Fix-tests workflow failed to fix the tests",
            }
    except Exception as e:
        print(f"Error running fix-tests workflow: {e}")
        return {
            **state,
            "tests_passed": False,
            "failure_reason": f"Error running fix-tests workflow: {str(e)}",
        }


def handle_success(state: AddTestsState) -> AddTestsState:
    """Handle successful test addition and execution."""
    print(
        f"""
🎉 SUCCESS! New tests have been added and are passing!

Test file: {state['test_file']}
Test command: {state['test_cmd']}
Artifacts saved in: {state['artifacts_dir']}
"""
    )

    # Run bam command to signal completion
    run_bam_command("Add-Tests Workflow Complete!")

    return state


def handle_failure(state: AddTestsState) -> AddTestsState:
    """Handle workflow failure."""
    print(
        f"""
❌ FAILURE! Unable to add working tests.

Test file: {state['test_file']}
Test command: {state['test_cmd']}
Failure reason: {state.get('failure_reason', 'Unknown error')}
Artifacts saved in: {state['artifacts_dir']}
"""
    )

    return state


class AddTestsWorkflow(BaseWorkflow):
    """A workflow for adding new tests to existing test files."""

    def __init__(
        self,
        test_file: str,
        test_cmd: str,
        query: Optional[str] = None,
        spec: str = "2+2+2",
        num_test_runs: int = 1,
    ):
        self.test_file = test_file
        self.test_cmd = test_cmd
        self.query = query
        self.spec = spec
        self.num_test_runs = num_test_runs

    @property
    def name(self) -> str:
        return "add-tests"

    @property
    def description(self) -> str:
        return "Add new tests to existing test files and verify they pass"

    def create_workflow(self):
        """Create and return the LangGraph workflow."""
        workflow = StateGraph(AddTestsState)

        # Add nodes
        workflow.add_node("initialize", initialize_add_tests_workflow)
        workflow.add_node("add_tests", add_tests_with_agent)
        workflow.add_node("run_tests", run_tests_with_gai_test)
        workflow.add_node("run_fix_tests", run_fix_tests_workflow)
        workflow.add_node("success", handle_success)
        workflow.add_node("failure", handle_failure)

        # Add edges
        workflow.add_edge(START, "initialize")
        workflow.add_edge("initialize", "add_tests")
        workflow.add_edge("add_tests", "run_tests")
        workflow.add_edge(
            "run_fix_tests", "success"
        )  # fix_tests handles its own failure cases

        # Add conditional edges
        workflow.add_conditional_edges(
            "run_tests",
            should_run_fix_tests,
            {"success": "success", "run_fix_test": "run_fix_tests"},
        )

        # Handle initialization failure
        workflow.add_conditional_edges(
            "initialize",
            lambda state: "failure" if state.get("failure_reason") else "continue",
            {"failure": "failure", "continue": "add_tests"},
        )

        workflow.add_edge("success", END)
        workflow.add_edge("failure", END)

        return workflow.compile()

    def run(self) -> bool:
        """Run the workflow and return True if successful, False otherwise."""
        # Create and run the workflow
        app = self.create_workflow()

        initial_state: AddTestsState = {
            "test_file": self.test_file,
            "test_cmd": self.test_cmd,
            "query": self.query,
            "spec": self.spec,
            "num_test_runs": self.num_test_runs,
            "artifacts_dir": "",
            "initial_artifacts": [],
            "tests_added": False,
            "tests_passed": False,
            "failure_reason": None,
            "messages": [],
            "test_output_file": None,
        }

        try:
            final_state = app.invoke(initial_state)
            return final_state["tests_passed"]
        except Exception as e:
            print(f"Error running add-tests workflow: {e}")
            return False
