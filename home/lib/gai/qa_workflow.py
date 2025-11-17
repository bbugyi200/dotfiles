"""Workflow for QA of CLs using Gemini AI."""

import os
import sys
from typing import NoReturn

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import print_artifact_created, print_status, print_workflow_header
from shared_utils import (
    copy_artifacts_locally,
    copy_design_docs_locally,
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


def _build_qa_prompt(
    local_artifacts: dict[str, str], context_file_directory: str | None
) -> str:
    """Build the QA prompt with context from artifacts.

    Args:
        local_artifacts: Dict mapping artifact names to their relative paths
        context_file_directory: Optional directory containing markdown context files.

    Returns:
        The complete QA prompt.
    """
    cl_changes_path = local_artifacts.get(
        "cl_changes_diff", "bb/gai/qa/cl_changes.diff"
    )
    cl_desc_path = local_artifacts.get("cl_desc_txt", "bb/gai/qa/cl_desc.txt")

    # Build context section
    context_section = ""
    if context_file_directory:
        if os.path.isfile(context_file_directory):
            # Single file - convert to relative path
            rel_path = os.path.relpath(context_file_directory)
            context_section = f"""
* @{rel_path} - Project context
"""
        elif os.path.isdir(context_file_directory):
            # Directory of files
            try:
                md_files = sorted(
                    [
                        f
                        for f in os.listdir(context_file_directory)
                        if f.endswith(".md") or f.endswith(".txt")
                    ]
                )
                if md_files:
                    for md_file in md_files:
                        file_path = os.path.join(context_file_directory, md_file)
                        # Convert to relative path
                        rel_path = os.path.relpath(file_path)
                        context_section += f"* @{rel_path} - {md_file}\n"
            except Exception as e:
                print(f"Warning: Could not list context files: {e}")
                # Convert to relative path
                rel_path = os.path.relpath(context_file_directory)
                context_section = f"* @{rel_path} - Project context directory\n"

    prompt = f"""You are a Senior SWE who works at Google on the Google Ad Manager FE team. Can you help me QA this CL for any of the
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

IMPORTANT: Do NOT modify any code that is outside the scope of this CL's pre-existing changes! Your job is to QA the
changes made by this CL, NOT to refactor unrelated code.

# AVAILABLE CONTEXT FILES
* @{cl_changes_path} - A diff of the changes made by this CL
* @{cl_desc_path} - This CL's description
{context_section}"""
    return prompt


class QaWorkflow(BaseWorkflow):
    """A workflow for QA of CLs and suggesting improvements."""

    def __init__(self, context_file_directory: str | None = None) -> None:
        """Initialize the QA workflow.

        Args:
            context_file_directory: Optional directory containing markdown files to add to
                the agent prompt (defaults to ~/.gai/context/<PROJECT>/).
        """
        self.context_file_directory = context_file_directory

    @property
    def name(self) -> str:
        return "qa"

    @property
    def description(self) -> str:
        return "QA a CL for anti-patterns and suggest improvements"

    def run(self) -> bool:
        """Run the QA workflow."""
        # Generate unique workflow tag
        workflow_tag = generate_workflow_tag()

        # Print workflow header
        print_workflow_header("qa", workflow_tag)

        print_status("Initializing QA workflow", "info")

        # Create artifacts directory
        artifacts_dir = create_artifacts_directory("qa")
        print_status(f"Created artifacts directory: {artifacts_dir}", "success")

        # Initialize the gai.md log
        initialize_gai_log(artifacts_dir, "qa", workflow_tag)

        # Copy context files to local bb/gai/context/ directory
        local_context_dir = copy_design_docs_locally([self.context_file_directory])

        # Create initial artifacts
        print_status("Creating artifacts...", "progress")

        diff_artifact = _create_branch_diff_artifact(artifacts_dir)
        print_artifact_created(diff_artifact)

        desc_artifact = _create_hdesc_artifact(artifacts_dir)
        print_artifact_created(desc_artifact)

        # Copy artifacts to local bb/gai/qa/ directory
        artifact_files = {
            "cl_changes_diff": diff_artifact,
            "cl_desc_txt": desc_artifact,
        }
        local_artifacts = copy_artifacts_locally(artifacts_dir, "qa", artifact_files)

        # Build the prompt
        print_status("Building QA prompt...", "progress")
        prompt = _build_qa_prompt(local_artifacts, local_context_dir)

        # Call Gemini
        print_status("Calling Gemini for CL QA...", "progress")
        model = GeminiCommandWrapper(model_size="big")
        model.set_logging_context(
            agent_type="qa",
            iteration=1,
            workflow_tag=workflow_tag,
            artifacts_dir=artifacts_dir,
        )

        messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
        response = model.invoke(messages)

        # Save the response
        response_path = os.path.join(artifacts_dir, "qa_response.txt")
        with open(response_path, "w") as f:
            f.write(ensure_str_content(response.content))
        print_artifact_created(response_path)

        print_status("QA complete!", "success")

        # Finalize the gai.md log
        finalize_gai_log(artifacts_dir, "qa", workflow_tag, True)

        # Run bam command to signal completion
        run_bam_command("QA Workflow Complete!")

        return True


def main() -> NoReturn:
    """Main entry point for the QA workflow."""
    workflow = QaWorkflow()
    success = workflow.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
