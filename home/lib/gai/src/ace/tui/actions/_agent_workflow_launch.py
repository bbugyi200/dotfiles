"""Agent launch mixin for the ace TUI app."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .agent_workflow._types import PromptContext

if TYPE_CHECKING:
    from ...changespec import ChangeSpec
    from ..models import Agent


class AgentLaunchMixin:
    """Internal mixin providing agent launching functionality."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    marked_indices: set[int]
    _agents: list[Agent]

    # State for bulk agent runs (from AgentWorkflowMixin)
    _bulk_changespecs: list[ChangeSpec] | None = None
    # State for prompt input (from AgentWorkflowMixin)
    _prompt_context: PromptContext | None = None

    def _finish_agent_launch(self, prompt: str) -> None:
        """Complete agent launch with the given prompt.

        Args:
            prompt: The user's prompt for the agent.
        """
        if self._prompt_context is None:
            self.notify("No prompt context - cannot launch", severity="error")  # type: ignore[attr-defined]
            return

        # Unmount prompt bar first
        self._unmount_prompt_bar()  # type: ignore[attr-defined]

        # Check if this is a bulk run
        if self._bulk_changespecs:
            self._launch_bulk_agents(prompt)
            return

        # Check for workflow reference (e.g., #test_workflow or #split(arg1, arg2))
        if prompt.startswith("#"):
            workflow_result = self._try_execute_workflow(prompt)
            if workflow_result:
                # Workflow executed successfully
                self._prompt_context = None
                self.call_later(self._load_agents)  # type: ignore[attr-defined]
                return

        ctx = self._prompt_context
        self._prompt_context = None

        # Launch single background agent
        self._launch_background_agent(
            cl_name=ctx.display_name,
            project_file=ctx.project_file,
            workspace_dir=ctx.workspace_dir,
            workspace_num=ctx.workspace_num,
            workflow_name=ctx.workflow_name,
            prompt=prompt,
            timestamp=ctx.timestamp,
            update_target=ctx.update_target,
            project_name=ctx.project_name,
            history_sort_key=ctx.history_sort_key,
            is_home_mode=ctx.is_home_mode,
        )

        # Refresh agents list (deferred to avoid lag)
        self.call_later(self._load_agents)  # type: ignore[attr-defined]
        self.notify(f"Agent started for {ctx.display_name}")  # type: ignore[attr-defined]

    def _launch_bulk_agents(self, prompt: str) -> None:
        """Launch agents for all bulk changespecs.

        Args:
            prompt: The user's prompt for all agents.
        """
        from gai_utils import generate_timestamp
        from running_field import (
            get_first_available_axe_workspace,
            get_workspace_directory_for_num,
        )

        if not self._bulk_changespecs:
            self.notify("No bulk changespecs", severity="error")  # type: ignore[attr-defined]
            return

        changespecs = self._bulk_changespecs
        self._bulk_changespecs = None
        self._prompt_context = None

        launched_count = 0
        failed_count = 0

        for cs in changespecs:
            project_name = cs.project_basename
            cl_name = cs.name

            project_file = os.path.expanduser(
                f"~/.gai/projects/{project_name}/{project_name}.gp"
            )

            if not os.path.isfile(project_file):
                self.notify(f"No project file for {cl_name}", severity="warning")  # type: ignore[attr-defined]
                failed_count += 1
                continue

            try:
                workspace_num = get_first_available_axe_workspace(project_file)
                timestamp = generate_timestamp()
                workflow_name = f"ace(run)-{timestamp}"
                workspace_dir, _ = get_workspace_directory_for_num(
                    workspace_num, project_name
                )
            except RuntimeError as e:
                self.notify(f"Workspace error for {cl_name}: {e}", severity="warning")  # type: ignore[attr-defined]
                failed_count += 1
                continue

            self._launch_background_agent(
                cl_name=cl_name,
                project_file=project_file,
                workspace_dir=workspace_dir,
                workspace_num=workspace_num,
                workflow_name=workflow_name,
                prompt=prompt,
                timestamp=timestamp,
                update_target=cl_name,
                project_name=project_name,
                history_sort_key=cl_name,
            )
            launched_count += 1

        # Clear marks after bulk launch
        self.marked_indices = set()  # type: ignore[assignment]
        self._refresh_display()  # type: ignore[attr-defined]

        # Refresh agents list
        self.call_later(self._load_agents)  # type: ignore[attr-defined]

        # Show summary notification
        if failed_count > 0:
            self.notify(  # type: ignore[attr-defined]
                f"Started {launched_count} agent(s), {failed_count} failed",
                severity="warning",
            )
        else:
            self.notify(f"Started {launched_count} agent(s)")  # type: ignore[attr-defined]

    def _launch_background_agent(
        self,
        cl_name: str,
        project_file: str,
        workspace_dir: str,
        workspace_num: int,
        workflow_name: str,
        prompt: str,
        timestamp: str,
        update_target: str = "",
        project_name: str = "",
        history_sort_key: str = "",
        is_home_mode: bool = False,
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
            update_target: What to checkout (CL name or "p4head").
            project_name: Project name for prompt history tracking.
            history_sort_key: CL name to associate with the prompt in history.
            is_home_mode: If True, skip workspace management (for home directory).
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
            "axe_run_agent_runner.py",
        )

        # Start background process first to get actual PID
        # Args: cl_name, project_file, workspace_dir, output_path, workspace_num,
        #       workflow_name, prompt_file, timestamp,
        #       update_target, project_name, history_sort_key, is_home_mode
        try:
            with open(output_path, "w") as output_file:
                process = subprocess.Popen(
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
                        update_target,
                        project_name,
                        history_sort_key,
                        "1" if is_home_mode else "",
                    ],
                    cwd=workspace_dir,
                    stdout=output_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,  # Detach from TUI process
                    env=os.environ,
                )
        except Exception as e:
            self.notify(f"Failed to start agent: {e}", severity="error")  # type: ignore[attr-defined]
            return

        # Claim workspace with actual subprocess PID (skip for home mode)
        if is_home_mode:
            # Create home project directory and file if needed (for artifact path resolution)
            home_project_dir = os.path.expanduser("~/.gai/projects/home")
            home_project_file = os.path.join(home_project_dir, "home.gp")
            os.makedirs(home_project_dir, exist_ok=True)
            if not os.path.exists(home_project_file):
                with open(home_project_file, "w", encoding="utf-8") as f:
                    f.write("")  # Empty file - just needs to exist
        else:
            from running_field import claim_workspace

            if not claim_workspace(
                project_file,
                workspace_num,
                workflow_name,
                process.pid,
                cl_name,
                artifacts_timestamp=timestamp,
            ):
                self.notify(  # type: ignore[attr-defined]
                    "Failed to claim workspace, terminating agent", severity="error"
                )
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                return

    def _try_execute_workflow(self, prompt: str) -> bool:
        """Try to execute a workflow reference.

        Args:
            prompt: The prompt starting with # (e.g., "#test_workflow" or "#split(arg)").

        Returns:
            True if workflow was executed, False if not a valid workflow reference.
        """
        from xprompt import get_all_workflows, parse_workflow_reference

        workflow_ref = prompt[1:]  # Strip the #
        workflow_name, positional_args, named_args = parse_workflow_reference(
            workflow_ref
        )

        workflows = get_all_workflows()
        if workflow_name not in workflows:
            return False

        # Check if we have changespec context (not home mode)
        ctx = self._prompt_context
        has_changespec_context = (
            ctx is not None and not ctx.is_home_mode and ctx.project_file
        )

        if has_changespec_context:
            # Launch as subprocess with workspace claiming
            return self._launch_workflow_subprocess(
                workflow_name, positional_args, named_args
            )

        # Original behavior: daemon thread for home mode or no context
        return self._execute_workflow_in_thread(
            workflow_name, positional_args, named_args
        )

    def _execute_workflow_in_thread(
        self,
        workflow_name: str,
        positional_args: list[str],
        named_args: dict[str, str],
    ) -> bool:
        """Execute workflow in a daemon thread (for home mode).

        Args:
            workflow_name: Name of the workflow to execute.
            positional_args: Positional arguments for the workflow.
            named_args: Named arguments for the workflow.

        Returns:
            True if workflow was started, False on error.
        """
        from datetime import datetime
        from pathlib import Path

        from xprompt import execute_workflow

        # Create proper artifacts directory for workflow state persistence
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        artifacts_dir = (
            Path.home()
            / ".gai"
            / "projects"
            / "home"
            / "artifacts"
            / f"workflow-{workflow_name}"
            / timestamp
        )
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Execute workflow in background thread to not block TUI
            import threading

            def run_workflow() -> None:
                try:
                    execute_workflow(
                        workflow_name,
                        positional_args,
                        named_args,
                        artifacts_dir=str(artifacts_dir),
                        silent=True,
                    )
                except Exception as e:
                    # Can't easily notify from background thread, so just log
                    import logging

                    logging.error(f"Workflow '{workflow_name}' failed: {e}")

            thread = threading.Thread(target=run_workflow, daemon=True)
            thread.start()
            self.notify(f"Workflow '{workflow_name}' started")  # type: ignore[attr-defined]
            return True
        except Exception as e:
            self.notify(f"Workflow error: {e}", severity="error")  # type: ignore[attr-defined]
            return False

    def _launch_workflow_subprocess(
        self,
        workflow_name: str,
        positional_args: list[str],
        named_args: dict[str, str],
    ) -> bool:
        """Launch workflow as subprocess with workspace claiming.

        Args:
            workflow_name: Name of the workflow to execute.
            positional_args: Positional arguments for the workflow.
            named_args: Named arguments for the workflow.

        Returns:
            True if workflow was started, False on error.
        """
        import json
        import subprocess
        from datetime import datetime

        from running_field import claim_workspace

        ctx = self._prompt_context
        if ctx is None:
            self.notify("No prompt context", severity="error")  # type: ignore[attr-defined]
            return False

        # Build artifacts directory using project context
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        project_name = os.path.basename(os.path.dirname(ctx.project_file))
        artifacts_dir = os.path.expanduser(
            f"~/.gai/projects/{project_name}/artifacts/workflow-{workflow_name}/{timestamp}"
        )
        os.makedirs(artifacts_dir, exist_ok=True)

        # Build runner script path
        # From src/ace/tui/actions/ we need 4 dirname calls to get to src/
        runner_script = os.path.join(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            ),
            "axe_run_workflow_runner.py",
        )

        # Build output log path
        output_path = os.path.join(artifacts_dir, "workflow.log")

        # Launch subprocess with output redirection
        try:
            with open(output_path, "w") as output_file:
                process = subprocess.Popen(
                    [
                        "python3",
                        runner_script,
                        workflow_name,
                        json.dumps(positional_args),
                        json.dumps(named_args),
                        ctx.project_file,
                        ctx.workspace_dir,
                        str(ctx.workspace_num),
                        artifacts_dir,
                        ctx.update_target or "",
                        "",  # not home mode
                    ],
                    cwd=ctx.workspace_dir,
                    stdout=output_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,  # Detach from TUI process
                    env=os.environ,
                )
        except Exception as e:
            self.notify(f"Failed to start workflow: {e}", severity="error")  # type: ignore[attr-defined]
            return False

        # Claim workspace with subprocess PID
        workflow_field_name = f"workflow({workflow_name})"
        if not claim_workspace(
            ctx.project_file,
            ctx.workspace_num,
            workflow_field_name,
            process.pid,
            ctx.display_name,
            artifacts_timestamp=timestamp,
        ):
            self.notify("Failed to claim workspace", severity="error")  # type: ignore[attr-defined]
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            return False

        self.notify(f"Workflow '{workflow_name}' started")  # type: ignore[attr-defined]
        return True
