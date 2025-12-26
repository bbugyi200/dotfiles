"""Loop workflow for continuously checking ChangeSpec status updates."""

import os
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from running_field import (
    claim_workspace,
    get_claimed_workspaces,
    get_first_available_loop_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)
from status_state_machine import remove_workspace_suffix, transition_changespec_status

from .changespec import (
    ChangeSpec,
    HistoryEntry,
    HookEntry,
    HookStatusLine,
    find_all_changespecs,
)
from .cl_status import (
    SYNCABLE_STATUSES,
    has_pending_comments,
    is_cl_submitted,
    is_parent_submitted,
)
from .hooks import (
    check_hook_completion,
    get_last_history_entry,
    get_last_history_entry_id,
    has_running_hooks,
    hook_has_any_running_status,
    hook_needs_run,
    is_hook_zombie,
    start_hook_background,
    update_changespec_hooks_field,
)

# Import history utilities for proposal diff handling
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from history_utils import apply_diff_to_workspace, clean_workspace

from .sync_cache import clear_cache_entry, should_check, update_last_checked


class LoopWorkflow:
    """Continuously loops through all ChangeSpecs for status updates."""

    def __init__(
        self,
        interval_seconds: int = 300,
        verbose: bool = False,
        hook_interval_seconds: int = 10,
    ) -> None:
        """Initialize the loop workflow.

        Args:
            interval_seconds: Polling interval in seconds (default: 300 = 5 minutes)
            verbose: If True, show skipped ChangeSpecs in output (default: False)
            hook_interval_seconds: Hook check interval in seconds (default: 10)
        """
        self.interval_seconds = interval_seconds
        self.verbose = verbose
        self.hook_interval_seconds = hook_interval_seconds
        self.console = Console()

    def _is_leaf_cl(self, changespec: ChangeSpec) -> bool:
        """Check if a ChangeSpec is a leaf CL (no parent or parent is submitted).

        Leaf CLs are checked on the first cycle regardless of cache state.

        Args:
            changespec: The ChangeSpec to check.

        Returns:
            True if this is a leaf CL, False otherwise.
        """
        return is_parent_submitted(changespec)

    def _log(self, message: str, style: str | None = None) -> None:
        """Print a timestamped log message.

        Args:
            message: The message to print.
            style: Optional rich style to apply (e.g., "dim", "green", "yellow").
        """
        timestamp = datetime.now(ZoneInfo("America/New_York")).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        if style:
            self.console.print(f"[{style}][{timestamp}] {message}[/{style}]")
        else:
            self.console.print(f"[{timestamp}] {message}")

    def _should_check_status(
        self, changespec: ChangeSpec, bypass_cache: bool = False
    ) -> tuple[bool, str | None]:
        """Determine if a ChangeSpec's CL status should be checked.

        Args:
            changespec: The ChangeSpec to check.
            bypass_cache: If True, skip the cache check (used for first cycle).

        Returns:
            Tuple of (should_check, skip_reason). skip_reason is None if should_check.
        """
        base_status = remove_workspace_suffix(changespec.status)
        if base_status not in SYNCABLE_STATUSES:
            return False, f"status '{changespec.status}' not syncable"

        if not bypass_cache:
            if not should_check(changespec.name):
                return False, "recently checked"

        return True, None

    def _check_status(self, changespec: ChangeSpec) -> str | None:
        """Check CL submission and comment status for a ChangeSpec.

        Args:
            changespec: The ChangeSpec to check.

        Returns:
            Update message if status was updated, None otherwise.
        """
        # Update the last_checked timestamp
        update_last_checked(changespec.name)

        # Check if submitted (applies to both Mailed and Changes Requested)
        if is_parent_submitted(changespec) and is_cl_submitted(changespec):
            success, old_status, _ = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                "Submitted",
                validate=False,
            )

            if success:
                clear_cache_entry(changespec.name)
                return f"Status changed {old_status} -> Submitted"

        # If not submitted and status is "Mailed", check for comments
        if (
            changespec.status == "Mailed"
            and is_parent_submitted(changespec)
            and has_pending_comments(changespec)
        ):
            success, old_status, _ = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                "Changes Requested",
                validate=False,
            )

            if success:
                return f"Status changed {old_status} -> Changes Requested"

        # If status is "Changes Requested", check if comments have been cleared
        if changespec.status == "Changes Requested" and not has_pending_comments(
            changespec
        ):
            success, old_status, _ = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                "Mailed",
                validate=False,
            )

            if success:
                return f"Status changed {old_status} -> Mailed"

        return None

    def _should_check_hooks(
        self, changespec: ChangeSpec, bypass_cache: bool = False
    ) -> tuple[bool, str | None]:
        """Determine if a ChangeSpec's hooks should be checked.

        Unlike status checks, hooks run even for ChangeSpecs with children.
        Returns True if there are:
        - Stale hooks that need to be started
        - Running hooks that need completion checks
        - Zombie hooks that need to be marked

        Args:
            changespec: The ChangeSpec to check.
            bypass_cache: If True, skip the cache check (used for first cycle).

        Returns:
            Tuple of (should_check, skip_reason). skip_reason is None if should_check.
        """
        # Check if there are any hooks defined
        if not changespec.hooks:
            return False, "no hooks defined"

        # Get last HISTORY entry ID to compare against (e.g., "1", "1a")
        last_history_entry_id = get_last_history_entry_id(changespec)

        # Check if any hook needs action:
        # - Stale hooks need to be started
        # - Running hooks need completion checks (check ALL status lines, not just latest)
        # - Zombie hooks need to be marked
        has_stale_hooks = False
        has_hooks_running = False
        has_zombie_hooks = False
        for hook in changespec.hooks:
            if hook_needs_run(hook, last_history_entry_id):
                has_stale_hooks = True
            elif hook_has_any_running_status(hook):
                # Check ALL status lines for RUNNING, not just the latest
                if is_hook_zombie(hook):
                    has_zombie_hooks = True
                else:
                    has_hooks_running = True

        if not has_stale_hooks and not has_hooks_running and not has_zombie_hooks:
            return False, "all hooks up to date"

        # Check cache (unless bypassing)
        if not bypass_cache:
            cache_key = f"hooks:{changespec.name}"
            if not should_check(cache_key):
                return False, "recently checked"

        return True, None

    def _check_hooks(self, changespec: ChangeSpec) -> list[str]:
        """Check and run hooks for a ChangeSpec.

        This method handles hooks in two phases:
        1. Check completion status of any RUNNING hooks (no workspace needed)
        2. Start any stale hooks in background (needs workspace)

        Hooks run in the background and their completion is checked in subsequent
        cycles via the output file's exit code marker.

        Args:
            changespec: The ChangeSpec to check.

        Returns:
            List of update messages.
        """
        updates: list[str] = []

        # Don't run hooks for terminal statuses
        if changespec.status in ("Reverted", "Submitted"):
            return updates

        # Hooks should exist at this point since we checked in _should_check_hooks
        if not changespec.hooks:
            return updates

        # Get last HISTORY entry ID for comparison (e.g., "1", "1a")
        last_history_entry_id = get_last_history_entry_id(changespec)

        # Phase 1: Check completion status of RUNNING hooks (no workspace needed)
        updated_hooks: list[HookEntry] = []
        has_stale_hooks = False

        for hook in changespec.hooks:
            # Check if this hook is a zombie
            if is_hook_zombie(hook):
                # Mark the RUNNING status line as ZOMBIE
                if hook.status_lines:
                    updated_status_lines = []
                    for sl in hook.status_lines:
                        if sl.status == "RUNNING":
                            # Update RUNNING to ZOMBIE
                            updated_status_lines.append(
                                HookStatusLine(
                                    history_entry_num=sl.history_entry_num,
                                    timestamp=sl.timestamp,
                                    status="ZOMBIE",
                                    duration=sl.duration,
                                )
                            )
                        else:
                            updated_status_lines.append(sl)
                    zombie_hook = HookEntry(
                        command=hook.command,
                        status_lines=updated_status_lines,
                    )
                    updated_hooks.append(zombie_hook)
                    updates.append(f"Hook '{hook.command}' marked as ZOMBIE")
                else:
                    updated_hooks.append(hook)
                continue

            # Check if hook has any RUNNING status (not just the latest)
            # This catches RUNNING hooks from older history entries
            if hook_has_any_running_status(hook):
                # Check if it has completed
                completed_hook = check_hook_completion(changespec, hook)
                if completed_hook:
                    updated_hooks.append(completed_hook)
                    status_msg = completed_hook.status or "UNKNOWN"
                    duration_msg = (
                        f" ({completed_hook.duration})"
                        if completed_hook.duration
                        else ""
                    )
                    updates.append(
                        f"Hook '{hook.command}' -> {status_msg}{duration_msg}"
                    )
                else:
                    # Still running, keep as is
                    updated_hooks.append(hook)
                continue

            # Check if hook needs to run (no status line for current history entry)
            if hook_needs_run(hook, last_history_entry_id):
                has_stale_hooks = True
                # Add placeholder - will be replaced after starting
                updated_hooks.append(hook)
            else:
                # Hook is up to date, keep as is
                updated_hooks.append(hook)

        # Phase 2: Start stale hooks in background (needs workspace)
        if has_stale_hooks:
            stale_updates, stale_hooks = self._start_stale_hooks(
                changespec, last_history_entry_id
            )
            updates.extend(stale_updates)

            # Merge stale hooks into updated_hooks
            # Replace any stale hooks with their started versions
            if stale_hooks:
                stale_by_command = {h.command: h for h in stale_hooks}
                for i, hook in enumerate(updated_hooks):
                    if hook.command in stale_by_command:
                        updated_hooks[i] = stale_by_command[hook.command]

        # Update the HOOKS field in the file only if there were actual changes
        if updates:
            update_changespec_hooks_field(
                changespec.file_path,
                changespec.name,
                updated_hooks,
            )

        # Release workspace if all hooks have completed (no longer RUNNING)
        # All entry-specific workspaces (loop(hooks)-*) are released by this method
        if not has_running_hooks(updated_hooks):
            self._release_entry_workspaces(changespec)

        return updates

    def _run_hooks_cycle(self) -> int:
        """Run a hooks cycle - check completion and start new hooks.

        This runs on the frequent hook interval (default 10s).

        Returns:
            Number of hook state changes detected.
        """
        all_changespecs = find_all_changespecs()
        update_count = 0

        for changespec in all_changespecs:
            # Skip if no hooks
            if not changespec.hooks:
                continue

            updates = self._check_hooks(changespec)
            for update in updates:
                self._log(f"* {changespec.name}: {update}", style="green bold")
                update_count += 1

        return update_count

    def _start_stale_hooks(
        self, changespec: ChangeSpec, last_history_entry_id: str | None
    ) -> tuple[list[str], list[HookEntry]]:
        """Start stale hooks in background.

        For regular history entries:
            Claims a workspace >= 100 for this ChangeSpec if not already claimed,
            runs bb_hg_update, and starts hooks. The workspace remains claimed while
            hooks are running and will be released by _check_hooks when all hooks
            complete (passed/failed/zombie).

        For proposal entries:
            Each hook gets its own workspace. After bb_hg_update, the proposal's
            diff is applied before running the hook.

        Args:
            changespec: The ChangeSpec to start hooks for.
            last_history_entry_id: The last HISTORY entry ID (e.g., "1", "1a").

        Returns:
            Tuple of (update messages, list of started HookEntry objects).
        """
        updates: list[str] = []
        started_hooks: list[HookEntry] = []

        if not changespec.hooks:
            return updates, started_hooks

        # Don't run hooks for terminal statuses
        if changespec.status in ("Reverted", "Submitted"):
            return updates, started_hooks

        # Get project info
        project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

        # Check if the last history entry is a proposal
        last_entry = get_last_history_entry(changespec)
        is_proposal = last_entry is not None and last_entry.is_proposed

        if is_proposal and last_entry is not None:
            # For proposals, each hook gets its own workspace
            return self._start_stale_hooks_for_proposal(
                changespec, last_history_entry_id, last_entry, project_basename
            )
        else:
            # For regular entries, use shared workspace
            return self._start_stale_hooks_shared_workspace(
                changespec, last_history_entry_id, project_basename
            )

    def _get_proposal_workspace(
        self, project_file: str, cl_name: str, proposal_workflow: str
    ) -> int | None:
        """Get workspace number claimed for a proposal's hooks, or None."""
        for claim in get_claimed_workspaces(project_file):
            if claim.cl_name == cl_name and claim.workflow == proposal_workflow:
                return claim.workspace_num
        return None

    def _release_entry_workspaces(self, changespec: ChangeSpec) -> None:
        """Release entry-specific workspaces (loop(hooks)-<id>) for this ChangeSpec.

        For proposal entries (e.g., loop(hooks)-3a), also cleans the workspace
        to remove uncommitted changes from `hg import --no-commit`.
        """
        project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]
        for claim in get_claimed_workspaces(changespec.file_path):
            if claim.cl_name == changespec.name and claim.workflow.startswith(
                "loop(hooks)-"
            ):
                # Extract entry_id from workflow name (e.g., "3" or "3a")
                entry_id = claim.workflow[len("loop(hooks)-") :]
                # Check if this is a proposal (entry_id contains a letter like "3a")
                is_proposal = any(c.isalpha() for c in entry_id)

                if is_proposal:
                    # Clean workspace to remove uncommitted changes from hg import
                    try:
                        workspace_dir, _ = get_workspace_directory_for_num(
                            claim.workspace_num, project_basename
                        )
                        clean_workspace(workspace_dir)
                    except Exception:
                        pass

                release_workspace(
                    changespec.file_path,
                    claim.workspace_num,
                    claim.workflow,
                    changespec.name,
                )

    def _start_stale_hooks_for_proposal(
        self,
        changespec: ChangeSpec,
        last_history_entry_id: str | None,
        last_entry: HistoryEntry,
        project_basename: str,
    ) -> tuple[list[str], list[HookEntry]]:
        """Start stale hooks for a proposal entry.

        All hooks for a proposal share one workspace. After bb_hg_update, the
        proposal's diff is applied before running hooks. Hooks prefixed with
        "!" are skipped for proposals.

        Args:
            changespec: The ChangeSpec to start hooks for.
            last_history_entry_id: The last HISTORY entry ID (e.g., "1a").
            last_entry: The last HistoryEntry (must be a proposal).
            project_basename: The project basename for workspace lookup.

        Returns:
            Tuple of (update messages, list of started HookEntry objects).
        """
        updates: list[str] = []
        started_hooks: list[HookEntry] = []

        if not changespec.hooks:
            return updates, started_hooks

        # Validate proposal has a diff
        if not last_entry.diff:
            self._log(
                f"Warning: Proposal ({last_entry.display_number}) has no DIFF path, "
                f"cannot run hooks for {changespec.name}",
                style="yellow",
            )
            return updates, started_hooks

        # Build proposal-specific workflow name (e.g., "loop(hooks)-2a")
        proposal_id = last_entry.display_number
        proposal_workflow = f"loop(hooks)-{proposal_id}"

        # Check if we already have a workspace claimed for this proposal
        existing_workspace = self._get_proposal_workspace(
            changespec.file_path, changespec.name, proposal_workflow
        )

        if existing_workspace is not None:
            workspace_num = existing_workspace
            newly_claimed = False
        else:
            # Claim a single workspace for ALL hooks of this proposal
            workspace_num = get_first_available_loop_workspace(changespec.file_path)
            newly_claimed = True

            if not claim_workspace(
                changespec.file_path,
                workspace_num,
                proposal_workflow,
                changespec.name,
            ):
                self._log(
                    f"Warning: Failed to claim workspace for proposal "
                    f"{proposal_id} on {changespec.name}",
                    style="yellow",
                )
                return updates, started_hooks

        # Track whether we should release on error (only if we newly claimed)
        should_release_on_error = newly_claimed

        try:
            # Get workspace directory
            workspace_dir, _ = get_workspace_directory_for_num(
                workspace_num, project_basename
            )

            if not os.path.isdir(workspace_dir):
                self._log(
                    f"Warning: Workspace directory not found: {workspace_dir}",
                    style="yellow",
                )
                if should_release_on_error:
                    release_workspace(
                        changespec.file_path,
                        workspace_num,
                        proposal_workflow,
                        changespec.name,
                    )
                return updates, started_hooks

            # Run bb_hg_update and apply diff only if newly claimed
            if newly_claimed:
                try:
                    result = subprocess.run(
                        ["bb_hg_update", changespec.name],
                        cwd=workspace_dir,
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
                    if result.returncode != 0:
                        self._log(
                            f"Warning: bb_hg_update failed for {changespec.name}: "
                            f"{result.stderr.strip()}",
                            style="yellow",
                        )
                        release_workspace(
                            changespec.file_path,
                            workspace_num,
                            proposal_workflow,
                            changespec.name,
                        )
                        return updates, started_hooks
                except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                    self._log(
                        f"Warning: bb_hg_update error for {changespec.name}: {e}",
                        style="yellow",
                    )
                    release_workspace(
                        changespec.file_path,
                        workspace_num,
                        proposal_workflow,
                        changespec.name,
                    )
                    return updates, started_hooks

                # Apply the proposal diff (only if newly claimed)
                success, error_msg = apply_diff_to_workspace(
                    workspace_dir, last_entry.diff
                )
                if not success:
                    self._log(
                        f"Warning: Failed to apply proposal diff for {changespec.name}: "
                        f"{error_msg}",
                        style="yellow",
                    )
                    clean_workspace(workspace_dir)
                    release_workspace(
                        changespec.file_path,
                        workspace_num,
                        proposal_workflow,
                        changespec.name,
                    )
                    return updates, started_hooks

            # Start stale hooks in background
            for hook in changespec.hooks:
                # Skip "!" prefixed hooks for proposals
                if hook.command.startswith("!"):
                    continue

                # Only start hooks that need to run
                if not hook_needs_run(hook, last_history_entry_id):
                    continue

                # Extra safeguard: don't start if already has a RUNNING status
                if hook.status == "RUNNING":
                    continue

                # Sleep 1 second between hooks to ensure unique timestamps
                if started_hooks:
                    time.sleep(1)

                # Start the hook in background
                updated_hook, _ = start_hook_background(
                    changespec, hook, workspace_dir, last_history_entry_id or "1"
                )
                started_hooks.append(updated_hook)

                updates.append(
                    f"Hook '{hook.command}' -> RUNNING (started for proposal "
                    f"{proposal_id})"
                )

            # If we claimed a workspace but didn't start any hooks, release it
            if newly_claimed and not started_hooks:
                clean_workspace(workspace_dir)
                release_workspace(
                    changespec.file_path,
                    workspace_num,
                    proposal_workflow,
                    changespec.name,
                )

            # NOTE: Workspace is NOT released here when hooks are started.
            # It will be released by _check_hooks when all hooks complete.

        except Exception as e:
            self._log(
                f"Warning: Error starting hooks for proposal: {e}",
                style="yellow",
            )
            if should_release_on_error:
                release_workspace(
                    changespec.file_path,
                    workspace_num,
                    proposal_workflow,
                    changespec.name,
                )

        return updates, started_hooks

    def _start_stale_hooks_shared_workspace(
        self,
        changespec: ChangeSpec,
        last_history_entry_id: str | None,
        project_basename: str,
    ) -> tuple[list[str], list[HookEntry]]:
        """Start stale hooks using a shared workspace (for regular entries).

        Claims a workspace >= 100 for this ChangeSpec's entry if not already
        claimed. Only reuses a workspace if it's for the SAME entry ID.
        The workspace remains claimed while hooks are running and will be
        released by _check_hooks when all hooks complete (passed/failed/zombie).

        Args:
            changespec: The ChangeSpec to start hooks for.
            last_history_entry_id: The last HISTORY entry ID (e.g., "1", "2").
            project_basename: The project basename for workspace lookup.

        Returns:
            Tuple of (update messages, list of started HookEntry objects).
        """
        updates: list[str] = []
        started_hooks: list[HookEntry] = []

        if not changespec.hooks:
            return updates, started_hooks

        # Build entry-specific workflow name (e.g., "loop(hooks)-3")
        entry_id = last_history_entry_id if last_history_entry_id else "0"
        entry_workflow = f"loop(hooks)-{entry_id}"

        # Check if we already have a workspace claimed for this SAME entry
        existing_workspace = self._get_proposal_workspace(
            changespec.file_path, changespec.name, entry_workflow
        )

        if existing_workspace is not None:
            # Already have a workspace claimed for same entry - reuse it
            workspace_num = existing_workspace
            newly_claimed = False
        else:
            # Claim a new workspace >= 100
            workspace_num = get_first_available_loop_workspace(changespec.file_path)
            newly_claimed = True

            if not claim_workspace(
                changespec.file_path,
                workspace_num,
                entry_workflow,
                changespec.name,
            ):
                self._log(
                    f"Warning: Failed to claim workspace for hooks on {changespec.name}",
                    style="yellow",
                )
                return updates, started_hooks

        # Track whether we should release on error (only if we newly claimed)
        should_release_on_error = newly_claimed

        try:
            # Get workspace directory
            workspace_dir, _ = get_workspace_directory_for_num(
                workspace_num, project_basename
            )

            if not os.path.isdir(workspace_dir):
                self._log(
                    f"Warning: Workspace directory not found: {workspace_dir}",
                    style="yellow",
                )
                if should_release_on_error:
                    release_workspace(
                        changespec.file_path,
                        workspace_num,
                        entry_workflow,
                        changespec.name,
                    )
                return updates, started_hooks

            # Run bb_hg_update to switch to the ChangeSpec's branch
            try:
                result = subprocess.run(
                    ["bb_hg_update", changespec.name],
                    cwd=workspace_dir,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                )
                if result.returncode != 0:
                    self._log(
                        f"Warning: bb_hg_update failed for {changespec.name}: "
                        f"{result.stderr.strip()}",
                        style="yellow",
                    )
                    if should_release_on_error:
                        release_workspace(
                            changespec.file_path,
                            workspace_num,
                            entry_workflow,
                            changespec.name,
                        )
                    return updates, started_hooks
            except subprocess.TimeoutExpired:
                self._log(
                    f"Warning: bb_hg_update timed out for {changespec.name}",
                    style="yellow",
                )
                if should_release_on_error:
                    release_workspace(
                        changespec.file_path,
                        workspace_num,
                        entry_workflow,
                        changespec.name,
                    )
                return updates, started_hooks
            except FileNotFoundError:
                self._log(
                    "Warning: bb_hg_update command not found",
                    style="yellow",
                )
                if should_release_on_error:
                    release_workspace(
                        changespec.file_path,
                        workspace_num,
                        entry_workflow,
                        changespec.name,
                    )
                return updates, started_hooks

            # Start stale hooks in background
            for hook in changespec.hooks:
                # Only start hooks that need to run
                if not hook_needs_run(hook, last_history_entry_id):
                    continue

                # Extra safeguard: don't start if already has a RUNNING status
                # This prevents duplicate RUNNING status lines if there's a race
                if hook.status == "RUNNING":
                    continue

                # Sleep 1 second between hooks to ensure unique timestamps
                if started_hooks:
                    time.sleep(1)

                # Start the hook in background
                updated_hook, _ = start_hook_background(
                    changespec, hook, workspace_dir, last_history_entry_id or "1"
                )
                started_hooks.append(updated_hook)

                updates.append(
                    f"Hook '{hook.command}' -> RUNNING (started for entry {entry_id})"
                )

            # If we claimed a workspace but didn't start any hooks, release it
            if newly_claimed and not started_hooks:
                release_workspace(
                    changespec.file_path,
                    workspace_num,
                    entry_workflow,
                    changespec.name,
                )

            # NOTE: Workspace is NOT released here when hooks are started.
            # It will be released by _check_hooks when all hooks complete.

        except Exception:
            # Release workspace on unexpected errors if we newly claimed it
            if should_release_on_error:
                release_workspace(
                    changespec.file_path,
                    workspace_num,
                    entry_workflow,
                    changespec.name,
                )
            raise

        return updates, started_hooks

    def _check_single_changespec(
        self, changespec: ChangeSpec, bypass_cache: bool = False
    ) -> tuple[list[str], list[str], list[str]]:
        """Check a single ChangeSpec for updates.

        Args:
            changespec: The ChangeSpec to check.
            bypass_cache: If True, skip the cache check (used for first cycle leaf CLs).

        Returns:
            Tuple of (updates, checked_types, skip_reasons).
            - updates: List of update messages (e.g., "Status changed Mailed -> Submitted")
            - checked_types: List of what was checked (e.g., ["status"])
            - skip_reasons: List of skip reasons (e.g., ["status: not syncable"])
        """
        updates = []
        checked_types = []
        skip_reasons = []

        # Check status (submission/comments)
        should_check_stat, stat_skip_reason = self._should_check_status(
            changespec, bypass_cache
        )
        if should_check_stat:
            checked_types.append("status")
            status_update = self._check_status(changespec)
            if status_update:
                updates.append(status_update)
        elif stat_skip_reason:
            skip_reasons.append(f"status: {stat_skip_reason}")

        return updates, checked_types, skip_reasons

    def _run_check_cycle(self, first_cycle: bool = False) -> int:
        """Run one full check cycle across all ChangeSpecs (status only).

        Hooks are checked separately via _run_hooks_cycle at a faster interval.

        Args:
            first_cycle: If True, bypass cache for leaf CLs (CLs with no parent
                or submitted parents).

        Returns:
            Number of ChangeSpecs that were updated.
        """
        all_changespecs = find_all_changespecs()
        update_count = 0

        for changespec in all_changespecs:
            # On first cycle, bypass cache for leaf CLs
            bypass_cache = first_cycle and self._is_leaf_cl(changespec)

            # Run status checks (hooks handled separately)
            updates: list[str] = []

            should_check_stat, _ = self._should_check_status(changespec, bypass_cache)
            if should_check_stat:
                status_update = self._check_status(changespec)
                if status_update:
                    updates.append(status_update)

            for update in updates:
                self._log(f"* {changespec.name}: {update}", style="green bold")
                update_count += 1

        # Only show cycle complete message if there were updates
        if update_count > 0:
            self._log(f"Full cycle complete: {update_count} update(s)", style="green")

        return update_count

    def _count_projects(self, changespecs: list[ChangeSpec]) -> int:
        """Count unique projects from a list of ChangeSpecs.

        Args:
            changespecs: List of ChangeSpecs.

        Returns:
            Number of unique projects.
        """
        projects = set()
        for cs in changespecs:
            # Extract project name from file path
            project_basename = os.path.splitext(os.path.basename(cs.file_path))[0]
            projects.add(project_basename)
        return len(projects)

    def run(self) -> bool:
        """Run the continuous loop.

        Full checks (status, hooks) run at interval_seconds (default 5m).
        Hook status checks run at hook_interval_seconds (default 10s).

        Returns:
            True if exited normally, False on error.
        """
        # Print startup info
        interval_str = (
            f"{self.interval_seconds // 60} minutes"
            if self.interval_seconds >= 60
            else f"{self.interval_seconds} seconds"
        )
        hook_interval_str = (
            f"{self.hook_interval_seconds // 60} minutes"
            if self.hook_interval_seconds >= 60
            else f"{self.hook_interval_seconds} seconds"
        )
        self._log(
            f"GAI Loop started - full checks every {interval_str}, "
            f"hook checks every {hook_interval_str} (Ctrl+C to exit)"
        )

        # Count initial changespecs
        initial_changespecs = find_all_changespecs()
        project_count = self._count_projects(initial_changespecs)
        self._log(
            f"Looping through {len(initial_changespecs)} ChangeSpecs "
            f"across {project_count} project(s)"
        )

        try:
            first_cycle = True
            while True:
                self._run_check_cycle(first_cycle=first_cycle)
                first_cycle = False

                # Between full cycles, run frequent hooks checks
                elapsed = 0
                while elapsed < self.interval_seconds:
                    time.sleep(self.hook_interval_seconds)
                    elapsed += self.hook_interval_seconds

                    # Check if we've reached the next full cycle
                    if elapsed >= self.interval_seconds:
                        break

                    # Run hooks cycle (check completion and start new hooks)
                    self._run_hooks_cycle()

        except KeyboardInterrupt:
            self._log("Loop stopped by user")
            return True
