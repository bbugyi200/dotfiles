"""Workflow for running mentor agents on CLs."""

import os
import subprocess
import sys
from typing import NoReturn

from ace.changespec import find_all_changespecs
from change_actions import execute_change_action, prompt_for_change_action
from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from mentor_config import MentorConfig, get_available_mentor_names, get_mentor_by_name
from rich.console import Console
from rich_utils import print_artifact_created, print_status, print_workflow_header
from running_field import (
    claim_workspace,
    get_first_available_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)
from shared_utils import (
    create_artifacts_directory,
    ensure_str_content,
    finalize_gai_log,
    generate_workflow_tag,
    initialize_gai_log,
    run_bam_command,
)
from workflow_base import BaseWorkflow
from workflow_utils import get_cl_name_from_branch


def _load_mentor_prompt_template() -> str:
    """Load the mentor prompt template.

    Returns:
        The prompt template content.

    Raises:
        FileNotFoundError: If template file doesn't exist.
    """
    template_path = os.path.join(os.path.dirname(__file__), "chats", "mentor_prompt.md")
    with open(template_path, encoding="utf-8") as f:
        return f.read()


def _build_mentor_prompt(mentor: MentorConfig) -> str:
    """Build the mentor prompt by substituting the mentor's prompt into the template.

    Args:
        mentor: The mentor configuration.

    Returns:
        The complete prompt.
    """
    template = _load_mentor_prompt_template()
    return template.replace("{prompt}", mentor.prompt)


def _find_changespec_by_name(cl_name: str) -> tuple[str | None, str | None]:
    """Find a ChangeSpec by name across all project files.

    Args:
        cl_name: The CL name to search for.

    Returns:
        Tuple of (project_file_path, project_name) if found, (None, None) otherwise.
    """
    all_changespecs = find_all_changespecs()
    for cs in all_changespecs:
        if cs.name == cl_name:
            # Extract project name from file path
            # Path format: ~/.gai/projects/<project>/<project>.gp
            project_name = os.path.basename(os.path.dirname(cs.file_path))
            return cs.file_path, project_name
    return None, None


