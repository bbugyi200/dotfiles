"""Workflow for fixing test failures using Gemini AI (simplified version)."""

import os
import sys
from typing import NoReturn

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import print_artifact_created, print_status, print_workflow_header
from shared_utils import (
    create_artifacts_directory,
    ensure_str_content,
    finalize_gai_log,
    generate_workflow_tag,
    initialize_gai_log,
    run_bam_command,
    run_shell_command,
    run_shell_command_with_input,
)
from workflow_base import BaseWorkflow


def _create_branch_diff_artifact(artifacts_dir: str) -> str:
    """Create artifact with branch_diff output."""
    result = run_shell_command("branch_diff --color=never", capture_output=True)

    artifact_path = os.path.join(artifacts_dir, "cl_changes.diff")
    with open(artifact_path, "w") as f:
        f.write(result.stdout)

    return artifact_path


def _create_hdesc_artifact(artifacts_dir: str) -> str:
    """Create artifact with hdesc output."""
    result = run_shell_command("hdesc", capture_output=True)

    artifact_path = os.path.join(artifacts_dir, "cl_desc.txt")
    with open(artifact_path, "w") as f:
        f.write(result.stdout)

    return artifact_path


def _create_test_output_artifact(artifacts_dir: str) -> str:
    """Create artifact with test output from last_test_file piped through trim_test_output."""
    # Get the last test file path
    last_test_result = run_shell_command("last_test_file", capture_output=True)
    if last_test_result.returncode != 0:
        print_status("Could not get last_test_file", "warning")
        artifact_path = os.path.join(artifacts_dir, "test_output.txt")
        with open(artifact_path, "w") as f:
            f.write("Error: Could not get last test file\n")
        return artifact_path

    last_test_file = last_test_result.stdout.strip()

    # Read the test file content
    try:
        with open(last_test_file) as f:
            test_output = f.read()
    except Exception as e:
        print_status(f"Could not read test file {last_test_file}: {e}", "warning")
        artifact_path = os.path.join(artifacts_dir, "test_output.txt")
        with open(artifact_path, "w") as f:
            f.write(f"Error reading test file: {str(e)}\n")
        return artifact_path

    # Pipe through trim_test_output
    trim_result = run_shell_command_with_input(
        "trim_test_output", test_output, capture_output=True
    )
    if trim_result.returncode == 0:
        trimmed_output = trim_result.stdout
    else:
        print_status("trim_test_output failed, using original output", "warning")
        trimmed_output = test_output

    artifact_path = os.path.join(artifacts_dir, "test_output.txt")
    with open(artifact_path, "w") as f:
        f.write(trimmed_output)

    return artifact_path


def _create_submitted_cls_artifact(artifacts_dir: str, project_name: str) -> str:
    """Create artifact with submitted CLs for the project."""
    query = f"a:me is:submitted d:{project_name}"
    result = run_shell_command(f'clsurf "{query}"', capture_output=True)

    artifact_path = os.path.join(artifacts_dir, "submitted_cls.txt")
    with open(artifact_path, "w") as f:
        f.write(result.stdout)

    return artifact_path


def _build_fix_ez_tests_prompt(artifacts_dir: str) -> str:
    """Build the fix tests prompt with context from artifacts."""
    # Check if design docs directory exists
    design_docs_note = ""
    bb_design_dir = os.path.expanduser("~/bb/design")
    if os.path.isdir(bb_design_dir):
        design_docs_note = (
            f"\n+ The @{bb_design_dir} directory contains relevant design docs."
        )

    prompt = f"""Can you help me fix the test failure shown in the @{artifacts_dir}/test_output.txt file?
+ The @{artifacts_dir}/cl_desc.txt file contain's this CL's description.
+ The @{artifacts_dir}/cl_changes.diff file contains a diff of this CL's changes.
+ The @{artifacts_dir}/submitted_cls.txt file contains the output of a Critique query that searches for all submitted CLs for this project.{design_docs_note}

# AVAILABLE CONTEXT FILES

* @{artifacts_dir}/test_output.txt - Test failure output
* @{artifacts_dir}/cl_desc.txt - This CL's description
* @{artifacts_dir}/cl_changes.diff - A diff of this CL's changes
* @{artifacts_dir}/submitted_cls.txt - Submitted CLs for this project
"""
    return prompt


class FixEzTestsWorkflow(BaseWorkflow):
    """A workflow for fixing test failures (simplified version)."""

    def __init__(self, project_name: str) -> None:
        self.project_name = project_name

    @property
    def name(self) -> str:
        return "fix-ez-tests"

    @property
    def description(self) -> str:
        return "Fix test failures using Gemini AI (simplified version)"

    def run(self) -> bool:
        """Run the fix-ez-tests workflow."""
        # Generate unique workflow tag
        workflow_tag = generate_workflow_tag()

        # Print workflow header
        print_workflow_header("fix-ez-tests", workflow_tag)

        print_status(
            f"Initializing fix-ez-tests workflow for project: {self.project_name}",
            "info",
        )

        # Create artifacts directory
        artifacts_dir = create_artifacts_directory()
        print_status(f"Created artifacts directory: {artifacts_dir}", "success")

        # Initialize the gai.md log
        initialize_gai_log(artifacts_dir, "fix-ez-tests", workflow_tag)

        # Create initial artifacts
        print_status("Creating artifacts...", "progress")

        diff_artifact = _create_branch_diff_artifact(artifacts_dir)
        print_artifact_created(diff_artifact)

        desc_artifact = _create_hdesc_artifact(artifacts_dir)
        print_artifact_created(desc_artifact)

        test_output_artifact = _create_test_output_artifact(artifacts_dir)
        print_artifact_created(test_output_artifact)

        submitted_cls_artifact = _create_submitted_cls_artifact(
            artifacts_dir, self.project_name
        )
        print_artifact_created(submitted_cls_artifact)

        # Build the prompt
        print_status("Building fix-ez-tests prompt...", "progress")
        prompt = _build_fix_ez_tests_prompt(artifacts_dir)

        # Call Gemini
        print_status("Calling Gemini to fix test failures...", "progress")
        model = GeminiCommandWrapper()
        model.set_logging_context(
            agent_type="fix_ez_tests",
            iteration=1,
            workflow_tag=workflow_tag,
            artifacts_dir=artifacts_dir,
        )

        messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
        response = model.invoke(messages)

        # Save the response
        response_path = os.path.join(artifacts_dir, "fix_ez_tests_response.txt")
        with open(response_path, "w") as f:
            f.write(ensure_str_content(response.content))
        print_artifact_created(response_path)

        print_status("Test fix analysis complete!", "success")

        # Finalize the gai.md log
        finalize_gai_log(artifacts_dir, "fix-ez-tests", workflow_tag, True)

        # Run bam command to signal completion
        run_bam_command("Fix-Ez-Tests Workflow Complete!")

        return True


def main() -> NoReturn:
    """Main entry point for the fix-ez-tests workflow."""
    if len(sys.argv) < 2:
        print("Usage: fix-ez-tests <project_name>")
        sys.exit(1)

    project_name = sys.argv[1]
    workflow = FixEzTestsWorkflow(project_name)
    success = workflow.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
