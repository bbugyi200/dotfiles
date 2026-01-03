"""Workflow for QA of CLs using Gemini AI."""

import os
import sys
from typing import NoReturn

from gai_utils import get_context_files
from gemini_wrapper import invoke_agent
from rich_utils import print_artifact_created, print_status
from shared_utils import (
    ensure_str_content,
    finalize_gai_log,
    initialize_workflow,
    run_bam_command,
)
from workflow_base import BaseWorkflow


def _build_qa_prompt(context_file_directory: str | None) -> str:
    """Build the QA prompt with context from artifacts.

    Args:
        context_file_directory: Optional directory containing markdown context files.

    Returns:
        The complete QA prompt.
    """
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
            # Directory of files - use get_context_files utility
            context_files = get_context_files(context_file_directory)
            for file_path in context_files:
                rel_path = os.path.relpath(file_path)
                filename = os.path.basename(file_path)
                context_section += f"* @{rel_path} - {filename}\n"

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

x::this_cl
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
        self.response_path: str | None = None

    @property
    def name(self) -> str:
        return "qa"

    @property
    def description(self) -> str:
        return "QA a CL for anti-patterns and suggest improvements"

    def run(self) -> bool:
        """Run the QA workflow."""
        # Initialize workflow (creates artifacts dir, prints header, initializes log)
        ctx = initialize_workflow("qa")

        # Build the prompt
        print_status("Building QA prompt...", "progress")
        prompt = _build_qa_prompt(self.context_file_directory)

        # Call Gemini
        print_status("Calling Gemini for CL QA...", "progress")
        response = invoke_agent(
            prompt,
            agent_type="qa",
            model_size="big",
            iteration=1,
            workflow_tag=ctx.workflow_tag,
            artifacts_dir=ctx.artifacts_dir,
            workflow="qa",
        )

        # Save the response
        self.response_path = os.path.join(ctx.artifacts_dir, "qa_response.txt")
        with open(self.response_path, "w") as f:
            f.write(ensure_str_content(response.content))
        print_artifact_created(self.response_path)

        print_status("QA complete!", "success")

        # Finalize the gai.md log
        finalize_gai_log(ctx.artifacts_dir, "qa", ctx.workflow_tag, True)

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
