"""Workflow for addressing Critique change request comments using Gemini AI."""

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
    run_shell_command,
)
from workflow_base import BaseWorkflow


def _create_critique_comments_artifact(
    artifacts_dir: str, comments_file: str | None = None
) -> str:
    """Create artifact with critique_comments output.

    Args:
        artifacts_dir: Directory to create the artifact in.
        comments_file: Optional path to existing comments JSON file.
            If provided, copy from this file instead of running critique_comments.

    Returns:
        Path to the critique_comments.json artifact.
    """
    artifact_path = os.path.join(artifacts_dir, "critique_comments.json")

    # Expand ~ in path if present
    expanded_comments_file = (
        os.path.expanduser(comments_file) if comments_file else None
    )

    if expanded_comments_file and os.path.exists(expanded_comments_file):
        # Copy from existing comments file
        import shutil

        shutil.copy(expanded_comments_file, artifact_path)
    else:
        # Run critique_comments command
        result = run_shell_command("critique_comments", capture_output=True)
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

#cl
+ @{critique_comments_path} - Unresolved Critique comments left on this CL (these are the comments you should address!)
"""

    # Add context files from the directory if provided
    context_files = get_context_files(context_file_directory)
    if context_files:
        prompt += "\n### ADDITIONAL CONTEXT\n"
        for context_file in context_files:
            prompt += f"+ @{context_file}\n"

    return prompt


class CrsWorkflow(BaseWorkflow):
    """A workflow for addressing Critique change request comments."""

    def __init__(
        self,
        context_file_directory: str | None = None,
        comments_file: str | None = None,
    ) -> None:
        """Initialize CRS workflow.

        Args:
            context_file_directory: Optional directory containing markdown files to add to the prompt
            comments_file: Optional path to existing comments JSON file.
                If provided, copy from this file instead of running critique_comments.
        """
        self.context_file_directory = context_file_directory
        self.comments_file = comments_file
        self.response_path: str | None = None

    @property
    def name(self) -> str:
        return "crs"

    @property
    def description(self) -> str:
        return "Address Critique change request comments on a CL"

    def run(self) -> bool:
        """Run the change request workflow."""
        # Initialize workflow (creates artifacts dir, prints header, initializes log)
        ctx = initialize_workflow("crs")

        # Create critique comments artifact
        print_status("Creating artifacts...", "progress")
        critique_artifact = _create_critique_comments_artifact(
            ctx.artifacts_dir, self.comments_file
        )
        print_artifact_created(critique_artifact)

        # Build the prompt
        print_status("Building change request prompt...", "progress")
        prompt = _build_crs_prompt(critique_artifact, self.context_file_directory)

        # Call Gemini
        print_status("Calling Gemini to address change requests...", "progress")
        response = invoke_agent(
            prompt,
            agent_type="crs",
            model_size="big",
            iteration=1,
            workflow_tag=ctx.workflow_tag,
            artifacts_dir=ctx.artifacts_dir,
            workflow="crs",
        )

        # Save the response
        self.response_path = os.path.join(ctx.artifacts_dir, "crs_response.txt")
        with open(self.response_path, "w") as f:
            f.write(ensure_str_content(response.content))
        print_artifact_created(self.response_path)

        print_status("Change request analysis complete!", "success")

        # Finalize the gai.md log
        finalize_gai_log(ctx.artifacts_dir, "crs", ctx.workflow_tag, True)

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
