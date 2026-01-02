"""Base action methods for the ace TUI app."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from ...query import QueryParseError, parse_query, to_canonical_string
from ...saved_queries import (
    delete_query,
    get_next_available_slot,
    load_saved_queries,
    save_query,
)
from ..modals import (
    AcceptProposalModal,
    QueryEditModal,
    StatusModal,
    WorkflowSelectModal,
)

if TYPE_CHECKING:
    from ...changespec import ChangeSpec


class BaseActionsMixin:
    """Mixin providing status, workflow, and tool actions."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    current_idx: int
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

    def action_run_query(self) -> None:
        """Run a query on the current ChangeSpec."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        from ...handlers import handle_run_query
        from .._workflow_context import WorkflowContext

        def run_handler() -> None:
            ctx = WorkflowContext()
            handle_run_query(ctx, changespec)  # type: ignore[arg-type]

        with self.suspend():  # type: ignore[attr-defined]
            run_handler()

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

    def action_accept_proposal(self) -> None:
        """Accept a proposal for the current ChangeSpec."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        # Check if there are proposed entries
        if not changespec.commits or not any(e.is_proposed for e in changespec.commits):
            self.notify("No proposals to accept", severity="warning")  # type: ignore[attr-defined]
            return

        def on_dismiss(entries: list[tuple[str, str | None]] | None) -> None:
            if entries is None:
                return  # User cancelled

            self._run_accept_workflow(changespec, entries)

        self.push_screen(AcceptProposalModal(changespec), on_dismiss)  # type: ignore[attr-defined]

    def _run_accept_workflow(
        self,
        changespec: ChangeSpec,
        entries: list[tuple[str, str | None]],
    ) -> None:
        """Run the accept workflow with parsed entries."""
        from accept_workflow import AcceptWorkflow

        def run_handler() -> None:
            # Build display message
            if len(entries) == 1:
                proposal_id, _ = entries[0]
                self.notify(f"Accepting proposal {proposal_id}...")  # type: ignore[attr-defined]
            else:
                ids = ", ".join(e[0] for e in entries)
                self.notify(f"Accepting proposals {ids}...")  # type: ignore[attr-defined]

            # Run accept workflow
            accept_workflow = AcceptWorkflow(
                proposals=entries,
                cl_name=changespec.name,
                project_file=changespec.file_path,
            )
            accept_workflow.run()

        with self.suspend():  # type: ignore[attr-defined]
            run_handler()

        self._reload_and_reposition()  # type: ignore[attr-defined]

    def action_refresh(self) -> None:
        """Refresh the ChangeSpec list."""
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
                        self.notify("Query updated")  # type: ignore[attr-defined]
                except QueryParseError as e:
                    self.notify(f"Invalid query: {e}", severity="error")  # type: ignore[attr-defined]

        self.push_screen(QueryEditModal(current_canonical), on_dismiss)  # type: ignore[attr-defined]
