"""Core ChangeSpec operations for updating, extracting, and validating."""

import os
import re
import subprocess
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from status_state_machine import remove_workspace_suffix, transition_changespec_status

from .changespec import ChangeSpec, find_all_changespecs


def _get_workspace_suffix(status: str) -> str | None:
    """Extract workspace share suffix from a status value.

    Args:
        status: STATUS value, possibly with workspace suffix (e.g., "Creating EZ CL... (fig_3)")

    Returns:
        Workspace suffix (e.g., "fig_3") or None if no suffix present
    """
    # Match pattern: " (<project>_<N>)" at the end of the status
    match = re.search(r" \(([a-zA-Z0-9_-]+_\d+)\)$", status)
    if match:
        return match.group(1)
    return None


def _is_in_progress_status(status: str) -> bool:
    """Check if a status represents an in-progress state.

    In-progress statuses are those ending with "..." (after removing workspace suffix).

    Args:
        status: STATUS value to check

    Returns:
        True if status is in-progress, False otherwise
    """
    # Remove workspace suffix first, then check if it ends with "..."
    base_status = remove_workspace_suffix(status)
    return base_status.endswith("...")


def get_workspace_directory(
    changespec: ChangeSpec, all_changespecs: list[ChangeSpec]
) -> tuple[str, str | None]:
    """Determine which workspace directory to use for a ChangeSpec.

    Logic:
    1. If NO ChangeSpec has in-progress status → use main workspace
    2. If a ChangeSpec has in-progress status without suffix → main workspace is in use
    3. Find lowest N (2-100) where no ChangeSpec has suffix (<project>_<N>)

    Args:
        changespec: The ChangeSpec to determine workspace for
        all_changespecs: All ChangeSpecs across all projects

    Returns:
        Tuple of (workspace_directory, workspace_suffix)
        - workspace_directory: Full path to workspace directory
        - workspace_suffix: Suffix like "fig_3" or None for main workspace
    """
    # Extract project basename from file path
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Get required environment variables
    goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
    goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")

    if not goog_cloud_dir or not goog_src_dir_base:
        # Fall back to main workspace if env vars not set
        main_dir = os.path.join(
            goog_cloud_dir or "", project_basename, goog_src_dir_base or ""
        )
        return (main_dir, None)

    # Filter changespecs for the same project
    project_changespecs = [
        cs
        for cs in all_changespecs
        if os.path.splitext(os.path.basename(cs.file_path))[0] == project_basename
    ]

    # Find all in-progress changespecs with their workspace suffixes
    in_progress_workspaces: set[str | None] = set()
    for cs in project_changespecs:
        if _is_in_progress_status(cs.status):
            suffix = _get_workspace_suffix(cs.status)
            in_progress_workspaces.add(suffix)

    # Case 1: No in-progress changespecs → use main workspace
    if not in_progress_workspaces:
        main_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)
        return (main_dir, None)

    # Case 2: Main workspace is available (no None in the set)
    if None not in in_progress_workspaces:
        main_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)
        return (main_dir, None)

    # Case 3: Main workspace is in use, find available workspace share
    # Check N from 2 to 100
    for n in range(2, 101):
        workspace_suffix = f"{project_basename}_{n}"
        if workspace_suffix not in in_progress_workspaces:
            # Check if this workspace directory exists
            workspace_dir = os.path.join(
                goog_cloud_dir, workspace_suffix, goog_src_dir_base
            )
            if os.path.exists(workspace_dir) and os.path.isdir(workspace_dir):
                return (workspace_dir, workspace_suffix)

    # No available workspace found - fall back to main workspace
    # (this shouldn't happen in normal usage, but provides a safe fallback)
    main_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)
    return (main_dir, None)


def get_available_workflows(changespec: ChangeSpec) -> list[str]:
    """Get all available workflows for this ChangeSpec.

    Returns a list of workflow names that are applicable for this ChangeSpec based on:
    - STATUS = "Unstarted" + has TEST TARGETS - Runs new-failing-tests workflow
    - STATUS = "Unstarted" + no TEST TARGETS - Runs new-ez-feature workflow
    - STATUS = "TDD CL Created" - Runs new-tdd-feature workflow
    - STATUS = "Pre-Mailed" or "Mailed" - Runs qa workflow
    - At least one TEST TARGET marked with "(FAILED)" - Runs fix-tests workflow
    - STATUS = "Mailed" - Runs crs workflow

    Args:
        changespec: The ChangeSpec object to check

    Returns:
        List of workflow names (e.g., ["fix-tests", "crs"])
    """
    workflows = []

    # Check if any test target is marked as failed
    has_failed_tests = False
    if changespec.test_targets:
        for target in changespec.test_targets:
            if "(FAILED)" in target:
                has_failed_tests = True
                break

    # Check if ChangeSpec has test targets
    # If omitted, test_targets will be None (no TEST TARGETS field in ChangeSpec)
    # If present, test_targets will be a list of target strings
    has_test_targets = (
        changespec.test_targets is not None and len(changespec.test_targets) > 0
    )

    # Add workflows based on status
    if changespec.status == "Unstarted":
        if has_test_targets:
            workflows.append("new-failing-tests")
        else:
            workflows.append("new-ez-feature")
    elif changespec.status == "TDD CL Created":
        workflows.append("new-tdd-feature")
    elif changespec.status in ["Pre-Mailed", "Mailed"]:
        workflows.append("qa")
        if changespec.status == "Mailed":
            workflows.append("crs")

    # Add fix-tests workflow if there are failed tests
    # This should be added FIRST if applicable (except for explicit status workflows)
    if has_failed_tests and changespec.status not in [
        "Unstarted",
        "TDD CL Created",
    ]:
        workflows.insert(0, "fix-tests")

    return workflows


