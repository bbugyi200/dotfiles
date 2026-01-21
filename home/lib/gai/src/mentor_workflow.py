"""Workflow for running mentor agents on CLs."""

import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from ace.changespec import find_all_changespecs
from ace.scheduler.mentor_runner import get_mentor_chat_path
from change_actions import execute_change_action, prompt_for_change_action
from commit_utils import run_bb_hg_clean
from gai_utils import generate_timestamp
from gemini_wrapper import invoke_agent
from mentor_config import (
    MentorConfig,
    get_mentor_from_profile,
    get_mentor_profile_by_name,
)
from rich.console import Console
from rich_utils import print_artifact_created, print_status, print_workflow_header
from running_field import (
    claim_workspace,
    get_first_available_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)
from shared_utils import (
    ensure_str_content,
    finalize_gai_log,
    generate_workflow_tag,
    initialize_gai_log,
    run_bam_command,
)
from summarize_utils import get_file_summary
from workflow_base import BaseWorkflow
from workflow_utils import get_cl_name_from_branch


def _load_mentor_prompt_template() -> str:
    """Load the mentor prompt template.

    Returns:
        The prompt template content.

    Raises:
        FileNotFoundError: If template file doesn't exist.
    """
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "chats",
        "mentor_prompt.md",
    )
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
    return template.replace("{prompt}", mentor.prompt.rstrip())


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
        profile_name: str,
        mentor_name: str,
        cl_name: str | None = None,
        workspace_num: int | None = None,
        workflow_name: str | None = None,
        workspace_dir: str | None = None,
        timestamp: str | None = None,
    ) -> None:
        """Initialize the mentor workflow.

        Args:
            profile_name: Name of the profile containing the mentor.
            mentor_name: Name of the mentor to use.
            cl_name: CL name to work on (defaults to current branch name).
            workspace_num: Pre-claimed workspace number (for axe context).
            workflow_name: Pre-claimed workflow name (for axe context).
            workspace_dir: Pre-configured workspace directory (for axe context).
            timestamp: Timestamp for chat file naming (YYmmdd_HHMMSS format).
        """
        self.profile_name = profile_name
        self.mentor_name = mentor_name
        self.cl_name = cl_name
        self._workspace_num = workspace_num
        self._workflow_name = workflow_name
        self._workspace_dir = workspace_dir
        self._timestamp = timestamp
        self._owns_workspace = False  # True if we claimed the workspace ourselves
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

        # Load profile and mentor config
        profile = get_mentor_profile_by_name(self.profile_name)
        if not profile:
            print_status(
                f"Error: Profile '{self.profile_name}' not found in "
                "~/.config/gai/gai.yml",
                "error",
            )
            return False

        self._mentor = get_mentor_from_profile(profile, self.mentor_name)
        if not self._mentor:
            available = [m.mentor_name for m in profile.mentors]
            print_status(
                f"Error: Mentor '{self.mentor_name}' not found in profile "
                f"'{self.profile_name}'. Available mentors: {', '.join(available)}",
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

        # Handle workspace: use pre-claimed if provided, otherwise claim new
        if self._workspace_num is not None and self._workspace_dir is not None:
            # Running in loop context - workspace already claimed
            workspace_num = self._workspace_num
            workspace_dir = self._workspace_dir
            workflow_name = self._workflow_name or f"mentor-{self.mentor_name}"
            self._owns_workspace = False
        else:
            # Interactive context - claim workspace ourselves
            workspace_num = get_first_available_workspace(project_file)
            try:
                workspace_dir, workspace_suffix = get_workspace_directory_for_num(
                    workspace_num, project
                )
            except RuntimeError as e:
                print_status(f"Error: {e}", "error")
                return False

            workflow_name = f"mentor-{self.mentor_name}"
            claim_success = claim_workspace(
                project_file,
                workspace_num,
                workflow_name,
                os.getpid(),
                resolved_cl_name,
            )
            if not claim_success:
                print_status("Error: Failed to claim workspace.", "error")
                return False

            self._owns_workspace = True

            if workspace_suffix:
                self._console.print(
                    f"[cyan]Using workspace share: {workspace_suffix}[/cyan]"
                )

        # Store for use in finally block
        self._workspace_num = workspace_num
        self._workflow_name = workflow_name
        self._project_file = project_file
        self._resolved_cl_name = resolved_cl_name

        # Generate workflow tag
        workflow_tag = generate_workflow_tag()
        print_workflow_header(f"mentor-{self.mentor_name}", workflow_tag)

        # Save current directory
        original_dir = os.getcwd()

        try:
            # Change to workspace and update to CL
            os.chdir(workspace_dir)

            # Run bb_hg_update to checkout the CL (skip if workspace already set up)
            if self._owns_workspace:
                # Clean workspace before switching branches
                clean_success, clean_error = run_bb_hg_clean(
                    workspace_dir, f"{resolved_cl_name}-mentor-{self.mentor_name}"
                )
                if not clean_success:
                    print_status(
                        f"Warning: bb_hg_clean failed: {clean_error}", "warning"
                    )

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

            # Generate timestamp if not provided (interactive mode)
            if self._timestamp is None:
                self._timestamp = generate_timestamp()

            # Create artifacts directory using the same timestamp as the agent suffix
            # This ensures the Agents tab can find the prompt file
            # Convert timestamp: YYmmdd_HHMMSS -> YYYYmmddHHMMSS
            artifacts_timestamp = f"20{self._timestamp[:6]}{self._timestamp[7:]}"
            project_name = Path(project_file).parent.name
            artifacts_dir = os.path.expanduser(
                f"~/.gai/projects/{project_name}/artifacts/"
                f"mentor-{self.mentor_name}/{artifacts_timestamp}"
            )
            Path(artifacts_dir).mkdir(parents=True, exist_ok=True)
            print_status(f"Created artifacts directory: {artifacts_dir}", "success")

            # Initialize the gai.md log
            initialize_gai_log(
                artifacts_dir, f"mentor-{self.mentor_name}", workflow_tag
            )

            # Build and run prompt
            print_status("Building mentor prompt...", "progress")
            prompt = _build_mentor_prompt(self._mentor)

            print_status(f"Running mentor '{self.mentor_name}'...", "progress")
            response = invoke_agent(
                prompt,
                agent_type=f"mentor-{self.mentor_name}",
                model_size="big",
                iteration=1,
                workflow_tag=workflow_tag,
                artifacts_dir=artifacts_dir,
                workflow=f"mentor-{self.mentor_name}",
                timestamp=self._timestamp,
            )

            # Check for empty response (indicates silent failure like permission issues)
            response_text = response.content
            if isinstance(response_text, str):
                response_text = response_text.strip()
            if not response_text:
                print_status(
                    f"Error: Mentor '{self.mentor_name}' returned empty response. "
                    "This may indicate a permission issue with ~/.gai/chats/",
                    "error",
                )
                return False

            # Get the chat file path for the proposal
            chat_file_path = get_mentor_chat_path(
                resolved_cl_name, self.mentor_name, self._timestamp
            )
            chat_path = chat_file_path.replace(str(Path.home()), "~")

            # Save response
            self.response_path = os.path.join(artifacts_dir, "mentor_response.txt")
            with open(self.response_path, "w") as f:
                f.write(ensure_str_content(response.content))
            print_artifact_created(self.response_path)

            # Get summary of mentor response for better proposal message
            print_status("Summarizing changes...", "progress")
            summary = get_file_summary(
                target_file=self.response_path,
                usage="a HISTORY entry header describing what changes were made by the mentor",
                fallback="",
            )

            print_status("Mentor workflow complete!", "success")
            finalize_gai_log(
                artifacts_dir, f"mentor-{self.mentor_name}", workflow_tag, True
            )
            run_bam_command(f"Mentor ({self.mentor_name}) Complete!")

            # Prompt for change action
            # In loop context (_owns_workspace=False), auto-reject to avoid blocking
            # on stdin which is unavailable in background processes
            action_result = prompt_for_change_action(
                self._console,
                workspace_dir,
                workflow_name=f"mentor:{self.mentor_name}",
                workflow_summary=summary,
                chat_path=chat_path,
                project_file=project_file,
                auto_reject=not self._owns_workspace,
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
            # Only release workspace if we claimed it ourselves
            if self._owns_workspace:
                release_workspace(
                    self._project_file,
                    self._workspace_num,
                    self._workflow_name,
                    self._resolved_cl_name,
                )


def main() -> NoReturn:
    """Main entry point for the mentor workflow."""
    import argparse

    parser = argparse.ArgumentParser(description="Run mentor workflow")
    parser.add_argument(
        "mentor_spec",
        help="Profile and mentor name in format 'profile:mentor' (e.g., 'code:comments')",
    )
    parser.add_argument(
        "--cl", dest="cl_name", help="CL name (defaults to branch name)"
    )
    args = parser.parse_args()

    # Parse profile:mentor format
    if ":" not in args.mentor_spec:
        print(
            f"Error: mentor_spec must be in format 'profile:mentor', "
            f"got '{args.mentor_spec}'",
            file=sys.stderr,
        )
        sys.exit(1)
    profile_name, mentor_name = args.mentor_spec.split(":", 1)

    workflow = MentorWorkflow(
        profile_name=profile_name,
        mentor_name=mentor_name,
        cl_name=args.cl_name,
    )
    success = workflow.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
