import os
from typing import Any, TypedDict

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from rich_utils import (
    print_artifact_created,
    print_status,
    print_test_result,
    print_workflow_failure,
    print_workflow_header,
    print_workflow_success,
)
from shared_utils import (
    LANGGRAPH_RECURSION_LIMIT,
    create_artifacts_directory,
    ensure_str_content,
    finalize_gai_log,
    generate_workflow_tag,
    initialize_gai_log,
    run_bam_command,
    run_shell_command,
    run_shell_command_with_input,
    safe_hg_amend,
)
from workflow_base import BaseWorkflow


def _create_hdesc_artifact(artifacts_dir: str) -> str:
    """Create artifact with hdesc output."""
    result = run_shell_command("hdesc")

    artifact_path = os.path.join(artifacts_dir, "cl_description.txt")
    with open(artifact_path, "w") as f:
        f.write(result.stdout)

    return artifact_path


def _create_diff_artifact(artifacts_dir: str) -> str:
    """Create artifact with hg pdiff output."""
    cmd = "hg pdiff $(branch_changes | grep -v -E 'png$|fingerprint$|BUILD$|recordio$')"
    result = run_shell_command(cmd)

    artifact_path = os.path.join(artifacts_dir, "cl_diff.txt")
    with open(artifact_path, "w") as f:
        f.write(result.stdout)

    return artifact_path


class AddTestsState(TypedDict):
    test_file: str
    test_cmd: str
    query: str | None
    spec: str
    num_test_runs: int
    artifacts_dir: str
    initial_artifacts: list[str]
    tests_added: bool
    tests_passed: bool
    failure_reason: str | None
    messages: list[HumanMessage | AIMessage]
    test_output_file: str | None
    workflow_tag: str