class MentorWorkflow(BaseWorkflow):
    """A workflow for running mentor agents on CLs."""

    def __init__(
        self,
        mentor_name: str,
        cl_name: str | None = None,
    ) -> None:
        """Initialize the mentor workflow.

        Args:
            mentor_name: Name of the mentor to use.
            cl_name: CL name to work on (defaults to current branch name).
        """
        self.mentor_name = mentor_name
        self.cl_name = cl_name
        self.response_path: str | None = None
        self._mentor: MentorConfig | None = None
        self._console = Console()

    @property
    def name(self) -> str:
        """Return the name of this workflow."""
        return "mentor"

    @property
    def description(self) -> str:
        """Return a description of what this workflow does."""
        return f"Run mentor '{self.mentor_name}' on a CL"

    def run(self) -> bool:
        """Run the mentor workflow."""
        # Resolve CL name
        resolved_cl_name = self.cl_name or get_cl_name_from_branch()
        if not resolved_cl_name:
            print_status(
                "Error: Could not determine CL name. Use --cl to specify.", "error"
            )
            return False

        # Load mentor config
        self._mentor = get_mentor_by_name(self.mentor_name)
        if not self._mentor:
            available = get_available_mentor_names()
            if available:
                print_status(
                    f"Error: Mentor '{self.mentor_name}' not found. "
                    f"Available mentors: {', '.join(available)}",
                    "error",
                )
            else:
                print_status(
                    f"Error: Mentor '{self.mentor_name}' not found. "
                    "No mentors configured in ~/.config/gai/gai.yml",
                    "error",
                )
            return False

        # Find the ChangeSpec and its project
        project_file, project = _find_changespec_by_name(resolved_cl_name)
        if not project_file or not project:
            print_status(
                f"Error: ChangeSpec '{resolved_cl_name}' not found in any project file.",
                "error",
            )
            return False

        # Claim workspace
        workspace_num = get_first_available_workspace(project_file)
        try:
            workspace_dir, workspace_suffix = get_workspace_directory_for_num(
                workspace_num, project
            )
        except RuntimeError as e:
            print_status(f"Error: {e}", "error")
            return False

        claim_success = claim_workspace(
            project_file,
            workspace_num,
            f"mentor-{self.mentor_name}",
            resolved_cl_name,
        )
        if not claim_success:
            print_status("Error: Failed to claim workspace.", "error")
            return False

        if workspace_suffix:
            self._console.print(
                f"[cyan]Using workspace share: {workspace_suffix}[/cyan]"
            )

        # Generate workflow tag
        workflow_tag = generate_workflow_tag()
        print_workflow_header(f"mentor-{self.mentor_name}", workflow_tag)

        # Save current directory
        original_dir = os.getcwd()

        try:
            # Change to workspace and update to CL
            os.chdir(workspace_dir)

            # Run bb_hg_update to checkout the CL
            print_status(f"Checking out CL: {resolved_cl_name}", "progress")
            result = subprocess.run(
                ["bb_hg_update", resolved_cl_name],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                print_status(f"Error: bb_hg_update failed: {error_msg}", "error")
                return False

            # Create artifacts directory
            artifacts_dir = create_artifacts_directory(f"mentor-{self.mentor_name}")
            print_status(f"Created artifacts directory: {artifacts_dir}", "success")

            # Initialize the gai.md log
            initialize_gai_log(
                artifacts_dir, f"mentor-{self.mentor_name}", workflow_tag
            )

            # Build and run prompt
            print_status("Building mentor prompt...", "progress")
            prompt = _build_mentor_prompt(self._mentor)

            print_status(f"Running mentor '{self.mentor_name}'...", "progress")
            model = GeminiCommandWrapper(model_size="big")
            model.set_logging_context(
                agent_type=f"mentor-{self.mentor_name}",
                iteration=1,
                workflow_tag=workflow_tag,
                artifacts_dir=artifacts_dir,
                workflow=f"mentor-{self.mentor_name}",
            )

            messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
            response = model.invoke(messages)

            # Save response
            self.response_path = os.path.join(artifacts_dir, "mentor_response.txt")
            with open(self.response_path, "w") as f:
                f.write(ensure_str_content(response.content))
            print_artifact_created(self.response_path)

            print_status("Mentor workflow complete!", "success")
            finalize_gai_log(
                artifacts_dir, f"mentor-{self.mentor_name}", workflow_tag, True
            )
            run_bam_command(f"Mentor ({self.mentor_name}) Complete!")

            # Prompt for change action
            action_result = prompt_for_change_action(
                self._console,
                workspace_dir,
                workflow_name=f"mentor-{self.mentor_name}",
                chat_path=self.response_path,
                project_file=project_file,
            )

            if action_result is None:
                self._console.print(
                    "\n[yellow]Warning: Mentor completed but no changes were made.[/yellow]"
                )
                return True

            action, action_args = action_result

            if action == "reject":
                self._console.print(
                    "[yellow]Changes rejected. Proposal saved.[/yellow]"
                )
                return True

            return execute_change_action(
                action=action,
                action_args=action_args,
                console=self._console,
                target_dir=workspace_dir,
                project_file=project_file,
            )

        except KeyboardInterrupt:
            self._console.print(
                "\n[yellow]Mentor workflow interrupted (Ctrl+C)[/yellow]"
            )
            return False
        except Exception as e:
            self._console.print(f"[red]Mentor workflow crashed: {e!s}[/red]")
            return False
        finally:
            os.chdir(original_dir)
            release_workspace(
                project_file,
                workspace_num,
                f"mentor-{self.mentor_name}",
                resolved_cl_name,
            )


def main() -> NoReturn:
    """Main entry point for the mentor workflow."""
    import argparse

    parser = argparse.ArgumentParser(description="Run mentor workflow")
    parser.add_argument("mentor_name", help="Name of the mentor")
    parser.add_argument(
        "--cl", dest="cl_name", help="CL name (defaults to branch name)"
    )
    args = parser.parse_args()

    workflow = MentorWorkflow(mentor_name=args.mentor_name, cl_name=args.cl_name)
    success = workflow.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
