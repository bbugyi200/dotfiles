"""Workflow for addressing Critique change request comments using Gemini AI."""

import os
import sys
from typing import NoReturn

from llm_provider import invoke_agent
from main.query_handler import (
    execute_standalone_steps,
    expand_embedded_workflows_in_query,
)
from rich_utils import (
    print_artifact_created,
    print_status,
    print_workflow_header,
)
from shared_utils import (
    create_artifacts_directory,
    ensure_str_content,
    finalize_gai_log,
    generate_workflow_tag,
    initialize_gai_log,
    initialize_workflow,
    run_bam_command,
    run_shell_command,
)
from workflow_base import BaseWorkflow
from xprompt import escape_for_xprompt, process_xprompt_references


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


def _build_crs_prompt(critique_comments_path: str) -> str:
    """Build the change request prompt using the crs xprompt.

    Args:
        critique_comments_path: Path to the critique comments JSON file

    Returns:
        The formatted prompt string
    """
    escaped_path = escape_for_xprompt(critique_comments_path)
    prompt_text = f'#crs(critique_comments_path="{escaped_path}")'
    return process_xprompt_references(prompt_text)


class CrsWorkflow(BaseWorkflow):
    """A workflow for addressing Critique change request comments."""

    def __init__(
        self,
        comments_file: str | None = None,
        timestamp: str | None = None,
        who: str | None = None,
        project_name: str | None = None,
    ) -> None:
        """Initialize CRS workflow.

        Args:
            comments_file: Optional path to existing comments JSON file.
                If provided, copy from this file instead of running critique_comments.
            timestamp: Optional timestamp for artifacts directory (YYmmdd_HHMMSS format).
                When provided, ensures the artifacts directory matches the agent suffix timestamp.
            who: Optional identifier for who is creating the proposal (e.g., "crs (ref)").
            project_name: Optional project name for artifacts directory.
        """
        self.project_name = project_name
        self.comments_file = comments_file
        self._timestamp = timestamp
        self._who = who
        self.response_path: str | None = None
        self.last_prompt: str | None = None
        self.proposal_id: str | None = None

    @property
    def name(self) -> str:
        return "crs"

    @property
    def description(self) -> str:
        return "Address Critique change request comments on a CL"

    def run(self) -> bool:
        """Run the change request workflow."""
        # Initialize workflow context
        if self._timestamp:
            # Use provided timestamp to ensure artifacts match agent suffix
            artifacts_dir = create_artifacts_directory(
                "crs", project_name=self.project_name, timestamp=self._timestamp
            )
            workflow_tag = generate_workflow_tag()
            print_workflow_header("crs", workflow_tag)
            print_status(f"Created artifacts directory: {artifacts_dir}", "success")
            initialize_gai_log(artifacts_dir, "crs", workflow_tag)
        else:
            # Interactive mode - use initialize_workflow for auto-generated timestamp
            ctx = initialize_workflow("crs")
            artifacts_dir = ctx.artifacts_dir
            workflow_tag = ctx.workflow_tag

        # Create critique comments artifact
        print_status("Creating artifacts...", "progress")
        critique_artifact = _create_critique_comments_artifact(
            artifacts_dir, self.comments_file
        )
        print_artifact_created(critique_artifact)

        # Build the prompt
        print_status("Building change request prompt...", "progress")
        prompt = _build_crs_prompt(critique_artifact)
        self.last_prompt = prompt

        # Expand embedded workflows (#propose from crs.md)
        expanded_prompt, post_workflows = expand_embedded_workflows_in_query(
            prompt, artifacts_dir
        )

        # Call Gemini
        print_status("Calling Gemini to address change requests...", "progress")
        response = invoke_agent(
            expanded_prompt,
            agent_type="crs",
            model_tier="big",
            iteration=1,
            workflow_tag=workflow_tag,
            artifacts_dir=artifacts_dir,
            workflow="crs",
            timestamp=self._timestamp,
        )

        # Save the response
        response_content = ensure_str_content(response.content)
        self.response_path = os.path.join(artifacts_dir, "crs_response.txt")
        with open(self.response_path, "w") as f:
            f.write(response_content)
        print_artifact_created(self.response_path)

        # Execute post-steps from embedded workflows (proposal creation via #propose)
        for ewf_result in post_workflows:
            ewf_result.context["_prompt"] = expanded_prompt
            ewf_result.context["_response"] = response_content
            if self._who:
                ewf_result.context["who"] = self._who
            ewf_result.context["_start_timestamp"] = self._timestamp
            try:
                execute_standalone_steps(
                    ewf_result.post_steps,
                    ewf_result.context,
                    "crs-embedded",
                    artifacts_dir,
                )
            except Exception as step_error:
                print(f"Warning: Some embedded workflow steps failed: {step_error}")
                import traceback

                traceback.print_exc()

            # Extract proposal_id from propose step output
            # (runs even if later steps like 'report' failed)
            create_result = ewf_result.context.get("propose", {})
            if isinstance(create_result, dict) and create_result.get("success") in (
                True,
                "true",
            ):
                self.proposal_id = create_result.get("proposal_id")

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
