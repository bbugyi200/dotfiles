"""Custom agent workflow mixin for the ace TUI app."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .agent_workflow_launch import AgentLaunchMixin

if TYPE_CHECKING:
    from ...changespec import ChangeSpec
    from ..models import Agent

# Type alias for tab names
TabName = Literal["changespecs", "agents", "axe"]


@dataclass
class _PromptContext:
    """Context for in-progress agent prompt input."""

    project_name: str
    cl_name: str | None
    new_cl_name: str | None
    parent_cl_name: str | None
    project_file: str
    workspace_dir: str
    workspace_num: int
    workflow_name: str
    timestamp: str
    history_sort_key: str
    display_name: str
    update_target: str
    bug: str | None = None
    fixed_bug: str | None = None


class AgentWorkflowMixin(AgentLaunchMixin):
    """Mixin providing custom agent workflow actions."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    current_idx: int
    current_tab: TabName
    marked_indices: set[int]
    _agents: list[Agent]

    # State for prompt input
    _prompt_context: _PromptContext | None = None
    # State for bulk agent runs
    _bulk_changespecs: list[ChangeSpec] | None = None

    def action_start_agent_from_changespec(self) -> None:
        """Start agent from current ChangeSpec (CLs tab only, bound to R)."""
        if self.current_tab != "changespecs":
            return

        if self.marked_indices:
            self._start_agents_from_marked()
        else:
            self._start_agent_from_changespec()

    def action_start_custom_agent(self) -> None:
        """Start a custom agent by selecting project or CL (works on all tabs)."""
        from ..modals import (
            BugInputModal,
            BugInputResult,
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

            # Determine selection type and details
            if isinstance(result, str):
                # Custom name entered - treat as new project name
                selection_type = "project"
                project_name: str = result
                selected_cl_name = None
            elif result.item_type == "project":
                selection_type = "project"
                selected_cl_name = None
                project_name = result.project_name
            else:
                selection_type = "cl"
                selected_cl_name = result.cl_name
                project_name = result.project_name

            def on_cl_name_input(result: CLNameResult | None) -> None:
                # Handle cancel
                if result is None or result.action == CLNameAction.CANCEL:
                    self.notify("CL name cancelled")  # type: ignore[attr-defined]
                    return

                new_cl_name = result.cl_name

                # Determine sort key for prompt history (never use new_cl_name)
                history_sort_key = selected_cl_name or project_name

                # For projects, CL name is required (modal validates this)
                if selection_type == "project":
                    if new_cl_name is None:
                        self.notify("CL name cancelled for project")  # type: ignore[attr-defined]
                        return

                    # Show bug input modal for project selections
                    def on_bug_input(bug_result: BugInputResult | None) -> None:
                        if bug_result is None or bug_result.cancelled:
                            self.notify("Cancelled")  # type: ignore[attr-defined]
                            return

                        # Determine bug vs fixed_bug based on is_fixed flag
                        bug_value = bug_result.bug if not bug_result.is_fixed else None
                        fixed_bug_value = (
                            bug_result.bug if bug_result.is_fixed else None
                        )

                        self._show_prompt_input_bar(
                            project_name,
                            cl_name=None,
                            update_target="p4head",
                            new_cl_name=new_cl_name,
                            history_sort_key=history_sort_key or project_name,
                            bug=bug_value,
                            fixed_bug=fixed_bug_value,
                        )

                    self.push_screen(BugInputModal(), on_bug_input)  # type: ignore[attr-defined]
                else:
                    if new_cl_name is None and selected_cl_name is None:
                        self.notify("No CL name and no selected CL")  # type: ignore[attr-defined]
                        return
                    self._show_prompt_input_bar(
                        project_name,
                        cl_name=selected_cl_name,
                        update_target=selected_cl_name or "",
                        new_cl_name=new_cl_name,
                        history_sort_key=history_sort_key or project_name,
                    )

            # Show CL name input modal
            self.push_screen(  # type: ignore[attr-defined]
                CLNameInputModal(
                    selection_type=selection_type,  # type: ignore[arg-type]
                    selected_cl_name=selected_cl_name,
                    project_name=project_name,
                ),
                on_cl_name_input,
            )

        self.push_screen(ProjectSelectModal(), on_project_select)  # type: ignore[attr-defined]

    def _start_agent_from_changespec(self) -> None:
        """Start agent using current ChangeSpec (skips ProjectSelectModal).

        This is used when pressing space on the CLs tab - it infers the
        project and CL name from the currently selected ChangeSpec. Shows
        CLNameInputModal to optionally create a new CL.
        """
        from ..modals import CLNameAction, CLNameInputModal, CLNameResult

        if not self.changespecs:
            self.notify("No ChangeSpecs available", severity="warning")  # type: ignore[attr-defined]
            return

        changespec = self.changespecs[self.current_idx]
        project_name = changespec.project_basename
        cl_name = changespec.name

        def on_cl_name_input(result: CLNameResult | None) -> None:
            if result is None or result.action == CLNameAction.CANCEL:
                self.notify("CL name cancelled")  # type: ignore[attr-defined]
                return

            new_cl_name = result.cl_name

            self._show_prompt_input_bar(
                project_name,
                cl_name=cl_name,
                update_target=cl_name,
                new_cl_name=new_cl_name,
                history_sort_key=cl_name,
            )

        self.push_screen(  # type: ignore[attr-defined]
            CLNameInputModal(
                selection_type="cl",
                selected_cl_name=cl_name,
                project_name=project_name,
            ),
            on_cl_name_input,
        )

    def _start_agents_from_marked(self) -> None:
        """Start agents for all marked ChangeSpecs.

        Shows CLNameInputModal first, then a single prompt input bar.
        The prompt and optional new CL name will be used for all marked items.
        """
        from ..modals import CLNameAction, CLNameInputModal, CLNameResult

        if not self.marked_indices:
            self.notify("No marked ChangeSpecs", severity="warning")  # type: ignore[attr-defined]
            return

        # Collect all marked ChangeSpecs (sorted by index for consistency)
        self._bulk_changespecs = [
            self.changespecs[idx]
            for idx in sorted(self.marked_indices)
            if idx < len(self.changespecs)
        ]

        if not self._bulk_changespecs:
            self.notify("No valid marked ChangeSpecs", severity="warning")  # type: ignore[attr-defined]
            self._bulk_changespecs = None
            return

        # Use first changespec for prompt context (history, etc.)
        first_cs = self._bulk_changespecs[0]
        count = len(self._bulk_changespecs)

        def on_cl_name_input(result: CLNameResult | None) -> None:
            if result is None or result.action == CLNameAction.CANCEL:
                self.notify("CL name cancelled")  # type: ignore[attr-defined]
                self._bulk_changespecs = None
                return

            new_cl_name = result.cl_name
            self.notify(f"Running agent on {count} marked CL(s)")  # type: ignore[attr-defined]

            self._show_prompt_input_bar(
                first_cs.project_basename,
                cl_name=first_cs.name,
                update_target=first_cs.name,
                new_cl_name=new_cl_name,
                history_sort_key=first_cs.name,
            )

        self.push_screen(  # type: ignore[attr-defined]
            CLNameInputModal(
                selection_type="cl",
                selected_cl_name=first_cs.name,
                project_name=first_cs.project_basename,
            ),
            on_cl_name_input,
        )

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

        from ..widgets import PromptInputBar

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
        self._prompt_context = _PromptContext(
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
        from ..widgets import PromptInputBar

        try:
            bar = self.query_one("#prompt-input-bar", PromptInputBar)  # type: ignore[attr-defined]
            bar.remove()
        except Exception:
            pass  # Bar not present

    def on_prompt_input_bar_submitted(self, event: object) -> None:
        """Handle prompt submission from the input bar."""
        from ..widgets import PromptInputBar

        if not isinstance(event, PromptInputBar.Submitted):
            return

        prompt = event.value
        if not prompt:
            self.notify("Empty prompt - cancelled", severity="warning")  # type: ignore[attr-defined]
            self._unmount_prompt_bar()
            self._prompt_context = None
            return

        self._finish_agent_launch(prompt)

    def on_prompt_input_bar_cancelled(self, event: object) -> None:
        """Handle cancellation from the input bar."""
        from ..widgets import PromptInputBar

        if not isinstance(event, PromptInputBar.Cancelled):
            return

        self.notify("Prompt input cancelled")  # type: ignore[attr-defined]
        self._unmount_prompt_bar()
        self._prompt_context = None

    def on_prompt_input_bar_editor_requested(self, event: object) -> None:
        """Handle request to open external editor (Ctrl+G)."""
        from ..widgets import PromptInputBar

        if not isinstance(event, PromptInputBar.EditorRequested):
            return

        if self._prompt_context is None:
            return

        # Suspend TUI and open editor with current text
        prompt = self._open_editor_for_agent_prompt(event.current_text)
        if prompt:
            self._finish_agent_launch(prompt)
        else:
            self.notify("No prompt from editor - cancelled", severity="warning")  # type: ignore[attr-defined]
            self._unmount_prompt_bar()
            self._prompt_context = None

    def on_prompt_input_bar_history_requested(self, event: object) -> None:
        """Handle request to show prompt history picker ('.')."""
        from ..widgets import PromptInputBar

        if not isinstance(event, PromptInputBar.HistoryRequested):
            return

        if self._prompt_context is None:
            return

        from ..modals import PromptHistoryModal

        def on_history_select(result: str | None) -> None:
            if result:
                # Open editor with selected prompt (preserves fzf behavior)
                edited_prompt = self._open_editor_for_agent_prompt(result)
                if edited_prompt:
                    self._finish_agent_launch(edited_prompt)
                else:
                    self.notify("No prompt from editor - cancelled", severity="warning")  # type: ignore[attr-defined]
                    self._unmount_prompt_bar()
                    self._prompt_context = None
            else:
                self.notify("No prompt from history - cancelled", severity="warning")  # type: ignore[attr-defined]
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
        from ..widgets import PromptInputBar

        if not isinstance(event, PromptInputBar.SnippetRequested):
            return

        from ..modals import SnippetSelectModal

        def on_snippet_select(result: str | None) -> None:
            if result:
                # Insert snippet name into the input bar
                try:
                    bar = self.query_one("#prompt-input-bar", PromptInputBar)  # type: ignore[attr-defined]
                    bar.insert_snippet(result)
                except Exception:
                    pass

        self.push_screen(SnippetSelectModal(), on_snippet_select)  # type: ignore[attr-defined]

    def _open_editor_for_agent_prompt(self, initial_content: str = "") -> str | None:
        """Suspend TUI and open editor for prompt input.

        Args:
            initial_content: Initial text to populate the editor with.

        Returns:
            The prompt content, or None if empty/cancelled.
        """
        import subprocess
        import tempfile

        def run_editor() -> str | None:
            fd, temp_path = tempfile.mkstemp(suffix=".md", prefix="gai_ace_prompt_")
            # Write initial content if provided
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(initial_content)

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
