"""Hook starting and workspace management for the axe scheduler."""

import os
import subprocess
import time
from collections.abc import Callable

from commit_utils import (
    apply_diff_to_workspace,
    clean_workspace,
    mark_proposal_broken,
    run_bb_hg_clean,
)
from running_field import (
    claim_workspace,
    get_claimed_workspaces,
    get_first_available_axe_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)

from ..changespec import (
    ChangeSpec,
    CommitEntry,
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
        proposal_workflow: The workflow name (e.g., "axe(hooks)-2a").

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
    """Release entry-specific workspaces (axe(hooks)-<id>) for this ChangeSpec.

    For proposal entries (e.g., axe(hooks)-3a), also cleans the workspace
    to remove uncommitted changes from `hg import --no-commit`.

    Args:
        changespec: The ChangeSpec to release workspaces for.
        log: Optional logging callback.
    """
    for claim in get_claimed_workspaces(changespec.file_path):
        if claim.cl_name == changespec.name and claim.workflow.startswith(
            "axe(hooks)-"
        ):
            # Extract entry_id from workflow name (e.g., "3" or "3a")
            entry_id = claim.workflow[len("axe(hooks)-") :]
            # Check if this is a proposal (entry_id contains a letter like "3a")
            is_proposal = any(c.isalpha() for c in entry_id)

            if is_proposal:
                # Clean workspace to remove uncommitted changes from hg import
                try:
                    workspace_dir, _ = get_workspace_directory_for_num(
                        claim.workspace_num, changespec.project_basename
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
    workflow = f"axe(hooks)-{entry_id}"

    for claim in get_claimed_workspaces(changespec.file_path):
        if claim.cl_name == changespec.name and claim.workflow == workflow:
            # Check if this is a proposal (entry_id contains a letter like "1a")
            is_proposal = any(c.isalpha() for c in entry_id)

            if is_proposal:
                # Clean workspace to remove uncommitted changes from hg import
                try:
                    workspace_dir, _ = get_workspace_directory_for_num(
                        claim.workspace_num, changespec.project_basename
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
                # Use ChangeSpec NAME if available, otherwise project basename
                identifier = changespec.name or changespec.project_basename
                log(
                    f"Released workspace #{claim.workspace_num} for entry"
                    f" {entry_id} ({identifier})",
                    "dim",
                )
            break


def start_stale_hooks(
    changespec: ChangeSpec,
    entry_id: str,
    entry: CommitEntry,
    log: LogCallback,
    *,
    skip_limited: bool = False,
) -> tuple[list[str], list[HookEntry], int]:
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
        entry: The CommitEntry object for this entry.
        log: Logging callback for status messages.
        skip_limited: If True, only start "unlimited" hooks (those with !-prefix,
            i.e., skip_fix_hook=True). Limited hooks are skipped. This allows
            !-prefixed hooks to bypass the --max-runners limit.

    Returns:
        Tuple of (update messages, list of started HookEntry objects, count of
        limited hooks started). The limited_count is used for runner limit tracking
        (unlimited hooks don't count toward the limit).
    """
    updates: list[str] = []
    started_hooks: list[HookEntry] = []

    if not changespec.hooks:
        return updates, started_hooks, 0

    # Don't run hooks for terminal statuses
    if changespec.status in ("Reverted", "Submitted"):
        return updates, started_hooks, 0

    # Check if this entry is a proposal
    is_proposal = entry.is_proposed

    if is_proposal:
        # For proposals, apply diff to workspace
        return _start_stale_hooks_for_proposal(
            changespec,
            entry_id,
            entry,
            changespec.project_basename,
            log,
            skip_limited=skip_limited,
        )
    else:
        # For regular entries, use shared workspace
        return _start_stale_hooks_shared_workspace(
            changespec,
            entry_id,
            changespec.project_basename,
            log,
            skip_limited=skip_limited,
        )


def _start_stale_hooks_for_proposal(
    changespec: ChangeSpec,
    entry_id: str,
    entry: CommitEntry,
    project_basename: str,
    log: LogCallback,
    *,
    skip_limited: bool = False,
) -> tuple[list[str], list[HookEntry], int]:
    """Start stale hooks for a proposal entry.

    All hooks for a proposal share one workspace. After bb_hg_update, the
    proposal's diff is applied before running hooks. Hooks prefixed with
    "$" are skipped for proposals.

    Args:
        changespec: The ChangeSpec to start hooks for.
        entry_id: The proposal HISTORY entry ID (e.g., "3a").
        entry: The CommitEntry (must be a proposal).
        project_basename: The project basename for workspace lookup.
        log: Logging callback for status messages.
        skip_limited: If True, only start "unlimited" hooks (those with !-prefix).

    Returns:
        Tuple of (update messages, list of started HookEntry objects, count of
        limited hooks started).
    """
    updates: list[str] = []
    started_hooks: list[HookEntry] = []
    limited_count = 0

    if not changespec.hooks:
        return updates, started_hooks, limited_count

    # Validate proposal has a diff
    if not entry.diff:
        log(
            f"Warning: Proposal ({entry_id}) has no DIFF path, "
            f"cannot run hooks for {changespec.name}",
            "yellow",
        )
        return updates, started_hooks, limited_count

    # Skip proposals already marked as broken
    if entry.suffix == "BROKEN PROPOSAL":
        log(
            f"Skipping broken proposal ({entry_id}) for {changespec.name}",
            "dim",
        )
        return updates, started_hooks, limited_count

    # Build proposal-specific workflow name (e.g., "axe(hooks)-3a")
    proposal_workflow = f"axe(hooks)-{entry_id}"

    # Check if we already have a workspace claimed for this proposal
    existing_workspace = _get_proposal_workspace(
        changespec.file_path, changespec.name, proposal_workflow
    )

    if existing_workspace is not None:
        workspace_num = existing_workspace
        newly_claimed = False
    else:
        # Claim a single workspace for ALL hooks of this proposal
        workspace_num = get_first_available_axe_workspace(changespec.file_path)
        newly_claimed = True

        if not claim_workspace(
            changespec.file_path,
            workspace_num,
            proposal_workflow,
            os.getpid(),
            changespec.name,
        ):
            log(
                f"[WS#{workspace_num}] Warning: Failed to claim workspace for proposal "
                f"{entry_id} on {changespec.name}",
                "yellow",
            )
            return updates, started_hooks, limited_count

    # Track whether we should release on error (only if we newly claimed)
    should_release_on_error = newly_claimed

    try:
        # Get workspace directory
        workspace_dir, _ = get_workspace_directory_for_num(
            workspace_num, project_basename
        )

        if not os.path.isdir(workspace_dir):
            log(
                f"[WS#{workspace_num}] Warning: Workspace directory not found: {workspace_dir}",
                "yellow",
            )
            if should_release_on_error:
                release_workspace(
                    changespec.file_path,
                    workspace_num,
                    proposal_workflow,
                    changespec.name,
                )
            return updates, started_hooks, limited_count

        # Run bb_hg_update and apply diff only if newly claimed
        if newly_claimed:
            # Clean workspace before switching branches
            clean_success, clean_error = run_bb_hg_clean(
                workspace_dir, f"{changespec.name}-hooks-proposal"
            )
            if not clean_success:
                log(
                    f"[WS#{workspace_num}] Warning: bb_hg_clean failed: {clean_error}",
                    "yellow",
                )

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
                        f"[WS#{workspace_num}] Warning: bb_hg_update failed for "
                        f"{changespec.name}: {error_output}",
                        "yellow",
                    )
                    release_workspace(
                        changespec.file_path,
                        workspace_num,
                        proposal_workflow,
                        changespec.name,
                    )
                    return updates, started_hooks, limited_count
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                log(
                    f"[WS#{workspace_num}] Warning: bb_hg_update error for "
                    f"{changespec.name}: {e}",
                    "yellow",
                )
                release_workspace(
                    changespec.file_path,
                    workspace_num,
                    proposal_workflow,
                    changespec.name,
                )
                return updates, started_hooks, limited_count

            # Apply the proposal diff (only if newly claimed)
            success, error_msg = apply_diff_to_workspace(workspace_dir, entry.diff)
            if not success:
                log(
                    f"[WS#{workspace_num}] Warning: Failed to apply proposal diff for "
                    f"{changespec.name}: {error_msg}",
                    "yellow",
                )
                # Mark proposal as broken so we don't retry
                mark_proposal_broken(
                    changespec.file_path,
                    changespec.name,
                    entry_id,
                )
                clean_workspace(workspace_dir)
                release_workspace(
                    changespec.file_path,
                    workspace_num,
                    proposal_workflow,
                    changespec.name,
                )
                return updates, started_hooks, limited_count

        # Start stale hooks in background
        for hook in changespec.hooks:
            # Skip "$" prefixed hooks for proposals
            if hook.skip_proposal_runs:
                continue

            # Skip limited hooks if requested (only start unlimited/!-prefixed hooks)
            # This allows !-prefixed hooks to bypass the --max-runners limit
            if skip_limited and not hook.skip_fix_hook:
                continue

            # Only start hooks that need to run
            if not hook_needs_run(hook, entry_id):
                continue

            # Re-check for race condition (another process may have started this hook)
            status_line = hook.get_status_line_for_commit_entry(entry_id)
            if status_line is not None:
                continue

            # Sleep 1 second between hooks to ensure unique timestamps
            if started_hooks:
                time.sleep(1)

            # Start the hook in background
            updated_hook, _ = start_hook_background(
                changespec, hook, workspace_dir, entry_id
            )
            started_hooks.append(updated_hook)

            # Track limited hooks separately for runner limit tracking
            if not hook.skip_fix_hook:
                limited_count += 1

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
            f"[WS#{workspace_num}] Warning: Error starting hooks for proposal: {e}",
            "yellow",
        )
        if should_release_on_error:
            release_workspace(
                changespec.file_path,
                workspace_num,
                proposal_workflow,
                changespec.name,
            )

    return updates, started_hooks, limited_count


def _start_stale_hooks_shared_workspace(
    changespec: ChangeSpec,
    entry_id: str,
    project_basename: str,
    log: LogCallback,
    *,
    skip_limited: bool = False,
) -> tuple[list[str], list[HookEntry], int]:
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
        skip_limited: If True, only start "unlimited" hooks (those with !-prefix).

    Returns:
        Tuple of (update messages, list of started HookEntry objects, count of
        limited hooks started).
    """
    updates: list[str] = []
    started_hooks: list[HookEntry] = []
    limited_count = 0

    if not changespec.hooks:
        return updates, started_hooks, limited_count

    # Build entry-specific workflow name (e.g., "axe(hooks)-3")
    entry_workflow = f"axe(hooks)-{entry_id}"

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
        workspace_num = get_first_available_axe_workspace(changespec.file_path)
        newly_claimed = True

        if not claim_workspace(
            changespec.file_path,
            workspace_num,
            entry_workflow,
            os.getpid(),
            changespec.name,
        ):
            log(
                f"[WS#{workspace_num}] Warning: Failed to claim workspace for hooks on "
                f"{changespec.name}",
                "yellow",
            )
            return updates, started_hooks, limited_count

    # Track whether we should release on error (only if we newly claimed)
    should_release_on_error = newly_claimed

    try:
        # Get workspace directory
        workspace_dir, _ = get_workspace_directory_for_num(
            workspace_num, project_basename
        )

        if not os.path.isdir(workspace_dir):
            log(
                f"[WS#{workspace_num}] Warning: Workspace directory not found: {workspace_dir}",
                "yellow",
            )
            if should_release_on_error:
                release_workspace(
                    changespec.file_path,
                    workspace_num,
                    entry_workflow,
                    changespec.name,
                )
            return updates, started_hooks, limited_count

        # Clean workspace before switching branches
        clean_success, clean_error = run_bb_hg_clean(
            workspace_dir, f"{changespec.name}-hooks-shared"
        )
        if not clean_success:
            log(
                f"[WS#{workspace_num}] Warning: bb_hg_clean failed: {clean_error}",
                "yellow",
            )

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
                    f"[WS#{workspace_num}] Warning: bb_hg_update failed for "
                    f"{changespec.name}: {error_output}",
                    "yellow",
                )
                if should_release_on_error:
                    release_workspace(
                        changespec.file_path,
                        workspace_num,
                        entry_workflow,
                        changespec.name,
                    )
                return updates, started_hooks, limited_count
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            msg = (
                "timed out"
                if isinstance(e, subprocess.TimeoutExpired)
                else "command not found"
            )
            log(
                f"[WS#{workspace_num}] Warning: bb_hg_update {msg} for {changespec.name}",
                "yellow",
            )
            if should_release_on_error:
                release_workspace(
                    changespec.file_path,
                    workspace_num,
                    entry_workflow,
                    changespec.name,
                )
            return updates, started_hooks, limited_count

        # Start stale hooks in background
        for hook in changespec.hooks:
            # Skip limited hooks if requested (only start unlimited/!-prefixed hooks)
            # This allows !-prefixed hooks to bypass the --max-runners limit
            if skip_limited and not hook.skip_fix_hook:
                continue

            # Only start hooks that need to run
            if not hook_needs_run(hook, entry_id):
                continue

            # Re-check for race condition (another process may have started this hook)
            status_line = hook.get_status_line_for_commit_entry(entry_id)
            if status_line is not None:
                continue

            # Sleep 1 second between hooks to ensure unique timestamps
            if started_hooks:
                time.sleep(1)

            # Start the hook in background
            updated_hook, _ = start_hook_background(
                changespec, hook, workspace_dir, entry_id
            )
            started_hooks.append(updated_hook)

            # Track limited hooks separately for runner limit tracking
            if not hook.skip_fix_hook:
                limited_count += 1

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

    return updates, started_hooks, limited_count
