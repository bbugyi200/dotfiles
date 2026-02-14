"""AcceptWorkflow class and main entry point for accepting proposals."""

import os
import sys
from typing import NoReturn

from ace.changespec import ChangeSpec, CommitEntry
from ace.operations import update_to_changespec
from commit_utils import apply_diff_to_workspace, clean_workspace, run_bb_hg_clean
from rich_utils import print_status
from running_field import (
    claim_workspace,
    get_claimed_workspaces,
    get_first_available_axe_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)
from vcs_provider import get_vcs_provider
from workflow_base import BaseWorkflow
from workflow_utils import (
    add_test_hooks_if_available,
    get_changespec_from_file,
    get_cl_name_from_branch,
    get_project_file_path,
    get_project_from_workspace,
)

from .conflict_check import ConflictCheckResult, run_conflict_check
from .parsing import find_proposal_entry, parse_proposal_entries, parse_proposal_id
from .renumber import renumber_commit_entries


class AcceptWorkflow(BaseWorkflow):
    """A workflow for accepting one or more proposed COMMITS entries."""

    def __init__(
        self,
        proposals: list[tuple[str, str | None]],
        cl_name: str | None = None,
        project_file: str | None = None,
        mark_ready_to_mail: bool = False,
        skip_amend: bool = False,
    ) -> None:
        """Initialize the accept workflow.

        Args:
            proposals: List of (proposal_id, msg) tuples to accept.
                Each proposal_id is e.g., "2a", and msg is an optional message.
            cl_name: Optional CL name. Defaults to current branch name.
            project_file: Optional path to project file. If not provided,
                will try to infer from workspace_name command.
            mark_ready_to_mail: If True, also reject remaining proposals and add
                READY TO MAIL suffix to STATUS, all in the same atomic write
                with the commit entry renumbering.
            skip_amend: If True, skip the checkout/apply/amend steps and only
                perform bookkeeping (renumber commit entries, etc.).
        """
        self._proposals = proposals
        self._cl_name = cl_name
        self._project_file = project_file
        self._mark_ready_to_mail = mark_ready_to_mail
        self._skip_amend = skip_amend
        self._conflict_result: ConflictCheckResult | None = None

    @property
    def name(self) -> str:
        return "accept"

    @property
    def description(self) -> str:
        return "Accept one or more proposed COMMITS entries"

    @property
    def conflict_result(self) -> ConflictCheckResult | None:
        """Return the conflict check result if one was performed."""
        return self._conflict_result

    def run(self) -> bool:
        """Run the accept workflow.

        Returns:
            True if the workflow completed successfully, False otherwise.
        """
        # Get CL name
        cl_name = self._cl_name or get_cl_name_from_branch()
        if not cl_name:
            print_status(
                "No CL name provided and not on a branch. "
                "Use 'gai cl accept <proposals> --cl <cl_name>' to specify.",
                "error",
            )
            return False

        # Get project file - prefer explicit path over workspace inference
        project: str | None
        if self._project_file:
            project_file = os.path.expanduser(self._project_file)
            # Extract project name from path (e.g., ~/.gai/projects/foo/foo.gp -> foo)
            project = os.path.basename(os.path.dirname(project_file))
        else:
            project = get_project_from_workspace()
            if not project:
                print_status(
                    "Failed to get project name from 'workspace_name' command.",
                    "error",
                )
                return False
            project_file = get_project_file_path(project)

        if not os.path.isfile(project_file):
            print_status(f"Project file not found: {project_file}", "error")
            return False

        # Get the ChangeSpec upfront for validation
        changespec = get_changespec_from_file(project_file, cl_name)
        if not changespec:
            print_status(f"ChangeSpec not found: {cl_name}", "error")
            return False

        # Validate ALL proposals upfront before making any changes
        validated_proposals: list[tuple[int, str, str | None, CommitEntry]] = []
        for proposal_id, msg in self._proposals:
            parsed = parse_proposal_id(proposal_id)
            if not parsed:
                print_status(
                    f"Invalid proposal ID: {proposal_id}. "
                    "Expected format like '2a', '2b'.",
                    "error",
                )
                return False
            base_num, letter = parsed

            # Validate proposal exists and has diff
            entry = find_proposal_entry(changespec.commits, base_num, letter)
            if not entry:
                print_status(
                    f"Proposal ({base_num}{letter}) not found in COMMITS.", "error"
                )
                return False
            if not self._skip_amend and not entry.diff:
                print_status(
                    f"Proposal ({base_num}{letter}) has no DIFF path.", "error"
                )
                return False

            validated_proposals.append((base_num, letter, msg, entry))

        if self._skip_amend:
            # Skip checkout/apply/amend — just build the accepted list directly
            accepted_proposals = [
                (bn, letter) for bn, letter, _, _ in validated_proposals
            ]
            extra_msgs = [msg for _, _, msg, _ in validated_proposals]
        else:
            # Full workflow: claim workspace, checkout, apply diffs, amend
            amend_result = self._run_amend_workflow(
                validated_proposals, project_file, project, cl_name, changespec
            )
            if amend_result[0] is None:
                return False
            accepted_proposals, extra_msgs = amend_result

        bookkeeping_suffix = " (bookkeeping only)" if self._skip_amend else ""

        # Renumber commit entries once for all accepted proposals
        # If mark_ready_to_mail is True, this also rejects remaining proposals
        # and adds READY TO MAIL suffix in the same atomic write
        if self._mark_ready_to_mail:
            print_status(
                f"Renumbering COMMITS entries and marking ready to mail{bookkeeping_suffix}...",
                "progress",
            )
        else:
            print_status(
                f"Renumbering COMMITS entries{bookkeeping_suffix}...", "progress"
            )
        if renumber_commit_entries(
            project_file,
            cl_name,
            accepted_proposals,
            extra_msgs,
            mark_ready_to_mail=self._mark_ready_to_mail,
        ):
            if self._mark_ready_to_mail:
                print_status(
                    "COMMITS entries renumbered and marked ready to mail.",
                    "success",
                )
            else:
                print_status("COMMITS entries renumbered successfully.", "success")
        else:
            print_status("Failed to renumber COMMITS entries.", "warning")

        # Add any new test target hooks from changed_test_targets
        add_test_hooks_if_available(project_file, cl_name)

        # Release axe(hooks)-* workspaces for accepted proposals
        # The proposals are now renumbered to regular entries, so the old
        # axe(hooks)-<proposal_id> workspace claims are stale
        for base_num, letter in accepted_proposals:
            old_workflow = f"axe(hooks)-{base_num}{letter}"
            for claim in get_claimed_workspaces(project_file):
                if claim.cl_name == cl_name and claim.workflow == old_workflow:
                    release_workspace(
                        project_file, claim.workspace_num, old_workflow, cl_name
                    )
                    print_status(
                        f"Released workspace #{claim.workspace_num}", "progress"
                    )

        # Build summary message
        if len(accepted_proposals) == 1:
            base_num, letter = accepted_proposals[0]
            print_status(
                f"Successfully accepted proposal ({base_num}{letter}){bookkeeping_suffix}!",
                "success",
            )
        else:
            ids = ", ".join(f"({num}{ltr})" for num, ltr in accepted_proposals)
            print_status(
                f"Successfully accepted proposals {ids}{bookkeeping_suffix}!",
                "success",
            )

        return True

    def _run_amend_workflow(
        self,
        validated_proposals: list[tuple[int, str, str | None, CommitEntry]],
        project_file: str,
        project: str | None,
        cl_name: str,
        changespec: ChangeSpec,
    ) -> tuple[list[tuple[int, str]], list[str | None]] | tuple[None, None]:
        """Run the workspace checkout/apply/amend steps.

        Returns:
            ``(accepted_proposals, extra_msgs)`` on success, or
            ``(None, None)`` on failure.
        """
        # Claim an available workspace
        assert project is not None
        workspace_num = get_first_available_axe_workspace(project_file)
        workspace_dir, workspace_suffix = get_workspace_directory_for_num(
            workspace_num, project
        )

        # Claim the workspace
        claim_success = claim_workspace(
            project_file,
            workspace_num,
            "accept",
            os.getpid(),
            cl_name,
        )
        if not claim_success:
            print_status("Error: Failed to claim workspace", "error")
            return None, None

        if workspace_suffix:
            print_status(f"Using workspace share: {workspace_suffix}", "progress")

        # Save original directory
        original_dir = os.getcwd()

        try:
            # Change to workspace directory
            os.chdir(workspace_dir)
            print_status(f"Changed to workspace: {workspace_dir}", "progress")

            # Clean workspace before switching branches
            clean_success, clean_error = run_bb_hg_clean(
                workspace_dir, f"{cl_name}-accept"
            )
            if not clean_success:
                print_status(f"Warning: bb_hg_clean failed: {clean_error}", "warning")

            # Update to the changespec branch
            print_status(f"Updating to branch: {cl_name}", "progress")
            success, error_msg = update_to_changespec(
                changespec, revision=cl_name, workspace_dir=workspace_dir
            )
            if not success:
                print_status(f"Failed to update to branch: {error_msg}", "error")
                return None, None

            # Run conflict check for 2+ proposals (single proposal can't conflict)
            if len(validated_proposals) >= 2:
                self._conflict_result = run_conflict_check(
                    workspace_dir, validated_proposals
                )
                if not self._conflict_result.success:
                    return None, None

            # Process each proposal in order
            accepted_proposals: list[tuple[int, str]] = []
            extra_msgs: list[str | None] = []

            total_proposals = len(validated_proposals)
            for idx, (base_num, letter, msg, entry) in enumerate(validated_proposals):
                # Apply the diff (entry.diff was validated to be non-None above)
                assert entry.diff is not None
                print_status(
                    f"Applying proposal ({base_num}{letter}): {entry.note}",
                    "progress",
                )
                success, error_msg = apply_diff_to_workspace(
                    workspace_dir,
                    entry.diff,
                )
                if not success:
                    print_status(
                        f"Failed to apply proposal ({base_num}{letter}): {error_msg}",
                        "error",
                    )
                    clean_workspace(workspace_dir)
                    return None, None

                print_status(f"Applied proposal ({base_num}{letter}).", "success")

                # Build amend message
                if msg:
                    amend_note = f"{entry.note} - {msg}"
                else:
                    amend_note = entry.note

                # Amend the commit
                # Use --no-upload for all but the last proposal to avoid unnecessary
                # uploads when accepting multiple proposals
                is_last = idx == total_proposals - 1
                if is_last:
                    print_status("Amending commit...", "progress")
                else:
                    print_status("Amending commit (skipping upload)...", "progress")

                provider = get_vcs_provider(workspace_dir)
                amend_ok, amend_err = provider.amend(
                    amend_note, workspace_dir, no_upload=not is_last
                )
                if not amend_ok:
                    print_status(f"bb_hg_amend failed: {amend_err}", "error")
                    clean_workspace(workspace_dir)
                    return None, None

                accepted_proposals.append((base_num, letter))
                extra_msgs.append(msg)

            return accepted_proposals, extra_msgs

        finally:
            # Always restore original directory and release workspace
            os.chdir(original_dir)
            release_workspace(project_file, workspace_num, "accept", cl_name)


def main() -> NoReturn:
    """Main entry point for the accept workflow (standalone execution)."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Accept one or more proposed COMMITS entries by applying their diffs."
    )
    parser.add_argument(
        "proposals",
        nargs="+",
        help="Proposal entries to accept. Format: <id>[(<msg>)]. "
        "Examples: '2a', '2b(Add foobar field)'.",
    )
    parser.add_argument(
        "--cl",
        dest="cl_name",
        help="CL name (defaults to current branch name).",
    )

    args = parser.parse_args()

    entries = parse_proposal_entries(args.proposals)
    if entries is None:
        print_status("Invalid proposal entry format", "error")
        sys.exit(1)

    workflow = AcceptWorkflow(
        proposals=entries,
        cl_name=args.cl_name,
    )
    success = workflow.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
