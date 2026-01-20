"""Accept and mail workflow methods for the ace TUI app."""

from __future__ import annotations

from accept_workflow.parsing import expand_shorthand_proposals, parse_proposal_entries

from ....changespec import ChangeSpec
from ._types import HintMixinBase


class AcceptMailMixin(HintMixinBase):
    """Mixin providing accept and mail workflow actions."""

    def _process_accept_input(self, user_input: str) -> None:
        """Process accept proposal input.

        Supports the @ suffix for triggering mail after accept:
        - "a b c@" - accept proposals a, b, c and then mail the CL
        - "@" alone - run full mail flow (mail prep first, then mark ready, then mail)
        """
        if not user_input:
            return

        changespec = self.changespecs[self.current_idx]

        # Special case: "@" alone means run full mail flow
        # (mail prep first, then mark ready to mail, then execute mail)
        if user_input.strip() == "@":
            self._handle_at_alone_mail_flow(changespec)
            return

        # Split input into args
        args = user_input.split()

        # Check if the last argument ends with "@" (trigger mail after accept)
        should_mail = False
        if args and args[-1].endswith("@"):
            should_mail = True
            # Strip the "@" suffix from the last argument
            args[-1] = args[-1][:-1]
            # If the last arg is now empty (it was just "@"), remove it
            if not args[-1]:
                args.pop()
            # If no args left after removing "@", that's an error
            if not args:
                self.notify("Invalid format", severity="warning")  # type: ignore[attr-defined]
                return

        # Try to expand shorthand and parse
        expanded = expand_shorthand_proposals(args, self._accept_last_base)
        if expanded is None:
            if self._accept_last_base is None:
                self.notify(  # type: ignore[attr-defined]
                    "No accepted commits - cannot use shorthand (a b c)",
                    severity="warning",
                )
            else:
                self.notify("Invalid format", severity="warning")  # type: ignore[attr-defined]
            return

        entries = parse_proposal_entries(expanded)
        if entries is None:
            self.notify("Invalid proposal format", severity="warning")  # type: ignore[attr-defined]
            return

        # Run the accept workflow (with mark_ready_to_mail flag if @ suffix was used)
        self._run_accept_workflow(  # type: ignore[attr-defined]
            changespec, entries, mark_ready_to_mail=should_mail
        )

        # If should_mail is True, the workflow already marked as ready to mail.
        # Now trigger the mail flow.
        if should_mail:
            self._trigger_mail_after_accept()  # type: ignore[attr-defined]

    def _trigger_mail_after_accept(self) -> None:
        """Trigger the mail flow after a successful accept with @ suffix.

        This reloads the changespec (which now has READY TO MAIL suffix)
        and triggers the mail action.
        """
        # Reload to get updated changespec with READY TO MAIL suffix
        self._reload_and_reposition()  # type: ignore[attr-defined]

        # Now call the mail action (same as pressing 'm')
        self.action_mail()  # type: ignore[attr-defined]

    def _handle_at_alone_mail_flow(self, changespec: ChangeSpec) -> None:
        """Handle the full mail flow when "@" alone is input.

        This runs the mail operations in a specific order:
        1. Run mail prep FIRST (reviewer prompts, description modification, nvim)
        2. Ask user if they want to mail
        3. Run mark_ready_to_mail operations (kill processes, reject proposals)
        4. Set status atomically (to "Mailed" if user confirmed, or READY TO MAIL if not)
        5. Execute hg mail if user confirmed

        Args:
            changespec: The ChangeSpec to process
        """
        from rich.console import Console

        from ....changespec import get_base_status, has_ready_to_mail_suffix
        from ....mail_ops import MailPrepResult, execute_mail, prepare_mail

        # Validate: must be Drafted without READY TO MAIL suffix
        base_status = get_base_status(changespec.status)
        if base_status != "Drafted":
            self.notify("Must be Drafted status", severity="warning")  # type: ignore[attr-defined]
            return
        if has_ready_to_mail_suffix(changespec.status):
            self.notify("Already marked as ready to mail", severity="warning")  # type: ignore[attr-defined]
            return

        # STEP 1: Run mail prep FIRST (prompts for reviewers, modifies description, opens nvim)
        prep_result: MailPrepResult | None = None

        def run_mail_prep() -> MailPrepResult | None:
            console = Console()
            return prepare_mail(changespec, console)

        with self.suspend():  # type: ignore[attr-defined]
            prep_result = run_mail_prep()

        if prep_result is None:
            # User aborted or error occurred
            self._reload_and_reposition()  # type: ignore[attr-defined]
            return

        # STEP 2: Mark ready to mail with appropriate final status
        # If user said "yes" to mail, set status directly to "Mailed"
        # If user said "no", just add READY TO MAIL suffix
        final_status = "Mailed" if prep_result.should_mail else None
        success = self._mark_ready_to_mail_atomic(changespec, final_status)  # type: ignore[attr-defined]

        if not success:
            self.notify("Failed to mark as ready to mail", severity="error")  # type: ignore[attr-defined]
            self._reload_and_reposition()  # type: ignore[attr-defined]
            return

        # STEP 3: Execute mail if user confirmed
        if prep_result.should_mail:

            def run_mail() -> bool:
                console = Console()
                return execute_mail(changespec, prep_result.target_dir, console)

            with self.suspend():  # type: ignore[attr-defined]
                mail_success = run_mail()

            if mail_success:
                self.notify("CL mailed successfully")  # type: ignore[attr-defined]
            else:
                self.notify("Failed to mail CL", severity="error")  # type: ignore[attr-defined]
        else:
            self.notify("Marked as ready to mail")  # type: ignore[attr-defined]

        self._reload_and_reposition()  # type: ignore[attr-defined]