def _build_add_tests_prompt(state: AddTestsState) -> str:
    """Build the prompt for adding new tests."""
    test_file = state["test_file"]

    prompt = f"""You are an expert test engineer tasked with adding new tests to an existing test file. Your goal is to add comprehensive, well-designed tests that follow the existing patterns and conventions in the test file.

CONTEXT:
* Test file: @{test_file}"""

    if state.get("query"):
        prompt += f"""
* Additional requirements: {state["query"]}"""

    # Add information about available artifacts
    initial_artifacts = state.get("initial_artifacts", [])
    if initial_artifacts:
        prompt += """

AVAILABLE CONTEXT ARTIFACTS:"""
        for artifact_path in initial_artifacts:
            prompt += f"""
* @{artifact_path}
"""

    prompt += """

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
   - Use this exact command: `gai_test @{state["artifacts_dir"]} add_tests_agent`
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
    # Generate unique workflow tag first
    workflow_tag = generate_workflow_tag()

    # Print workflow header
    print_workflow_header("add-tests", workflow_tag)

    print_status(
        f"Initializing add-tests workflow for test file: {state['test_file']}", "info"
    )

    # Verify test file exists
    if not os.path.exists(state["test_file"]):
        return {
            **state,
            "tests_added": False,
            "failure_reason": f"Test file '{state['test_file']}' does not exist",
        }

    print_status(f"Generated workflow tag: {workflow_tag}", "success")

    # Create artifacts directory
    artifacts_dir = create_artifacts_directory()
    print_status(f"Created artifacts directory: {artifacts_dir}", "success")

    # Initialize the gai.md log with the artifacts directory and workflow tag
    initialize_gai_log(artifacts_dir, "add-tests", workflow_tag)

    # Create test runs limit file
    test_runs_limit_file = os.path.join(artifacts_dir, "test_runs_limit.txt")
    with open(test_runs_limit_file, "w") as f:
        f.write(str(state["num_test_runs"]))

    # Create initial artifacts (same as fix-test workflow)
    hdesc_artifact = _create_hdesc_artifact(artifacts_dir)
    print_artifact_created(hdesc_artifact)
    diff_artifact = _create_diff_artifact(artifacts_dir)
    print_artifact_created(diff_artifact)

    # Create test_output.txt with the test command for gai_test to read
    test_output_artifact = os.path.join(artifacts_dir, "test_output.txt")

    # Read the original test output file and pipe it through trim_test_output
    try:
        test_output_file = state["test_output_file"]
        if not test_output_file:
            raise ValueError("test_output_file is not set")
        with open(test_output_file) as f:
            original_output = f.read()

        # Pipe through trim_test_output
        trim_result = run_shell_command_with_input(
            "trim_test_output", original_output, capture_output=True
        )
        if trim_result.returncode == 0:
            trimmed_output = trim_result.stdout
        else:
            # If trim_test_output fails, use original output
            trimmed_output = original_output
            print_status(
                "trim_test_output command failed, using original output", "warning"
            )
    except Exception as e:
        print_status(f"Could not process test output file: {e}", "warning")
        trimmed_output = f"# {state['test_cmd']}\nInitial test output placeholder\n"

    with open(test_output_artifact, "w") as f:
        f.write(f"# {state['test_cmd']}\n")
        f.write(trimmed_output)
    print_artifact_created(test_output_artifact)

    initial_artifacts = [hdesc_artifact, diff_artifact, test_output_artifact]
    print_status(f"Created {len(initial_artifacts)} initial artifacts", "success")

    return {
        **state,
        "artifacts_dir": artifacts_dir,
        "workflow_tag": workflow_tag,
        "initial_artifacts": initial_artifacts,
        "tests_added": False,
        "tests_passed": False,
        "messages": [],
    }


def add_tests_with_agent(state: AddTestsState) -> AddTestsState:
    """Use Gemini agent to add new tests to the test file."""
    print_status("Running Gemini agent to add new tests...", "progress")

    # Build prompt for adding tests
    prompt = _build_add_tests_prompt(state)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    model.set_logging_context(
        agent_type="add_tests",
        iteration=1,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
    )
    messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print_status("Gemini agent response received", "success")

    # Save the agent's response as an artifact
    response_path = os.path.join(state["artifacts_dir"], "add_tests_agent_response.txt")
    with open(response_path, "w") as f:
        f.write(ensure_str_content(response.content))
    print_artifact_created(response_path)

    return {**state, "tests_added": True, "messages": messages + [response]}


def run_tests_with_gai_test(state: AddTestsState) -> AddTestsState:
    """Run the test using gai_test script."""
    print_status("Running tests with gai_test...", "progress")

    agent_name = "add_tests_agent"

    # Run gai_test with the artifacts directory and agent name
    gai_test_cmd = f"gai_test {state['artifacts_dir']} {agent_name}"

    # Run the test command
    result = run_shell_command(gai_test_cmd, capture_output=True)

    # Save test output to artifacts, piping stdout through trim_test_output
    test_output_path = os.path.join(state["artifacts_dir"], "gai_test_output.txt")

    # Pipe stdout through trim_test_output if available
    trimmed_stdout = result.stdout
    if result.stdout:
        try:
            trim_result = run_shell_command_with_input(
                "trim_test_output", result.stdout, capture_output=True
            )
            if trim_result.returncode == 0:
                trimmed_stdout = trim_result.stdout
            else:
                print_status(
                    "trim_test_output command failed for gai_test output, using original",
                    "warning",
                )
        except Exception as e:
            print_status(f"Could not trim gai_test output: {e}", "warning")

    with open(test_output_path, "w") as f:
        f.write(f"Command: {gai_test_cmd}\n")
        f.write(f"Return code: {result.returncode}\n")
        f.write(f"STDOUT:\n{trimmed_stdout}\n")
        f.write(f"STDERR:\n{result.stderr}\n")
    print_artifact_created(test_output_path)

    # Check if tests passed
    tests_passed = result.returncode == 0

    # Print test results using Rich formatting
    print_test_result(gai_test_cmd, tests_passed, result.stdout)

    # Get the output file from last_test_file command for potential fix-tests workflow
    test_output_file = None
    try:
        last_test_result = run_shell_command("last_test_file", capture_output=True)
        if last_test_result.returncode == 0:
            test_output_file = last_test_result.stdout.strip()
            print_status(
                f"Test output file for potential fix-tests workflow: {test_output_file}",
                "info",
            )
    except Exception as e:
        print_status(f"Could not get last_test_file: {e}", "warning")

    return {**state, "tests_passed": tests_passed, "test_output_file": test_output_file}


def should_run_fix_tests(state: AddTestsState) -> str:
    """Determine if we should run fix-tests workflow or end successfully."""
    if state["tests_passed"]:
        return "success"
    else:
        return "run_fix_test"


def run_fix_tests_workflow(state: AddTestsState) -> AddTestsState:
    """Run the fix-tests workflow to fix failing tests."""
    print_status("Tests failed, running fix-tests workflow...", "progress")

    if not state.get("test_output_file"):
        return {
            **state,
            "failure_reason": "No test output file available for fix-tests workflow",
        }

    # Commit the new tests before running fix-tests workflow
    test_file = state["test_file"]
    filename = os.path.basename(test_file)
    workflow_tag = state.get("workflow_tag", "XXX")
    commit_msg = f"@AI({workflow_tag}) [add-tests] New tests added to {filename} - #1"

    print_status(f"Committing new tests with message: {commit_msg}", "progress")
    amend_successful = safe_hg_amend(commit_msg, use_unamend_first=False)

    if not amend_successful:
        print_status("Failed to commit new tests safely", "warning")
        # Continue anyway, as this shouldn't block the fix-tests workflow
    else:
        print_status("New tests committed successfully", "success")

    # Import here to avoid circular imports
    from fix_tests_workflow.main import FixTestsWorkflow

    try:
        # Create fix-tests workflow with the test command and output file
        test_output_file = state["test_output_file"]
        if not test_output_file:
            raise ValueError("test_output_file is required for fix-tests workflow")
        fix_workflow = FixTestsWorkflow(
            state["test_cmd"],
            test_output_file,
        )
        fix_success = fix_workflow.run()

        if fix_success:
            print_status(
                "Fix-tests workflow succeeded! Tests are now passing.", "success"
            )
            return {**state, "tests_passed": True}
        else:
            print_status("Fix-tests workflow failed to fix the tests.", "error")
            return {
                **state,
                "tests_passed": False,
                "failure_reason": "Fix-tests workflow failed to fix the tests",
            }
    except Exception as e:
        print_status(f"Error running fix-tests workflow: {e}", "error")
        return {
            **state,
            "tests_passed": False,
            "failure_reason": f"Error running fix-tests workflow: {str(e)}",
        }


def handle_success(state: AddTestsState) -> AddTestsState:
    """Handle successful test addition and execution."""
    success_message = f"""New tests have been added and are passing!

