"""Workflow for addressing Critique change request comments using Gemini AI."""

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


def _create_critique_comments_artifact(artifacts_dir: str) -> str:
    """Create artifact with critique_comments output."""
    result = run_shell_command("critique_comments", capture_output=True)

    artifact_path = os.path.join(artifacts_dir, "critique_comments.json")
    with open(artifact_path, "w") as f:
        f.write(result.stdout)

    return artifact_path


def _build_crs_prompt(
    critique_comments_path: str, context_file_directory: str | None = None
) -> str:
    """Build the change request prompt with context from artifacts.

    Args:
        critique_comments_path: Path to the critique comments JSON file
        context_file_directory: Optional directory containing context files

    Returns:
        The formatted prompt string
    """
    prompt = f"""Can you help me address the Critique comments? Read all of the files below VERY carefully to make sure that the changes
you make align with the overall goal of this CL! Make the necessary file changes, but do NOT amend/upload the CL.

x::this_cl
+ @{critique_comments_path} - Unresolved Critique comments left on this CL (these are the comments you should address!)
"""

    # Add context files from the directory if provided
    if context_file_directory and os.path.isdir(context_file_directory):
        context_files = [
            os.path.join(context_file_directory, f)
            for f in os.listdir(context_file_directory)
            if f.endswith((".md", ".txt"))
        ]
        if context_files:
            prompt += "\n### ADDITIONAL CONTEXT\n"
            for context_file in sorted(context_files):
                prompt += f"+ @{context_file}\n"

    return prompt


class CrsWorkflow(BaseWorkflow):
    """A workflow for addressing Critique change request comments."""

    def __init__(self, context_file_directory: str | None = None) -> None:
        """Initialize CRS workflow.

        Args:
            context_file_directory: Optional directory containing markdown files to add to the prompt
        """
        self.context_file_directory = context_file_directory
        self.response_path: str | None = None

    @property
    def name(self) -> str:
        return "crs"

    @property
    def description(self) -> str:
        return "Address Critique change request comments on a CL"

    def run(self) -> bool:
        """Run the change request workflow."""
        # Generate unique workflow tag
        workflow_tag = generate_workflow_tag()

        # Print workflow header
        print_workflow_header("crs", workflow_tag)

        print_status("Initializing change request (crs) workflow", "info")

        # Create artifacts directory
        artifacts_dir = create_artifacts_directory("crs")
        print_status(f"Created artifacts directory: {artifacts_dir}", "success")

        # Initialize the gai.md log
        initialize_gai_log(artifacts_dir, "crs", workflow_tag)

        # Create critique comments artifact
        print_status("Creating artifacts...", "progress")
        critique_artifact = _create_critique_comments_artifact(artifacts_dir)
        print_artifact_created(critique_artifact)

        # Build the prompt
        print_status("Building change request prompt...", "progress")
        prompt = _build_crs_prompt(critique_artifact, self.context_file_directory)

        # Call Gemini
        print_status("Calling Gemini to address change requests...", "progress")
        model = GeminiCommandWrapper(model_size="big")
        model.set_logging_context(
            agent_type="crs",
            iteration=1,
            workflow_tag=workflow_tag,
            artifacts_dir=artifacts_dir,
            workflow="crs",
        )

        messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
        response = model.invoke(messages)

        # Save the response
        self.response_path = os.path.join(artifacts_dir, "crs_response.txt")
        with open(self.response_path, "w") as f:
            f.write(ensure_str_content(response.content))
        print_artifact_created(self.response_path)

        print_status("Change request analysis complete!", "success")

        # Finalize the gai.md log
        finalize_gai_log(artifacts_dir, "crs", workflow_tag, True)

        # Run bam command to signal completion
        run_bam_command("CRS Workflow Complete!")

        return True


def main() -> NoReturn:
    """Main entry point for the crs workflow."""
    workflow = CrsWorkflow()
    success = workflow.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
