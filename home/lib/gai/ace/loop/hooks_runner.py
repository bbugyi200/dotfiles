"""Hook starting and workspace management for the loop workflow."""

import os
import subprocess
import time
from collections.abc import Callable

from history_utils import apply_diff_to_workspace, clean_workspace, run_bb_hg_clean
from running_field import (
    claim_workspace,
    get_claimed_workspaces,
    get_first_available_loop_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)

from ..changespec import (
    ChangeSpec,
    HistoryEntry,
    HookEntry,
)
from ..hooks import (
    hook_needs_run,
    start_hook_background,
)

# Type alias for logging callback
LogCallback = Callable[[str, str | None], None]


def _get_proposal_workspace(
    project_file: str, cl_name: str, proposal_workflow: str
) -> int | None:
    """Get workspace number claimed for a proposal's hooks, or None.

    Args:
        project_file: Path to the project file.
        cl_name: Name of the ChangeSpec.
        proposal_workflow: The workflow name (e.g., "loop(hooks)-2a").

    Returns:
        The workspace number if found, None otherwise.
    """
    for claim in get_claimed_workspaces(project_file):
        if claim.cl_name == cl_name and claim.workflow == proposal_workflow:
            return claim.workspace_num
    return None


def release_entry_workspaces(
    changespec: ChangeSpec, log: LogCallback | None = None
) -> None:
    """Release entry-specific workspaces (loop(hooks)-<id>) for this ChangeSpec.

    For proposal entries (e.g., loop(hooks)-3a), also cleans the workspace
    to remove uncommitted changes from `hg import --no-commit`.

    Args:
        changespec: The ChangeSpec to release workspaces for.
        log: Optional logging callback.
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


def release_entry_workspace(
    changespec: ChangeSpec, entry_id: str, log: LogCallback | None = None
) -> None:
    """Release the workspace for a specific entry ID (e.g., '1', '1a', '2').

    For proposal entries (entry_id contains a letter like "1a"), also cleans the
    workspace to remove uncommitted changes from `hg import --no-commit`.

    Args:
        changespec: The ChangeSpec to release workspaces for.
        entry_id: The history entry ID (e.g., "1", "1a", "2").
        log: Optional logging callback.
    """
    workflow = f"loop(hooks)-{entry_id}"
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    for claim in get_claimed_workspaces(changespec.file_path):
        if claim.cl_name == changespec.name and claim.workflow == workflow:
            # Check if this is a proposal (entry_id contains a letter like "1a")
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
                workflow,
                changespec.name,
            )
            if log:
                log(
                    f"Released workspace #{claim.workspace_num} for entry {entry_id}",
                    "dim",
                )
            break


def start_stale_hooks(
    changespec: ChangeSpec,
    entry_id: str,
    entry: HistoryEntry,
    log: LogCallback,
) -> tuple[list[str], list[HookEntry]]:
    """Start stale hooks in background for a specific history entry.

    For regular history entries:
        Claims a workspace >= 100 for this ChangeSpec if not already claimed,
        runs bb_hg_update, and starts hooks. The workspace remains claimed while
        hooks are running and will be released by _check_hooks when all hooks
        complete (passed/failed/zombie).

    For proposal entries:
        All hooks for a proposal share one workspace. After bb_hg_update, the
        proposal's diff is applied before running hooks.

    Args:
        changespec: The ChangeSpec to start hooks for.
        entry_id: The specific HISTORY entry ID to run hooks for (e.g., "3", "3a").
        entry: The HistoryEntry object for this entry.
        log: Logging callback for status messages.

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

    # Check if this entry is a proposal
    is_proposal = entry.is_proposed

    if is_proposal:
        # For proposals, apply diff to workspace
        return _start_stale_hooks_for_proposal(
            changespec, entry_id, entry, project_basename, log
        )
    else:
        # For regular entries, use shared workspace
        return _start_stale_hooks_shared_workspace(
            changespec, entry_id, project_basename, log
        )


