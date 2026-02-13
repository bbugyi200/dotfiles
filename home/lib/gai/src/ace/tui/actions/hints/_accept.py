"""Accept and mail workflow methods for the ace TUI app."""

from __future__ import annotations

from accept_workflow.parsing import expand_shorthand_proposals, parse_proposal_entries

from ....changespec import ChangeSpec
from ._types import HintMixinBase


def _strip_accept_suffixes(
    args: list[str],
) -> tuple[list[str] | None, bool, bool]:
    """Strip ``!`` and ``@`` suffixes from the last arg.

    Returns:
        A tuple of ``(cleaned_args, should_mail, skip_amend)``.
        ``cleaned_args`` is ``None`` when the args are invalid (empty after
        stripping).
    """
    should_mail = False
    skip_amend = False
    if not args:
        return None, should_mail, skip_amend

    last_arg = args[-1]
    while last_arg.endswith(("!", "@")):
        if last_arg[-1] == "!":
            skip_amend = True
        else:
            should_mail = True
        last_arg = last_arg[:-1]
    args[-1] = last_arg

    # Remove empty last arg, error if no args left
    if not args[-1]:
        args.pop()
    if not args:
        return None, should_mail, skip_amend

    return args, should_mail, skip_amend


class AcceptMailMixin(HintMixinBase):
    """Mixin providing accept and mail workflow actions."""

    def _process_accept_input(self, user_input: str) -> None:
        """Process accept proposal input.

        Supports suffixes on the last proposal argument:
        - ``!`` — skip the checkout/apply/amend steps (bookkeeping only)
        - ``@`` — trigger mail after accept
        - ``!@`` or ``@!`` — combine both (any order)
        - ``@`` alone — run full mail flow (mail prep first, then mark ready,
          then mail)
        """
        if not user_input:
            return

        changespec = self.changespecs[self.current_idx]

        # Special case: "@" alone means run full mail flow
        # (mail prep first, then mark ready to mail, then execute mail)
        if user_input.strip() == "@":
            self._handle_at_alone_mail_flow(changespec)
            return

        # Split input into args and strip suffixes
        args = user_input.split()
        cleaned, should_mail, skip_amend = _strip_accept_suffixes(args)
        if cleaned is None:
            self.notify("Invalid format", severity="warning")  # type: ignore[attr-defined]
            return
        args = cleaned

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
            changespec,
            entries,
            mark_ready_to_mail=should_mail,
            skip_amend=skip_amend,
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
        1. Claim a workspace in the 100-199 range
        2. Run mail prep FIRST (reviewer prompts, description modification, nvim)
        3. Ask user if they want to mail
        4. Run mark_ready_to_mail operations (kill processes, reject proposals)
        5. Set status atomically (to "Mailed" if user confirmed, or READY TO MAIL if not)
        6. Execute hg mail if user confirmed
        7. Release the workspace

        Args:
            changespec: The ChangeSpec to process
        """
        import os

        from rich.console import Console
        from running_field import (
            claim_workspace,
            get_first_available_axe_workspace,
            get_workspace_directory_for_num,
            release_workspace,
        )

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

        # Claim a workspace in the 100-199 range
        workspace_num = get_first_available_axe_workspace(changespec.file_path)

        if not claim_workspace(
            changespec.file_path, workspace_num, "mail", os.getpid(), changespec.name
        ):
            self.notify("Failed to claim workspace", severity="error")  # type: ignore[attr-defined]
            return

        try:
            # Get workspace directory
            workspace_dir, workspace_suffix = get_workspace_directory_for_num(
                workspace_num, changespec.project_basename
            )

            if workspace_suffix:
                self.notify(f"Using workspace: {workspace_suffix}")  # type: ignore[attr-defined]

            # STEP 1: Run mail prep FIRST (prompts for reviewers, modifies description, opens nvim)
            prep_result: MailPrepResult | None = None

            def run_mail_prep() -> MailPrepResult | None:
                console = Console()
                return prepare_mail(changespec, workspace_dir, console)

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
                    return execute_mail(changespec, workspace_dir, console)

                with self.suspend():  # type: ignore[attr-defined]
                    mail_success = run_mail()

                if mail_success:
                    self.notify("CL mailed successfully")  # type: ignore[attr-defined]
                else:
                    self.notify("Failed to mail CL", severity="error")  # type: ignore[attr-defined]
            else:
                self.notify("Marked as ready to mail")  # type: ignore[attr-defined]

            self._reload_and_reposition()  # type: ignore[attr-defined]

        finally:
            # Always release the workspace
            release_workspace(
                changespec.file_path, workspace_num, "mail", changespec.name
            )
