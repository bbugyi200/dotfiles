"""Workflow for reviewing CLs using Gemini AI."""

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


def _build_review_prompt(artifacts_dir: str) -> str:
    """Build the review prompt with context from artifacts."""
    prompt = f"""You are a Senior SWE who works at Google on the Google Ad Manager FE team. Can you help me review this CL for any of the
following anti-patterns, MODIFY THE CODE FILES to correct these anti-patterns (if any are found), run the relevant tests, and then
summarize what changes you made and why?:

+ Any code changes that are out-of-scope for this CL.
+ Any code changes that are unnecessary or overcomplicate this CL.
+ Any classes/functions/variables that COULD be made private, but are not private.
+ Any code that violates go/readability standards for the coding languages that are used in this CL.
+ Any classes/functions/variables that are defined in non-test code but only
used by test code. These class/function/variable definitions should be moved to
the test file that uses them (or a shared testing utilities library if multiple
test files use them).
+ Any test method that does NOT structure its statements using the Arrange, Act, Assert pattern. There should NEVER be a
blank line that breaks up one of these sections. Use comments if necessary to separate different parts of each section,
but NEVER specify the section name using a comment (ex: '# Act'). When no section has more than 1 top-level (ex: not
nested in a lambda expression block) statement, no blank lines are necessary. Otherwise, the sections should ALWAYS be
separated by a blank line.

IMPORTANT: Do NOT ask me for permission to make changes. Just make the changes directly in the code files.

# AVAILABLE CONTEXT FILES
* @{artifacts_dir}/cl_changes.diff - A diff of the changes made by this CL
* @{artifacts_dir}/cl_desc.txt - This CL's description
"""
    return prompt


class ReviewWorkflow(BaseWorkflow):
    """A workflow for reviewing CLs and suggesting improvements."""

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "review"

    @property
    def description(self) -> str:
        return "Review a CL for anti-patterns and suggest improvements"

    def run(self) -> bool:
        """Run the review workflow."""
        # Generate unique workflow tag
        workflow_tag = generate_workflow_tag()

        # Print workflow header
        print_workflow_header("review", workflow_tag)

        print_status("Initializing review workflow", "info")

        # Create artifacts directory
        artifacts_dir = create_artifacts_directory()
        print_status(f"Created artifacts directory: {artifacts_dir}", "success")

        # Initialize the gai.md log
        initialize_gai_log(artifacts_dir, "review", workflow_tag)

        # Create initial artifacts
        print_status("Creating artifacts...", "progress")

        diff_artifact = _create_branch_diff_artifact(artifacts_dir)
        print_artifact_created(diff_artifact)

        desc_artifact = _create_hdesc_artifact(artifacts_dir)
        print_artifact_created(desc_artifact)

        # Build the prompt
        print_status("Building review prompt...", "progress")
        prompt = _build_review_prompt(artifacts_dir)

        # Call Gemini
        print_status("Calling Gemini for CL review...", "progress")
        model = GeminiCommandWrapper(model_size="big")
        model.set_logging_context(
            agent_type="review",
            iteration=1,
            workflow_tag=workflow_tag,
            artifacts_dir=artifacts_dir,
        )

        messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
        response = model.invoke(messages)

        # Save the response
        response_path = os.path.join(artifacts_dir, "review_response.txt")
        with open(response_path, "w") as f:
            f.write(ensure_str_content(response.content))
        print_artifact_created(response_path)

        print_status("Review complete!", "success")

        # Finalize the gai.md log
        finalize_gai_log(artifacts_dir, "review", workflow_tag, True)

        # Run bam command to signal completion
        run_bam_command("Review Workflow Complete!")

        return True


def main() -> NoReturn:
    """Main entry point for the review workflow."""
    workflow = ReviewWorkflow()
    success = workflow.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
