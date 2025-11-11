"""Workflow for addressing Critique change request comments using Gemini AI."""

import os
import sys
from typing import NoReturn

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import print_artifact_created, print_status, print_workflow_header
from shared_utils import (
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


def _create_critique_comments_artifact(artifacts_dir: str) -> str:
    """Create artifact with critique_comments output."""
    result = run_shell_command("critique_comments", capture_output=True)

    artifact_path = os.path.join(artifacts_dir, "critique_comments.json")
    with open(artifact_path, "w") as f:
        f.write(result.stdout)

    return artifact_path


def _build_crs_prompt(
    artifacts_dir: str, context_file_directory: str | None = None
) -> str:
    """Build the change request prompt with context from artifacts."""
    prompt = f"""Can you help me address the Critique comments? Read all of the files below VERY carefully to make sure that the changes
you make align with the overall goal of this CL! For any reviewer comments that do not require code changes, explain why
and recomment a reply to send to the reviewer.

# AVAILABLE CONTEXT FILES
* @{artifacts_dir}/cl_changes.diff - A diff of the changes made by this CL
* @{artifacts_dir}/cl_desc.txt - This CL's description
* @{artifacts_dir}/critique_comments.json - Unresolved Critique comments left on this CL (these are the comments you should address!)
"""

    # Add context files from the directory if provided
    if context_file_directory and os.path.isdir(context_file_directory):
        context_files = [
            os.path.join(context_file_directory, f)
            for f in os.listdir(context_file_directory)
            if f.endswith((".md", ".txt"))
        ]
        if context_files:
            prompt += "\n# ADDITIONAL CONTEXT\n"
            for context_file in sorted(context_files):
                prompt += f"* @{context_file}\n"

    return prompt


class CrsWorkflow(BaseWorkflow):
    """A workflow for addressing Critique change request comments."""

    def __init__(self, context_file_directory: str | None = None) -> None:
        """Initialize CRS workflow.

        Args:
            context_file_directory: Optional directory containing markdown files to add to the prompt
        """
        self.context_file_directory = context_file_directory

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
        artifacts_dir = create_artifacts_directory()
        print_status(f"Created artifacts directory: {artifacts_dir}", "success")

        # Initialize the gai.md log
        initialize_gai_log(artifacts_dir, "crs", workflow_tag)

        # Copy context files to local .gai/context/ directory
        local_context_dir = copy_design_docs_locally([self.context_file_directory])

        # Create initial artifacts
        print_status("Creating artifacts...", "progress")

        diff_artifact = _create_branch_diff_artifact(artifacts_dir)
        print_artifact_created(diff_artifact)

        desc_artifact = _create_hdesc_artifact(artifacts_dir)
        print_artifact_created(desc_artifact)

        critique_artifact = _create_critique_comments_artifact(artifacts_dir)
        print_artifact_created(critique_artifact)

        # Build the prompt
        print_status("Building change request prompt...", "progress")
        prompt = _build_crs_prompt(artifacts_dir, local_context_dir)

        # Call Gemini
        print_status("Calling Gemini to address change requests...", "progress")
        model = GeminiCommandWrapper(model_size="big")
        model.set_logging_context(
            agent_type="crs",
            iteration=1,
            workflow_tag=workflow_tag,
            artifacts_dir=artifacts_dir,
        )

        messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
        response = model.invoke(messages)

        # Save the response
        response_path = os.path.join(artifacts_dir, "crs_response.txt")
        with open(response_path, "w") as f:
            f.write(ensure_str_content(response.content))
        print_artifact_created(response_path)

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
