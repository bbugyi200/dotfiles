"""Agent start entry points and leader mode for the ace TUI app."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._types import PromptContext, TabName

if TYPE_CHECKING:
    from ....changespec import ChangeSpec
    from ...models import Agent


class EntryPointsMixin:
    """Mixin providing agent start entry points and leader mode."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    current_idx: int
    current_tab: TabName
    marked_indices: set[int]
    _agents: list[Agent]
    _leader_mode_active: bool

    # State for prompt input
    _prompt_context: PromptContext | None = None
    # State for bulk agent runs
    _bulk_changespecs: list[ChangeSpec] | None = None

    def action_start_agent_from_changespec(self) -> None:
        """Start agent from current ChangeSpec (CLs tab only, bound to space)."""
        if self.current_tab != "changespecs":
            return

        if self.marked_indices:
            self._start_agents_from_marked()
        else:
            self._start_agent_from_changespec_quick()

    def action_start_leader_mode(self) -> None:
        """Enter leader mode for quick shortcuts (CLs tab only, bound to ,)."""
        if self.current_tab != "changespecs":
            return

        self._leader_mode_active = True
        self._update_leader_footer()

    def _handle_leader_key(self, key: str) -> bool:
        """Handle a key press in leader mode.

        Args:
            key: The key that was pressed.

        Returns:
            True if the key was handled, False otherwise.
        """
        # Always exit leader mode
        self._leader_mode_active = False

        if key == "escape":
            # Cancel silently and restore footer
            self._refresh_display()  # type: ignore[attr-defined]
            return True

        if key == "space":
            self._start_agent_from_changespec()
            return True

        if key == "exclamation_mark":
            self._start_bgcmd_from_changespec()  # type: ignore[attr-defined]
            return True

        # Unknown key - just exit mode and restore footer
        self._refresh_display()  # type: ignore[attr-defined]
        return True

    def _start_agent_from_changespec_quick(self) -> None:
        """Start agent from current ChangeSpec without CL name modal.

        This is the quick version that skips CLNameInputModal entirely,
        going directly to the prompt input bar.
        """
        if not self.changespecs:
            self.notify("No ChangeSpecs available", severity="warning")  # type: ignore[attr-defined]
            return

        changespec = self.changespecs[self.current_idx]
        project_name = changespec.project_basename
        cl_name = changespec.name

        # Go directly to prompt input bar, skipping CLNameInputModal
        self._show_prompt_input_bar(  # type: ignore[attr-defined]
            project_name,
            cl_name=cl_name,
            update_target=cl_name,
            new_cl_name=None,  # Key difference: no new CL name
            history_sort_key=cl_name,
        )

    def _update_leader_footer(self) -> None:
        """Update the footer to show leader mode bindings."""
        from ...widgets import KeybindingFooter

        try:
            footer = self.query_one("#keybinding-footer", KeybindingFooter)  # type: ignore[attr-defined]
            footer.update_leader_bindings()
        except Exception:
            pass

    def action_start_custom_agent(self) -> None:
        """Start a custom agent by selecting project or CL (works on all tabs)."""
        from ...modals import (
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

            # Handle home directory selection - skip CL name and bug modals
            if isinstance(result, SelectionItem) and result.item_type == "home":
                self._show_prompt_input_bar_for_home()  # type: ignore[attr-defined]
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

                # Handle project selection
                if selection_type == "project":
                    if new_cl_name is not None:
                        # New CL name provided - show bug input modal (existing behavior)
                        def on_bug_input(bug_result: BugInputResult | None) -> None:
                            if bug_result is None or bug_result.cancelled:
                                self.notify("Cancelled")  # type: ignore[attr-defined]
                                return

                            # Determine bug vs fixed_bug based on is_fixed flag
                            bug_value = (
                                bug_result.bug if not bug_result.is_fixed else None
                            )
                            fixed_bug_value = (
                                bug_result.bug if bug_result.is_fixed else None
                            )

                            self._show_prompt_input_bar(  # type: ignore[attr-defined]
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
                        # No CL name provided - skip bug modal, go straight to prompt
                        self._show_prompt_input_bar(  # type: ignore[attr-defined]
                            project_name,
                            cl_name=None,
                            update_target="p4head",
                            new_cl_name=None,
                            history_sort_key=history_sort_key or project_name,
                        )
                else:
                    if new_cl_name is None and selected_cl_name is None:
                        self.notify("No CL name and no selected CL")  # type: ignore[attr-defined]
                        return
                    self._show_prompt_input_bar(  # type: ignore[attr-defined]
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
        from ...modals import CLNameAction, CLNameInputModal, CLNameResult

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

            self._show_prompt_input_bar(  # type: ignore[attr-defined]
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
        from ...modals import CLNameAction, CLNameInputModal, CLNameResult

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

            self._show_prompt_input_bar(  # type: ignore[attr-defined]
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