Test file: {state["test_file"]}
Test command: {state["test_cmd"]}
Artifacts saved in: {state["artifacts_dir"]}"""

    print_workflow_success("add-tests", success_message)

    # Run bam command to signal completion
    run_bam_command("Add-Tests Workflow Complete!")

    return state


def handle_failure(state: AddTestsState) -> AddTestsState:
    """Handle workflow failure."""
    failure_message = f"""Unable to add working tests.

Test file: {state["test_file"]}
Test command: {state["test_cmd"]}
Artifacts saved in: {state["artifacts_dir"]}"""

    failure_details = state.get("failure_reason", "Unknown error")

    print_workflow_failure("add-tests", failure_message, failure_details)

    return state


class AddTestsWorkflow(BaseWorkflow):
    """A workflow for adding new tests to existing test files."""

    def __init__(
        self,
        test_file: str,
        test_cmd: str,
        query: str | None = None,
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

    def create_workflow(self) -> Any:
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
            "workflow_tag": "",  # Will be set during initialization
        }

        try:
            final_state = app.invoke(
                initial_state, config={"recursion_limit": LANGGRAPH_RECURSION_LIMIT}
            )
            success = final_state["tests_passed"]

            # Finalize the gai.md log
            workflow_tag = final_state.get("workflow_tag", "UNKNOWN")
            artifacts_dir = final_state.get("artifacts_dir", "")
            if artifacts_dir:
                finalize_gai_log(artifacts_dir, "add-tests", workflow_tag, success)

            return success
        except Exception as e:
            print(f"Error running add-tests workflow: {e}")
            # Note: Cannot finalize log here as artifacts_dir is not available
            return False
