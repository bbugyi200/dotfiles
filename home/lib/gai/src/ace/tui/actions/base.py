"""Base action methods for the ace TUI app."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from ...hooks.history import get_last_accepted_history_entry_id
from ...query import QueryParseError, parse_query, to_canonical_string
from ...saved_queries import (
    delete_query,
    get_next_available_slot,
    load_saved_queries,
    save_query,
)
from ..modals import (
    QueryEditModal,
    StatusModal,
    WorkflowSelectModal,
)
from ..widgets import HintInputBar

if TYPE_CHECKING:
    from ...changespec import ChangeSpec
    from ..types import TabName


class BaseActionsMixin:
    """Mixin providing status, workflow, and tool actions."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    current_idx: int
    current_tab: TabName
    query_string: str
    parsed_query: Any

    # --- Status Actions ---

    def action_change_status(self) -> None:
        """Open status change modal."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        def on_dismiss(new_status: str | None) -> None:
            if new_status:
                self._apply_status_change(changespec, new_status)

        self.push_screen(StatusModal(changespec.status), on_dismiss)  # type: ignore[attr-defined]

    def _apply_status_change(self, changespec: ChangeSpec, new_status: str) -> None:
        """Apply a status change to a ChangeSpec."""
        from status_state_machine import (
            remove_ready_to_mail_suffix,
            transition_changespec_status,
        )

        from ...revert import revert_changespec
        from ...status import STATUS_REVERTED

        # Special handling for "Reverted" status
        if new_status == STATUS_REVERTED:
            # Need to suspend for revert workflow
            def run_revert() -> tuple[bool, str | None]:
                from rich.console import Console

                console = Console()
                return revert_changespec(changespec, console)

            with self.suspend():  # type: ignore[attr-defined]
                success, error_msg = run_revert()

            if not success:
                self.notify(f"Error reverting: {error_msg}", severity="error")  # type: ignore[attr-defined]
            self._reload_and_reposition()  # type: ignore[attr-defined]
            return

        # Remove READY TO MAIL suffix if present before transitioning
        remove_ready_to_mail_suffix(changespec.file_path, changespec.name)

        # Update the status in the project file
        success, old_status, error_msg = transition_changespec_status(
            changespec.file_path,
            changespec.name,
            new_status,
            validate=False,
        )

        if success:
            self.notify(f"Status updated: {old_status} -> {new_status}")  # type: ignore[attr-defined]
        else:
            self.notify(f"Error: {error_msg}", severity="error")  # type: ignore[attr-defined]

        self._reload_and_reposition()  # type: ignore[attr-defined]

    # --- Workflow Actions ---

    def action_run_workflow(self) -> None:
        """Run a workflow on the current ChangeSpec."""
        from ...operations import get_available_workflows

        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]
        workflows = get_available_workflows(changespec)

        if not workflows:
            self.notify("No workflows available", severity="warning")  # type: ignore[attr-defined]
            return

        if len(workflows) == 1:
            # Single workflow, run directly
            self._run_workflow(changespec, 0)
        else:
            # Multiple workflows, show selection modal

            def on_dismiss(workflow_idx: int | None) -> None:
                if workflow_idx is not None:
                    self._run_workflow(changespec, workflow_idx)

            self.push_screen(WorkflowSelectModal(workflows), on_dismiss)  # type: ignore[attr-defined]

    def _run_workflow(self, changespec: ChangeSpec, workflow_index: int) -> None:
        """Run a specific workflow."""
        from ...handlers import handle_run_workflow
        from .._workflow_context import WorkflowContext

        def run_handler() -> tuple[list[ChangeSpec], int]:
            ctx = WorkflowContext()
            return handle_run_workflow(
                ctx,  # type: ignore[arg-type]
                changespec,
                self.changespecs,
                self.current_idx,
                workflow_index,
            )

        with self.suspend():  # type: ignore[attr-defined]
            try:
                new_changespecs, new_idx = run_handler()
            except Exception as e:
                self.notify(f"Workflow error: {e}", severity="error")  # type: ignore[attr-defined]
                self._reload_and_reposition()  # type: ignore[attr-defined]
                return

        self._reload_and_reposition()  # type: ignore[attr-defined]

    # --- Tool Actions ---

    def action_show_diff(self) -> None:
        """Show diff for the current ChangeSpec."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        from ...handlers import handle_show_diff
        from .._workflow_context import WorkflowContext

        def run_handler() -> None:
            ctx = WorkflowContext()
            handle_show_diff(ctx, changespec)  # type: ignore[arg-type]

        with self.suspend():  # type: ignore[attr-defined]
            run_handler()

    def action_reword(self) -> None:
        """Reword (change CL description) for the current ChangeSpec."""
        from ...changespec import get_base_status

        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        # Validate CL is set
        if changespec.cl is None:
            self.notify("CL is not set", severity="warning")  # type: ignore[attr-defined]
            return

        # Validate status is Drafted or Mailed
        base_status = get_base_status(changespec.status)
        if base_status not in ("Drafted", "Mailed"):
            self.notify(  # type: ignore[attr-defined]
                "Reword is only available for Drafted or Mailed ChangeSpecs",
                severity="warning",
            )
            return

        from ...handlers import handle_reword
        from .._workflow_context import WorkflowContext

        def run_handler() -> None:
            ctx = WorkflowContext()
            handle_reword(ctx, changespec)  # type: ignore[arg-type]

        with self.suspend():  # type: ignore[attr-defined]
            run_handler()

        self._reload_and_reposition()  # type: ignore[attr-defined]

    def action_mail(self) -> None:
        """Mail the current ChangeSpec."""
        from ...changespec import has_ready_to_mail_suffix

        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        if not has_ready_to_mail_suffix(changespec.status):
            self.notify("ChangeSpec is not ready to mail", severity="warning")  # type: ignore[attr-defined]
            return

        from ...handlers import handle_mail
        from .._workflow_context import WorkflowContext

        def run_handler() -> tuple[list[ChangeSpec], int]:
            ctx = WorkflowContext()
            return handle_mail(ctx, changespec, self.changespecs, self.current_idx)  # type: ignore[arg-type]

        with self.suspend():  # type: ignore[attr-defined]
            run_handler()

        self._reload_and_reposition()  # type: ignore[attr-defined]

    def action_findreviewers(self) -> None:
        """Find reviewers for the current ChangeSpec."""
        from ...changespec import has_ready_to_mail_suffix

        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        if not has_ready_to_mail_suffix(changespec.status):
            self.notify("ChangeSpec is not ready to mail", severity="warning")  # type: ignore[attr-defined]
            return

        from ...handlers import handle_findreviewers
        from .._workflow_context import WorkflowContext

        def run_handler() -> None:
            ctx = WorkflowContext()
            handle_findreviewers(ctx, changespec)  # type: ignore[arg-type]

        with self.suspend():  # type: ignore[attr-defined]
            run_handler()

    def action_mark_ready_to_mail(self) -> None:
        """Mark the current ChangeSpec as ready to mail.

        This action:
        1. Kills all running agents
        2. Kills running hooks (except $-prefixed ones)
        3. Rejects all new proposals
        4. Adds the READY TO MAIL suffix to the STATUS line
        """
        from commit_utils import reject_all_new_proposals
        from status_state_machine import add_ready_to_mail_suffix

        from ...changespec import get_base_status, has_ready_to_mail_suffix
        from ...comments import update_changespec_comments_field
        from ...comments.operations import mark_comment_agents_as_killed
        from ...hooks import (
            kill_running_agent_processes,
            kill_running_hook_processes_except_dollar,
            mark_hook_agents_as_killed,
            mark_hooks_as_killed,
            update_changespec_hooks_field,
        )

        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        # Validate: must be Drafted without READY TO MAIL suffix
        base_status = get_base_status(changespec.status)
        if base_status != "Drafted":
            self.notify("Must be Drafted status", severity="warning")  # type: ignore[attr-defined]
            return
        if has_ready_to_mail_suffix(changespec.status):
            self.notify("Already marked as ready to mail", severity="warning")  # type: ignore[attr-defined]
            return

        # 1. Kill all running agents (hooks and comments)
        killed_hook_agents, killed_comment_agents = kill_running_agent_processes(
            changespec
        )

        # Update hooks to mark agents as killed and persist
        if killed_hook_agents and changespec.hooks:
            updated_hooks = mark_hook_agents_as_killed(
                changespec.hooks, killed_hook_agents
            )
            update_changespec_hooks_field(
                changespec.file_path, changespec.name, updated_hooks
            )

        # Update comments to mark agents as killed and persist
        if killed_comment_agents and changespec.comments:
            updated_comments = mark_comment_agents_as_killed(
                changespec.comments, killed_comment_agents
            )
            update_changespec_comments_field(
                changespec.file_path, changespec.name, updated_comments
            )

        # 2. Kill running hooks except $-prefixed ones
        killed_hooks = kill_running_hook_processes_except_dollar(changespec)

        # Update hooks to mark as killed and persist
        if killed_hooks and changespec.hooks:
            updated_hooks = mark_hooks_as_killed(
                changespec.hooks, killed_hooks, "Manually marked ready to mail"
            )
            update_changespec_hooks_field(
                changespec.file_path, changespec.name, updated_hooks
            )

        # 3. Reject all new proposals
        reject_all_new_proposals(changespec.file_path, changespec.name)

        # 4. Add READY TO MAIL suffix
        success = add_ready_to_mail_suffix(changespec.file_path, changespec.name)

        if success:
            self.notify("Marked as ready to mail")  # type: ignore[attr-defined]
        else:
            self.notify("Failed to mark as ready to mail", severity="error")  # type: ignore[attr-defined]

        self._reload_and_reposition()  # type: ignore[attr-defined]

    def action_accept_proposal(self) -> None:
        """Accept a proposal for the current ChangeSpec."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        # Check if there are proposed entries
        if not changespec.commits or not any(e.is_proposed for e in changespec.commits):
            self.notify("No proposals to accept", severity="warning")  # type: ignore[attr-defined]
            return

        # Get the last accepted (all-numeric) entry ID to filter proposals
        last_accepted_id = get_last_accepted_history_entry_id(changespec)
        last_accepted_base = int(last_accepted_id) if last_accepted_id else None

        # Build placeholder with just proposal letters for NEW proposals only
        # (proposals whose base number matches the latest all-numeric entry)
        proposal_letters: list[str] = []
        for entry in changespec.commits:
            if entry.is_proposed and entry.number == last_accepted_base:
                # Extract just the letter suffix from display_number (e.g., "2a" -> "a")
                display_num = entry.display_number
                if display_num and len(display_num) > 0:
                    # The letter is the last character
                    proposal_letters.append(display_num[-1])

        placeholder = " ".join(proposal_letters)

        # Store accept mode state
        self._accept_mode_active = True  # type: ignore[attr-defined]
        self._accept_last_base = last_accepted_id  # type: ignore[attr-defined]

        # Mount the accept input bar
        detail_container = self.query_one("#detail-container")  # type: ignore[attr-defined]
        accept_bar = HintInputBar(
            mode="accept", placeholder=placeholder, id="hint-input-bar"
        )
        detail_container.mount(accept_bar)

    def _run_accept_workflow(
        self,
        changespec: ChangeSpec,
        entries: list[tuple[str, str | None]],
        mark_ready_to_mail: bool = False,
    ) -> None:
        """Run the accept workflow with parsed entries.

        Args:
            changespec: The ChangeSpec to accept proposals for.
            entries: List of (proposal_id, msg) tuples.
            mark_ready_to_mail: If True, also reject remaining proposals and add
                READY TO MAIL suffix to STATUS, all in the same atomic write.
        """
        from accept_workflow import AcceptWorkflow

        def run_handler() -> None:
            # Build display message
            if len(entries) == 1:
                proposal_id, _ = entries[0]
                if mark_ready_to_mail:
                    msg = (
                        f"Accepting proposal {proposal_id} and marking ready to mail..."
                    )
                else:
                    msg = f"Accepting proposal {proposal_id}..."
                self.notify(msg)  # type: ignore[attr-defined]
            else:
                ids = ", ".join(e[0] for e in entries)
                if mark_ready_to_mail:
                    msg = f"Accepting proposals {ids} and marking ready to mail..."
                else:
                    msg = f"Accepting proposals {ids}..."
                self.notify(msg)  # type: ignore[attr-defined]

            # Run accept workflow
            accept_workflow = AcceptWorkflow(
                proposals=entries,
                cl_name=changespec.name,
                project_file=changespec.file_path,
                mark_ready_to_mail=mark_ready_to_mail,
            )
            accept_workflow.run()

        with self.suspend():  # type: ignore[attr-defined]
            run_handler()

        self._reload_and_reposition()  # type: ignore[attr-defined]

    def action_refresh(self) -> None:
        """Refresh the current tab's content."""
        if self.current_tab == "agents":
            self._load_agents()  # type: ignore[attr-defined]
            self._refresh_agent_diff()  # type: ignore[attr-defined]
        else:
            self._reload_and_reposition()  # type: ignore[attr-defined]
        self.notify("Refreshed")  # type: ignore[attr-defined]

    def action_edit_query(self) -> None:
        """Edit the search query.

        Supports saving queries with # prefix:
        - #<N> <query> - Save query to slot N (0-9)
        - # <query> - Save query to next available slot
        - #<N> (no query) - Delete query from slot N
        """
        current_canonical = self.canonical_query_string  # type: ignore[attr-defined]

        def on_dismiss(new_query: str | None) -> None:
            if not new_query:
                return

            # Check for save prefix: #<N> or just #
            save_match = re.match(r"^#(\d)?(.*)$", new_query.strip())

            if save_match:
                slot_specified = save_match.group(1)
                query_part = save_match.group(2).strip()

                if not query_part:
                    # Delete mode: #<N> with no query
                    if slot_specified:
                        if delete_query(slot_specified):
                            self.notify(f"Deleted query from slot {slot_specified}")  # type: ignore[attr-defined]
                            self._refresh_saved_queries_panel()  # type: ignore[attr-defined]
                        else:
                            self.notify("Failed to delete query", severity="error")  # type: ignore[attr-defined]
                    else:
                        self.notify("No slot specified to delete", severity="warning")  # type: ignore[attr-defined]
                    return

                # Save mode: parse and save the query
                try:
                    parsed = parse_query(query_part)
                    canonical = to_canonical_string(parsed)
                except QueryParseError as e:
                    self.notify(f"Invalid query: {e}", severity="error")  # type: ignore[attr-defined]
                    return

                # Determine slot
                if slot_specified:
                    slot = slot_specified
                else:
                    queries = load_saved_queries()
                    slot = get_next_available_slot(queries)
                    if slot is None:
                        self.notify("All 10 slots are full", severity="warning")  # type: ignore[attr-defined]
                        return

                if save_query(slot, canonical):
                    self.notify(f"Saved to slot {slot}: {canonical}")  # type: ignore[attr-defined]
                    self._refresh_saved_queries_panel()  # type: ignore[attr-defined]
                else:
                    self.notify("Failed to save query", severity="error")  # type: ignore[attr-defined]
            else:
                # Normal query update (existing logic)
                try:
                    new_parsed = parse_query(new_query)
                    new_canonical = to_canonical_string(new_parsed)
                    # Only update if the canonical form changed
                    if new_canonical != current_canonical:
                        self.query_string = new_query
                        self.parsed_query = new_parsed
                        self._load_changespecs()  # type: ignore[attr-defined]
                        self._save_current_query()  # type: ignore[attr-defined]
                        self.notify("Query updated")  # type: ignore[attr-defined]
                except QueryParseError as e:
                    self.notify(f"Invalid query: {e}", severity="error")  # type: ignore[attr-defined]

        self.push_screen(QueryEditModal(current_canonical), on_dismiss)  # type: ignore[attr-defined]

    def action_rebase(self) -> None:
        """Open parent selection modal for rebasing the current ChangeSpec."""
        from ...changespec import get_base_status, get_eligible_parents_in_project
        from ..modals import ParentSelectModal

        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        # Validate status is eligible (WIP, Drafted, or Mailed)
        base_status = get_base_status(changespec.status)
        if base_status not in ("WIP", "Drafted", "Mailed"):
            self.notify(  # type: ignore[attr-defined]
                "Rebase is only available for WIP, Drafted, or Mailed ChangeSpecs",
                severity="warning",
            )
            return

        # Get eligible parents from same project file
        eligible_parents = get_eligible_parents_in_project(
            changespec.file_path, changespec.name
        )

        # Always include p4head as the first option (rebasing to root)
        eligible_parents.insert(0, ("p4head", "root"))

        if len(eligible_parents) == 1:  # Only p4head, no other parents
            self.notify(  # type: ignore[attr-defined]
                "No eligible ChangeSpecs to use as parent",
                severity="warning",
            )
            return

        def on_dismiss(selected_parent: str | None) -> None:
            if selected_parent:
                self._run_rebase_workflow(changespec, selected_parent)

        self.push_screen(ParentSelectModal(eligible_parents), on_dismiss)  # type: ignore[attr-defined]

    def _run_rebase_workflow(
        self, changespec: ChangeSpec, new_parent_name: str
    ) -> None:
        """Run the rebase workflow.

        Args:
            changespec: The ChangeSpec being rebased
            new_parent_name: Name of the new parent ChangeSpec
        """
        import os
        import subprocess

        from commit_utils import run_bb_hg_clean
        from running_field import (
            claim_workspace,
            get_first_available_loop_workspace,
            get_workspace_directory_for_num,
            release_workspace,
        )
        from status_state_machine import update_changespec_parent_atomic

        project_basename = os.path.basename(changespec.file_path).replace(".gp", "")
        workspace_num: int | None = None

        def run_handler() -> tuple[bool, str]:
            """Execute rebase in suspended TUI context.

            Returns:
                Tuple of (success, message)
            """
            nonlocal workspace_num

            # Get workspace info
            workspace_num = get_first_available_loop_workspace(changespec.file_path)
            workflow_name = f"rebase-{changespec.name}"

            try:
                workspace_dir, _ = get_workspace_directory_for_num(
                    workspace_num, project_basename
                )
            except RuntimeError as e:
                return (False, f"Failed to get workspace directory: {e}")

            # Claim workspace (use our process ID since this is synchronous)
            pid = os.getpid()
            if not claim_workspace(
                changespec.file_path, workspace_num, workflow_name, pid, changespec.name
            ):
                return (False, "Failed to claim workspace")

            try:
                # Clean workspace before switching branches
                clean_success, clean_error = run_bb_hg_clean(
                    workspace_dir, f"{changespec.name}-rebase"
                )
                if not clean_success:
                    print(f"Warning: bb_hg_clean failed: {clean_error}")

                # Checkout the CL being rebased
                try:
                    result = subprocess.run(
                        ["bb_hg_update", changespec.name],
                        cwd=workspace_dir,
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
                    if result.returncode != 0:
                        error_output = (result.stderr or result.stdout).strip()
                        return (
                            False,
                            f"bb_hg_update failed: {error_output}",
                        )
                except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                    return (False, f"bb_hg_update error: {e}")

                # Run bb_hg_rebase
                try:
                    result = subprocess.run(
                        ["bb_hg_rebase", changespec.name, new_parent_name],
                        cwd=workspace_dir,
                        capture_output=True,
                        text=True,
                        timeout=600,  # 10 minutes for rebase
                    )
                    if result.returncode != 0:
                        error_output = (result.stderr or result.stdout).strip()
                        return (
                            False,
                            f"bb_hg_rebase failed: {error_output}",
                        )
                except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                    return (False, f"bb_hg_rebase error: {e}")

                # Update PARENT field on success
                # If p4head was selected, delete the PARENT field (pass None)
                try:
                    parent_value = (
                        None if new_parent_name == "p4head" else new_parent_name
                    )
                    update_changespec_parent_atomic(
                        changespec.file_path, changespec.name, parent_value
                    )
                except Exception as e:
                    return (False, f"Failed to update PARENT field: {e}")

                return (True, f"Rebased onto {new_parent_name}")

            finally:
                # Always release workspace
                if workspace_num is not None:
                    release_workspace(
                        changespec.file_path,
                        workspace_num,
                        workflow_name,
                        changespec.name,
                    )

        with self.suspend():  # type: ignore[attr-defined]
            success, message = run_handler()

        if success:
            self.notify(message)  # type: ignore[attr-defined]
        else:
            self.notify(f"Rebase failed: {message}", severity="error")  # type: ignore[attr-defined]

        self._reload_and_reposition()  # type: ignore[attr-defined]