def extract_changespec_text(
    project_file: str, changespec_name: str, console: Console | None = None
) -> str | None:
    """Extract the full ChangeSpec text from a project file.

    Args:
        project_file: Path to the project file
        changespec_name: NAME of the ChangeSpec to extract
        console: Optional Rich Console object for error output

    Returns:
        The full ChangeSpec text, or None if not found
    """
    try:
        with open(project_file) as f:
            lines = f.readlines()

        in_target_changespec = False
        changespec_lines = []
        current_name = None
        consecutive_blank_lines = 0

        for i, line in enumerate(lines):
            # Check if this is a NAME field
            if line.startswith("NAME:"):
                # If we were already in the target changespec, we're done
                if in_target_changespec:
                    break

                current_name = line.split(":", 1)[1].strip()
                if current_name == changespec_name:
                    in_target_changespec = True
                    changespec_lines.append(line)
                    consecutive_blank_lines = 0
                continue

            # If we're in the target changespec, collect lines
            if in_target_changespec:
                # Check for end conditions
                if line.strip().startswith("##") and i > 0:
                    break
                if line.strip() == "":
                    consecutive_blank_lines += 1
                    if consecutive_blank_lines >= 2:
                        break
                else:
                    consecutive_blank_lines = 0

                changespec_lines.append(line)

        if changespec_lines:
            return "".join(changespec_lines).strip()
        return None
    except Exception as e:
        if console:
            console.print(f"[red]Error extracting ChangeSpec text: {e}[/red]")
        return None


def update_to_changespec(
    changespec: ChangeSpec,
    console: Console | None = None,
    revision: str | None = None,
    workspace_dir: str | None = None,
) -> tuple[bool, str | None]:
    """Update working directory to the specified ChangeSpec.

    This function:
    1. Changes to workspace directory (or $GOOG_CLOUD_DIR/<project>/$GOOG_SRC_DIR_BASE if not specified)
    2. Runs bb_hg_update <revision>

    Args:
        changespec: The ChangeSpec object to update to
        console: Optional Rich Console object for error output
        revision: Specific revision to update to. If None, uses parent or p4head.
                  Common values: changespec.name (for diff), changespec.parent (for workflow)
        workspace_dir: Optional workspace directory to use. If None, uses main workspace.

    Returns:
        Tuple of (success, error_message)
    """
    # Determine target directory
    if workspace_dir:
        target_dir = workspace_dir
    else:
        # Extract project basename from file path
        # e.g., /path/to/foobar.md -> foobar
        project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

        # Get required environment variables
        goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
        goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")

        if not goog_cloud_dir:
            return (False, "GOOG_CLOUD_DIR environment variable is not set")
        if not goog_src_dir_base:
            return (False, "GOOG_SRC_DIR_BASE environment variable is not set")

        # Build target directory path
        target_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)

    # Verify directory exists
    if not os.path.exists(target_dir):
        return (False, f"Target directory does not exist: {target_dir}")
    if not os.path.isdir(target_dir):
        return (False, f"Target path is not a directory: {target_dir}")

    # Determine which revision to update to
    if revision is not None:
        update_target = revision
    else:
        # Default: Use PARENT field if set, otherwise use p4head
        update_target = changespec.parent if changespec.parent else "p4head"

    # Run bb_hg_update command
    try:
        subprocess.run(
            ["bb_hg_update", update_target],
            cwd=target_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return (True, None)
    except subprocess.CalledProcessError as e:
        error_msg = f"bb_hg_update failed (exit code {e.returncode})"
        if e.stderr:
            error_msg += f": {e.stderr.strip()}"
        elif e.stdout:
            error_msg += f": {e.stdout.strip()}"
        return (False, error_msg)
    except FileNotFoundError:
        return (False, "bb_hg_update command not found")
    except Exception as e:
        return (False, f"Unexpected error running bb_hg_update: {str(e)}")


def unblock_child_changespecs(
    parent_changespec: ChangeSpec, console: Console | None = None
) -> int:
    """Unblock child ChangeSpecs when parent is moved to Pre-Mailed.

    When a ChangeSpec is moved to "Pre-Mailed", any ChangeSpecs that:
    - Have STATUS of "Blocked"
    - Have PARENT field equal to the NAME of the parent ChangeSpec

    Will automatically have their STATUS changed to "Unstarted".

    Args:
        parent_changespec: The ChangeSpec that was moved to Pre-Mailed
        console: Optional Rich Console for output

    Returns:
        Number of child ChangeSpecs that were unblocked
    """
    # Find all ChangeSpecs
    all_changespecs = find_all_changespecs()

    # Filter for blocked children of this parent
    blocked_children = [
        cs
        for cs in all_changespecs
        if cs.status == "Blocked" and cs.parent == parent_changespec.name
    ]

    if not blocked_children:
        return 0

    # Unblock each child
    unblocked_count = 0
    for child in blocked_children:
        # Update the status
        success, old_status, error_msg = transition_changespec_status(
            child.file_path,
            child.name,
            "Unstarted",
            validate=False,  # Don't validate - we know this transition is valid
        )

        if success:
            unblocked_count += 1
            if console:
                console.print(
                    f"[green]Unblocked child ChangeSpec '{child.name}': {old_status} → Unstarted[/green]"
                )
        else:
            if console:
                console.print(
                    f"[yellow]Warning: Failed to unblock '{child.name}': {error_msg}[/yellow]"
                )

    return unblocked_count