def _start_stale_hooks_for_proposal(
    changespec: ChangeSpec,
    entry_id: str,
    entry: HistoryEntry,
    project_basename: str,
    log: LogCallback,
) -> tuple[list[str], list[HookEntry]]:
    """Start stale hooks for a proposal entry.

    All hooks for a proposal share one workspace. After bb_hg_update, the
    proposal's diff is applied before running hooks. Hooks prefixed with
    "$" are skipped for proposals.

    Args:
        changespec: The ChangeSpec to start hooks for.
        entry_id: The proposal HISTORY entry ID (e.g., "3a").
        entry: The HistoryEntry (must be a proposal).
        project_basename: The project basename for workspace lookup.
        log: Logging callback for status messages.

    Returns:
        Tuple of (update messages, list of started HookEntry objects).
    """
    updates: list[str] = []
    started_hooks: list[HookEntry] = []

    if not changespec.hooks:
        return updates, started_hooks

    # Validate proposal has a diff
    if not entry.diff:
        log(
            f"Warning: Proposal ({entry_id}) has no DIFF path, "
            f"cannot run hooks for {changespec.name}",
            "yellow",
        )
        return updates, started_hooks

    # Build proposal-specific workflow name (e.g., "loop(hooks)-3a")
    proposal_workflow = f"loop(hooks)-{entry_id}"

    # Check if we already have a workspace claimed for this proposal
    existing_workspace = _get_proposal_workspace(
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
            log(
                f"Warning: Failed to claim workspace for proposal "
                f"{entry_id} on {changespec.name}",
                "yellow",
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
            log(
                f"Warning: Workspace directory not found: {workspace_dir}",
                "yellow",
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
            # Clean workspace before switching branches
            clean_success, clean_error = run_bb_hg_clean(
                workspace_dir, f"{changespec.name}-hooks-proposal"
            )
            if not clean_success:
                log(f"Warning: bb_hg_clean failed: {clean_error}", "yellow")

            try:
                result = subprocess.run(
                    ["bb_hg_update", changespec.name],
                    cwd=workspace_dir,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode != 0:
                    error_output = (
                        result.stderr.strip()
                        or result.stdout.strip()
                        or "no error output"
                    )
                    log(
                        f"Warning: bb_hg_update failed for {changespec.name} "
                        f"(cwd: {workspace_dir}): {error_output}",
                        "yellow",
                    )
                    release_workspace(
                        changespec.file_path,
                        workspace_num,
                        proposal_workflow,
                        changespec.name,
                    )
                    return updates, started_hooks
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                log(
                    f"Warning: bb_hg_update error for {changespec.name} "
                    f"(cwd: {workspace_dir}): {e}",
                    "yellow",
                )
                release_workspace(
                    changespec.file_path,
                    workspace_num,
                    proposal_workflow,
                    changespec.name,
                )
                return updates, started_hooks

            # Apply the proposal diff (only if newly claimed)
            success, error_msg = apply_diff_to_workspace(workspace_dir, entry.diff)
            if not success:
                log(
                    f"Warning: Failed to apply proposal diff for {changespec.name}: "
                    f"{error_msg}",
                    "yellow",
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
            # Skip "$" prefixed hooks for proposals
            if hook.skip_proposal_runs:
                continue

            # Only start hooks that need to run
            if not hook_needs_run(hook, entry_id):
                continue

            # Extra safeguard: don't start if already has a RUNNING status
            if hook.status == "RUNNING":
                continue

            # Sleep 1 second between hooks to ensure unique timestamps
            if started_hooks:
                time.sleep(1)

            # Start the hook in background
            updated_hook, _ = start_hook_background(
                changespec, hook, workspace_dir, entry_id
            )
            started_hooks.append(updated_hook)

            updates.append(
                f"Hook '{hook.command}' -> RUNNING (started for proposal {entry_id})"
            )

        # If no hooks were started, release the workspace
        # (whether newly claimed or previously claimed - if all hooks are done, release)
        if not started_hooks:
            clean_workspace(workspace_dir)
            release_workspace(
                changespec.file_path,
                workspace_num,
                proposal_workflow,
                changespec.name,
            )

        # NOTE: Workspace is NOT released here when hooks ARE started.
        # It will be released by _check_hooks when all hooks complete.

    except Exception as e:
        log(
            f"Warning: Error starting hooks for proposal: {e}",
            "yellow",
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
    changespec: ChangeSpec,
    entry_id: str,
    project_basename: str,
    log: LogCallback,
) -> tuple[list[str], list[HookEntry]]:
    """Start stale hooks using a shared workspace (for regular entries).

    Claims a workspace >= 100 for this ChangeSpec's entry if not already
    claimed. Only reuses a workspace if it's for the SAME entry ID.
    The workspace remains claimed while hooks are running and will be
    released by _check_hooks when all hooks complete (passed/failed/zombie).

    Args:
        changespec: The ChangeSpec to start hooks for.
        entry_id: The HISTORY entry ID (e.g., "1", "2", "3").
        project_basename: The project basename for workspace lookup.
        log: Logging callback for status messages.

    Returns:
        Tuple of (update messages, list of started HookEntry objects).
    """
    updates: list[str] = []
    started_hooks: list[HookEntry] = []

    if not changespec.hooks:
        return updates, started_hooks

    # Build entry-specific workflow name (e.g., "loop(hooks)-3")
    entry_workflow = f"loop(hooks)-{entry_id}"

    # Check if we already have a workspace claimed for this SAME entry
    existing_workspace = _get_proposal_workspace(
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
            log(
                f"Warning: Failed to claim workspace for hooks on {changespec.name}",
                "yellow",
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
            log(
                f"Warning: Workspace directory not found: {workspace_dir}",
                "yellow",
            )
            if should_release_on_error:
                release_workspace(
                    changespec.file_path,
                    workspace_num,
                    entry_workflow,
                    changespec.name,
                )
            return updates, started_hooks

        # Clean workspace before switching branches
        clean_success, clean_error = run_bb_hg_clean(
            workspace_dir, f"{changespec.name}-hooks-shared"
        )
        if not clean_success:
            log(f"Warning: bb_hg_clean failed: {clean_error}", "yellow")

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
                error_output = (
                    result.stderr.strip() or result.stdout.strip() or "no error output"
                )
                log(
                    f"Warning: bb_hg_update failed for {changespec.name} "
                    f"(cwd: {workspace_dir}): {error_output}",
                    "yellow",
                )
                if should_release_on_error:
                    release_workspace(
                        changespec.file_path,
                        workspace_num,
                        entry_workflow,
                        changespec.name,
                    )
                return updates, started_hooks
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            msg = (
                "timed out"
                if isinstance(e, subprocess.TimeoutExpired)
                else "command not found"
            )
            log(
                f"Warning: bb_hg_update {msg} for {changespec.name} "
                f"(cwd: {workspace_dir})",
                "yellow",
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
            if not hook_needs_run(hook, entry_id):
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
                changespec, hook, workspace_dir, entry_id
            )
            started_hooks.append(updated_hook)

            updates.append(
                f"Hook '{hook.command}' -> RUNNING (started for entry {entry_id})"
            )

        # If no hooks were started, release the workspace
        # (whether newly claimed or previously claimed - if all hooks are done, release)
        if not started_hooks:
            release_workspace(
                changespec.file_path,
                workspace_num,
                entry_workflow,
                changespec.name,
            )

        # NOTE: Workspace is NOT released here when hooks ARE started.
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
