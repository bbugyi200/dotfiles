"""Prompt input bar management and event handlers for agent workflow."""

from __future__ import annotations

import os

from ._types import PromptContext


class PromptBarMixin:
    """Mixin providing prompt input bar management and event handlers."""

    # State for prompt input
    _prompt_context: PromptContext | None = None

    def _show_prompt_input_bar(
        self,
        project_name: str | None,
        cl_name: str | None,
        update_target: str,
        new_cl_name: str | None,
        history_sort_key: str,
        bug: str | None = None,
        fixed_bug: str | None = None,
    ) -> None:
        """Show prompt input bar for agent workflow.

        Args:
            project_name: The project name.
            cl_name: The selected CL name (or None for project-only).
            update_target: What to checkout (CL name or "p4head").
            new_cl_name: If provided, create a new ChangeSpec with this name.
            history_sort_key: Branch/CL name to sort prompt history by.
            bug: Bug number to associate with a new ChangeSpec (BUG: field).
            fixed_bug: Bug number for FIXED: field (mutually exclusive with bug).
        """
        from commit_workflow.project_file_utils import create_project_file
        from gai_utils import generate_timestamp
        from running_field import (
            get_first_available_axe_workspace,
            get_workspace_directory_for_num,
        )

        from ...widgets import PromptInputBar

        if project_name is None:
            self.notify("No project selected", severity="error")  # type: ignore[attr-defined]
            return

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

        # Get workspace info (don't claim yet - need subprocess PID first)
        workspace_num = get_first_available_axe_workspace(project_file)
        timestamp = generate_timestamp()
        workflow_name = f"ace(run)-{timestamp}"
        display_name = cl_name or project_name

        try:
            workspace_dir, _ = get_workspace_directory_for_num(
                workspace_num, project_name
            )
        except RuntimeError as e:
            self.notify(f"Failed to get workspace: {e}", severity="error")  # type: ignore[attr-defined]
            return

        # Store context for when prompt is submitted
        self._prompt_context = PromptContext(
            project_name=project_name,
            cl_name=cl_name,
            new_cl_name=new_cl_name,
            parent_cl_name=cl_name,
            project_file=project_file,
            workspace_dir=workspace_dir,
            workspace_num=workspace_num,
            workflow_name=workflow_name,
            timestamp=timestamp,
            history_sort_key=history_sort_key,
            display_name=display_name,
            update_target=update_target,
            bug=bug,
            fixed_bug=fixed_bug,
        )

        # Immediately show prompt input bar (workspace prep happens in runner)
        self.mount(PromptInputBar(id="prompt-input-bar"))  # type: ignore[attr-defined]

    def _unmount_prompt_bar(self) -> None:
        """Unmount the prompt input bar if present."""
        from ...widgets import PromptInputBar

        try:
            bar = self.query_one("#prompt-input-bar", PromptInputBar)  # type: ignore[attr-defined]
            bar.remove()
        except Exception:
            pass  # Bar not present

    def _show_prompt_input_bar_for_home(self) -> None:
        """Show prompt input bar for home directory mode.

        This skips CL name and bug modals, running the agent from the user's
        home directory without version control or workspace management.
        """
        from pathlib import Path

        from gai_utils import generate_timestamp

        from ...widgets import PromptInputBar

        timestamp = generate_timestamp()
        workflow_name = f"ace(run)-{timestamp}"

        # Store context for when prompt is submitted
        # project_file is needed for artifact path resolution in agent_loader
        self._prompt_context = PromptContext(
            project_name="home",
            cl_name=None,
            new_cl_name=None,
            parent_cl_name=None,
            project_file=os.path.expanduser("~/.gai/projects/home/home.gp"),
            workspace_dir=str(Path.home()),
            workspace_num=0,
            workflow_name=workflow_name,
            timestamp=timestamp,
            history_sort_key="home",
            display_name="~",
            update_target="",
            is_home_mode=True,
        )

        # Show prompt input bar
        self.mount(PromptInputBar(id="prompt-input-bar"))  # type: ignore[attr-defined]

    def on_prompt_input_bar_submitted(self, event: object) -> None:
        """Handle prompt submission from the input bar."""
        from ...widgets import PromptInputBar

        if not isinstance(event, PromptInputBar.Submitted):
            return

        prompt = event.value
        if not prompt:
            self.notify("Empty prompt - cancelled", severity="warning")  # type: ignore[attr-defined]
            self._unmount_prompt_bar()
            self._prompt_context = None
            return

        self._finish_agent_launch(prompt)  # type: ignore[attr-defined]

    def on_prompt_input_bar_cancelled(self, event: object) -> None:
        """Handle cancellation from the input bar."""
        from ...widgets import PromptInputBar

        if not isinstance(event, PromptInputBar.Cancelled):
            return

        self.notify("Prompt input cancelled")  # type: ignore[attr-defined]
        self._unmount_prompt_bar()
        self._prompt_context = None

    def on_prompt_input_bar_editor_requested(self, event: object) -> None:
        """Handle request to open external editor (Ctrl+G)."""
        from ...widgets import PromptInputBar

        if not isinstance(event, PromptInputBar.EditorRequested):
            return

        if self._prompt_context is None:
            return

        # Suspend TUI and open editor with current text
        prompt = self._open_editor_for_agent_prompt(event.current_text)  # type: ignore[attr-defined]
        if prompt:
            self._finish_agent_launch(prompt)  # type: ignore[attr-defined]
        else:
            self.notify("No prompt from editor - cancelled", severity="warning")  # type: ignore[attr-defined]
            self._unmount_prompt_bar()
            self._prompt_context = None

    def on_prompt_input_bar_history_requested(self, event: object) -> None:
        """Handle request to show prompt history picker ('.')."""
        from ...widgets import PromptInputBar

        if not isinstance(event, PromptInputBar.HistoryRequested):
            return

        if self._prompt_context is None:
            return

        from ...modals import (
            PromptHistoryAction,
            PromptHistoryModal,
            PromptHistoryResult,
        )

        def on_history_select(result: PromptHistoryResult | None) -> None:
            if result is None:
                self.notify("No prompt from history - cancelled", severity="warning")  # type: ignore[attr-defined]
                self._unmount_prompt_bar()
                self._prompt_context = None
                return

            if result.action == PromptHistoryAction.SUBMIT:
                # Direct submit - skip editor
                self._finish_agent_launch(result.prompt_text)  # type: ignore[attr-defined]
            else:
                # Edit first - open editor with selected prompt
                edited_prompt = self._open_editor_for_agent_prompt(result.prompt_text)  # type: ignore[attr-defined]
                if edited_prompt:
                    self._finish_agent_launch(edited_prompt)  # type: ignore[attr-defined]
                else:
                    self.notify("No prompt from editor - cancelled", severity="warning")  # type: ignore[attr-defined]
                    self._unmount_prompt_bar()
                    self._prompt_context = None

        self.push_screen(  # type: ignore[attr-defined]
            PromptHistoryModal(
                sort_by=self._prompt_context.history_sort_key,
                workspace=self._prompt_context.project_name,
            ),
            on_history_select,
        )

    def on_prompt_input_bar_snippet_requested(self, event: object) -> None:
        """Handle request to show snippet modal ('#')."""
        from ...widgets import PromptInputBar

        if not isinstance(event, PromptInputBar.SnippetRequested):
            return

        from ...modals import XPromptSelectModal

        def on_xprompt_select(result: str | None) -> None:
            if result:
                # Insert xprompt name into the input bar
                try:
                    bar = self.query_one("#prompt-input-bar", PromptInputBar)  # type: ignore[attr-defined]
                    bar.insert_snippet(result)
                except Exception:
                    pass

        # Get project from prompt context if available
        project = self._prompt_context.project_name if self._prompt_context else None
        self.push_screen(XPromptSelectModal(project=project), on_xprompt_select)  # type: ignore[attr-defined]

    def on_prompt_input_bar_workflow_editor_requested(self, event: object) -> None:
        """Handle request to open workflow YAML editor (Ctrl+Y)."""
        from ...widgets import PromptInputBar

        if not isinstance(event, PromptInputBar.WorkflowEditorRequested):
            return

        if self._prompt_context is None:
            return

        result = self._open_workflow_yaml_editor()  # type: ignore[attr-defined]
        if result:
            workflow_name, _file_path = result
            self._finish_agent_launch(f"#{workflow_name}")  # type: ignore[attr-defined]
        else:
            self.notify("No workflow from editor - cancelled", severity="warning")  # type: ignore[attr-defined]
            self._unmount_prompt_bar()
            self._prompt_context = None
