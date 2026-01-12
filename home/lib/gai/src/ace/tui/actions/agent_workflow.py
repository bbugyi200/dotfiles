"""Custom agent workflow mixin for the ace TUI app."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ...changespec import ChangeSpec
    from ..models import Agent

# Type alias for tab names
TabName = Literal["changespecs", "agents"]


class AgentWorkflowMixin:
    """Mixin providing custom agent workflow actions."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    current_idx: int
    current_tab: TabName
    _agents: list[Agent]

    def action_start_custom_agent(self) -> None:
        """Start a custom agent by selecting project or CL."""
        if self.current_tab != "agents":
            self.notify("Switch to Agents tab first", severity="warning")  # type: ignore[attr-defined]
            return

        from ...changespec import find_all_changespecs
        from ..modals import (
            CLNameAction,
            CLNameInputModal,
            CLNameResult,
            ProjectSelectModal,
            SelectionItem,
        )

        def on_project_select(result: SelectionItem | str | None) -> None:
            if result is None:
                self.notify("Selection cancelled")  # type: ignore[attr-defined]
                return

            self.notify(f"Selected: {result}")  # type: ignore[attr-defined]

            # Determine selection type and details
            if isinstance(result, str):
                # Custom CL name entered - derive project from CL
                selection_type = "cl"
                selected_cl_name = result
                project_name: str | None = None
                # Find project for this CL
                for cs in find_all_changespecs():
                    if cs.name == selected_cl_name:
                        project_name = cs.project_basename
                        break
                if project_name is None:
                    self.notify(  # type: ignore[attr-defined]
                        f"Could not find CL '{selected_cl_name}' in any project",
                        severity="error",
                    )
                    return
            elif result.item_type == "project":
                selection_type = "project"
                selected_cl_name = None
                project_name = result.project_name
            else:
                selection_type = "cl"
                selected_cl_name = result.cl_name
                project_name = result.project_name

            def on_cl_name_input(result: CLNameResult | None) -> None:
                self.notify(f"CL name input: {result!r}")  # type: ignore[attr-defined]

                # Handle cancel
                if result is None or result.action == CLNameAction.CANCEL:
                    self.notify("CL name cancelled")  # type: ignore[attr-defined]
                    return

                new_cl_name = result.cl_name
                use_history = result.action == CLNameAction.USE_HISTORY

                # Determine sort key for prompt history
                history_sort_key = new_cl_name or selected_cl_name or project_name

                # For projects, CL name is required (modal validates this)
                if selection_type == "project":
                    if new_cl_name is None:
                        self.notify("CL name cancelled for project")  # type: ignore[attr-defined]
                        return
                    self._start_agent_for_project(
                        project_name,
                        new_cl_name,
                        use_history=use_history,
                        history_sort_key=history_sort_key,
                    )
                else:
                    if new_cl_name is None and selected_cl_name is None:
                        self.notify("No CL name and no selected CL")  # type: ignore[attr-defined]
                        return
                    self._start_agent_for_cl(
                        selected_cl_name,
                        project_name,
                        new_cl_name,
                        use_history=use_history,
                        history_sort_key=history_sort_key,
                    )

            # Show CL name input modal
            self.push_screen(  # type: ignore[attr-defined]
                CLNameInputModal(
                    selection_type=selection_type,  # type: ignore[arg-type]
                    selected_cl_name=selected_cl_name,
                ),
                on_cl_name_input,
            )

        self.push_screen(ProjectSelectModal(), on_project_select)  # type: ignore[attr-defined]

    def _start_agent_for_project(
        self,
        project_name: str | None,
        new_cl_name: str,
        use_history: bool = False,
        history_sort_key: str | None = None,
    ) -> None:
        """Start agent for a project (update to p4head).

        Args:
            project_name: The project name.
            new_cl_name: Name for the new ChangeSpec to create if agent makes changes.
            use_history: If True, show prompt history picker instead of blank editor.
            history_sort_key: Branch/CL name to sort prompt history by.
        """
        if project_name is None:
            self.notify("No project selected", severity="error")  # type: ignore[attr-defined]
            return
        self._start_agent_common(
            project_name=project_name,
            cl_name=None,
            update_target="p4head",
            new_cl_name=new_cl_name,
            use_history=use_history,
            history_sort_key=history_sort_key,
        )

    def _start_agent_for_cl(
        self,
        cl_name: str | None,
        project_name: str | None,
        new_cl_name: str | None,
        use_history: bool = False,
        history_sort_key: str | None = None,
    ) -> None:
        """Start agent for a CL.

        Args:
            cl_name: The selected CL name to work on.
            project_name: The project name.
            new_cl_name: If provided, create a new ChangeSpec with this name.
                If None, create a proposal for the existing CL.
            use_history: If True, show prompt history picker instead of blank editor.
            history_sort_key: Branch/CL name to sort prompt history by.
        """
        from ...changespec import find_all_changespecs

        if cl_name is None:
            self.notify("No CL selected", severity="error")  # type: ignore[attr-defined]
            return

        # Derive project from CL name if not provided
        if project_name is None:
            for cs in find_all_changespecs():
                if cs.name == cl_name:
                    project_name = cs.project_basename
                    break

        if project_name is None:
            self.notify(f"Could not determine project for {cl_name}", severity="error")  # type: ignore[attr-defined]
            return

        self._start_agent_common(
            project_name=project_name,
            cl_name=cl_name,
            update_target=cl_name,  # Checkout CL
            new_cl_name=new_cl_name,
            use_history=use_history,
            history_sort_key=history_sort_key,
        )

    def _start_agent_common(
        self,
        project_name: str,
        cl_name: str | None,
        update_target: str,
        new_cl_name: str | None = None,
        use_history: bool = False,
        history_sort_key: str | None = None,
    ) -> None:
        """Common logic for starting agent after selection.

        Args:
            project_name: The project name.
            cl_name: The selected CL name (or None for project-only).
            update_target: What to checkout (CL name or "p4head").
            new_cl_name: If provided, create a new ChangeSpec with this name
                when the agent makes changes. If None and cl_name is set,
                create a proposal for the existing CL.
            use_history: If True, show prompt history picker instead of blank editor.
            history_sort_key: Branch/CL name to sort prompt history by.
        """
        import subprocess

        from commit_utils import run_bb_hg_clean
        from commit_workflow.project_file_utils import create_project_file
        from gai_utils import generate_timestamp
        from running_field import (
            claim_workspace,
            get_first_available_loop_workspace,
            get_workspace_directory_for_num,
            release_workspace,
        )

        project_file = os.path.expanduser(
            f"~/.gai/projects/{project_name}/{project_name}.gp"
        )

        # Create project file if it doesn't exist
        if not os.path.isfile(project_file):
            if not create_project_file(project_name):
                self.notify(  # type: ignore[attr-defined]
                    f"Failed to create project file: {project_file}",
                    severity="error",
                )
                return

        # Claim a workspace >= 100
        workspace_num = get_first_available_loop_workspace(project_file)
        timestamp = generate_timestamp()
        workflow_name = f"ace(run)-{timestamp}"
        display_name = cl_name or project_name

        if not claim_workspace(
            project_file,
            workspace_num,
            workflow_name,
            display_name,
            pid=os.getpid(),
            artifacts_timestamp=timestamp,
        ):
            self.notify("Failed to claim workspace", severity="error")  # type: ignore[attr-defined]
            return

        try:
            workspace_dir, _ = get_workspace_directory_for_num(
                workspace_num, project_name
            )

            # Clean workspace
            self.notify(f"Cleaning workspace {workspace_num}...")  # type: ignore[attr-defined]
            run_bb_hg_clean(workspace_dir, f"{display_name}-ace")

            # Update workspace
            self.notify(f"Updating to {update_target}...")  # type: ignore[attr-defined]
            result = subprocess.run(
                ["bb_hg_update", update_target],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                self.notify(f"bb_hg_update failed: {error_msg}", severity="error")  # type: ignore[attr-defined]
                release_workspace(
                    project_file, workspace_num, workflow_name, display_name
                )
                return

            # Open editor or history picker for prompt (TUI suspended)
            if use_history:
                prompt = self._open_prompt_history_picker(
                    history_sort_key or project_name
                )
            else:
                prompt = self._open_editor_for_agent_prompt()

            if prompt is None:
                self.notify("No prompt provided - cancelled", severity="warning")  # type: ignore[attr-defined]
                release_workspace(
                    project_file, workspace_num, workflow_name, display_name
                )
                return

            # Launch background agent
            self._launch_background_agent(
                cl_name=display_name,
                project_file=project_file,
                workspace_dir=workspace_dir,
                workspace_num=workspace_num,
                workflow_name=workflow_name,
                prompt=prompt,
                timestamp=timestamp,
                new_cl_name=new_cl_name,
                parent_cl_name=cl_name,  # Used as parent for new ChangeSpec
            )

            # Refresh agents list
            self._load_agents()  # type: ignore[attr-defined]
            self.notify(f"Agent started for {display_name}")  # type: ignore[attr-defined]

        except subprocess.TimeoutExpired:
            self.notify("bb_hg_update timed out", severity="error")  # type: ignore[attr-defined]
            release_workspace(project_file, workspace_num, workflow_name, display_name)
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")  # type: ignore[attr-defined]
            release_workspace(project_file, workspace_num, workflow_name, display_name)

    def _open_editor_for_agent_prompt(self) -> str | None:
        """Suspend TUI and open editor for prompt input.

        Returns:
            The prompt content, or None if empty/cancelled.
        """
        import subprocess
        import tempfile

        def run_editor() -> str | None:
            fd, temp_path = tempfile.mkstemp(suffix=".md", prefix="gai_ace_prompt_")
            os.close(fd)

            editor = os.environ.get("EDITOR", "nvim")

            result = subprocess.run([editor, temp_path], check=False)
            if result.returncode != 0:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                return None

            try:
                with open(temp_path, encoding="utf-8") as f:
                    content = f.read().strip()
            finally:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

            return content if content else None

        with self.suspend():  # type: ignore[attr-defined]
            return run_editor()

    def _open_prompt_history_picker(self, sort_by: str) -> str | None:
        """Suspend TUI and open fzf prompt history picker.

        Args:
            sort_by: Branch/CL name to sort prompts by.

        Returns:
            The selected and edited prompt content, or None if cancelled.
        """
        from main.query_handler._editor import show_prompt_history_picker_for_branch

        with self.suspend():  # type: ignore[attr-defined]
            return show_prompt_history_picker_for_branch(sort_by)

    def _launch_background_agent(
        self,
        cl_name: str,
        project_file: str,
        workspace_dir: str,
        workspace_num: int,
        workflow_name: str,
        prompt: str,
        timestamp: str,
        new_cl_name: str | None = None,
        parent_cl_name: str | None = None,
    ) -> None:
        """Launch agent as background process.

        Args:
            cl_name: Display name for the CL/project.
            project_file: Path to the project file.
            workspace_dir: Path to the workspace directory.
            workspace_num: The workspace number.
            workflow_name: Name for the workflow.
            prompt: The user's prompt for the agent.
            timestamp: Shared timestamp for artifacts.
            new_cl_name: If provided, create a new ChangeSpec with this name.
            parent_cl_name: The parent CL name for the new ChangeSpec (if any).
        """
        import subprocess
        import tempfile

        from gai_utils import ensure_gai_directory

        # Write prompt to temp file (runner will read and delete)
        fd, prompt_file = tempfile.mkstemp(suffix=".md", prefix="gai_ace_prompt_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(prompt)

        # Get output file path
        workflows_dir = ensure_gai_directory("workflows")
        # Sanitize cl_name for filename
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in cl_name)
        output_path = os.path.join(
            workflows_dir, f"{safe_name}_ace-run-{timestamp}.txt"
        )

        # Build runner script path
        # From src/ace/tui/actions/ we need 4 dirname calls to get to src/
        runner_script = os.path.join(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            ),
            "loop_run_agent_runner.py",
        )

        # Start background process
        # Pass new_cl_name and parent_cl_name as 9th and 10th args (empty string if None)
        with open(output_path, "w") as output_file:
            subprocess.Popen(
                [
                    "python3",
                    runner_script,
                    cl_name,
                    project_file,
                    workspace_dir,
                    output_path,
                    str(workspace_num),
                    workflow_name,
                    prompt_file,
                    timestamp,
                    new_cl_name or "",
                    parent_cl_name or "",
                ],
                cwd=workspace_dir,
                stdout=output_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # Detach from TUI process
                env=os.environ,
            )
