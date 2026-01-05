"""
RUNNING field management for tracking active workflows and workspace claims.

The RUNNING field in ProjectSpec files tracks which workspace directories
are currently in use by gai workflows. Format:

RUNNING:
  #1 | fix-tests | my_feature
  #3 | crs | other_feature

Where:
- #N is the workspace number (1 = main workspace, 2+ = workspace shares)
- WORKFLOW is the name of the running workflow (e.g., fix-tests, crs, run, rerun)
- CL_NAME is the ChangeSpec name being worked on (optional, can be empty)
"""

import os
import re
import subprocess
from dataclasses import dataclass

from ace.changespec import changespec_lock, write_changespec_atomic


@dataclass
class _WorkspaceClaim:
    """Represents a single workspace claim in the RUNNING field."""

    workspace_num: int
    workflow: str
    cl_name: str | None

    def to_line(self) -> str:
        """Convert to RUNNING field line format."""
        cl_part = self.cl_name or ""
        return f"  #{self.workspace_num} | {self.workflow} | {cl_part}"

    @staticmethod
    def from_line(line: str) -> "_WorkspaceClaim | None":
        """Parse a RUNNING field line into a _WorkspaceClaim."""
        # Match pattern: "  #<N> | <WORKFLOW> | <CL_NAME>"
        match = re.match(r"^\s*#(\d+)\s*\|\s*(\S+)\s*\|\s*(.*)$", line)
        if not match:
            return None
        workspace_num = int(match.group(1))
        workflow = match.group(2)
        cl_name = match.group(3).strip() or None
        return _WorkspaceClaim(
            workspace_num=workspace_num,
            workflow=workflow,
            cl_name=cl_name,
        )


def _normalize_running_field_spacing(content: str) -> str:
    """Normalize blank lines around the RUNNING field.

    Ensures exactly two blank lines between:
    - The last RUNNING entry and the first ChangeSpec (NAME field)
    - If there's no RUNNING field, clean up any orphaned blank lines at the start

    Args:
        content: The file content as a string.

    Returns:
        The content with normalized spacing.
    """
    lines = content.split("\n")
    result_lines: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this is the RUNNING field
        if line.startswith("RUNNING:"):
            result_lines.append(line)
            i += 1

            # Collect all RUNNING entries (2-space indented lines starting with #)
            while i < len(lines):
                entry_line = lines[i]
                if entry_line.startswith("  ") and entry_line.strip().startswith("#"):
                    result_lines.append(entry_line)
                    i += 1
                else:
                    break

            # Skip all blank lines after RUNNING entries
            while i < len(lines) and lines[i].strip() == "":
                i += 1

            # Add exactly two blank lines before the next content (NAME field)
            if i < len(lines):
                result_lines.append("")
                result_lines.append("")
        else:
            result_lines.append(line)
            i += 1

    return "\n".join(result_lines)


def _clean_orphaned_blank_lines(content: str) -> str:
    """Clean up orphaned consecutive blank lines in the file.

    This is used after removing the RUNNING field entirely to clean up
    any extra blank lines that were left behind.

    Args:
        content: The file content as a string.

    Returns:
        The content with consecutive blank lines reduced to at most two.
        Two blank lines are preserved because they serve as boundaries
        between ChangeSpecs.
    """
    lines = content.split("\n")
    result_lines: list[str] = []
    consecutive_blank_count = 0

    for line in lines:
        is_blank = line.strip() == ""

        if is_blank:
            consecutive_blank_count += 1
            # Allow at most 2 consecutive blank lines (ChangeSpec boundary)
            if consecutive_blank_count > 2:
                continue
        else:
            consecutive_blank_count = 0

        result_lines.append(line)

    return "\n".join(result_lines)


def get_claimed_workspaces(project_file: str) -> list[_WorkspaceClaim]:
    """Get all workspace claims from a ProjectSpec file.

    Args:
        project_file: Path to the ProjectSpec file

    Returns:
        List of _WorkspaceClaim objects representing active claims
    """
    if not os.path.exists(project_file):
        return []

    try:
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return []

    claims: list[_WorkspaceClaim] = []
    in_running_field = False

    for line in lines:
        if line.startswith("RUNNING:"):
            in_running_field = True
            continue

        if in_running_field:
            # Check if this is a continuation line (starts with 2 spaces)
            if line.startswith("  ") and line.strip().startswith("#") is not False:
                claim = _WorkspaceClaim.from_line(line)
                if claim:
                    claims.append(claim)
            else:
                # End of RUNNING field
                break

    return claims


def claim_workspace(
    project_file: str,
    workspace_num: int,
    workflow: str,
    cl_name: str | None = None,
) -> bool:
    """Claim a workspace by adding it to the RUNNING field.

    Acquires a lock for the entire read-modify-write cycle.

    Args:
        project_file: Path to the ProjectSpec file
        workspace_num: Workspace number to claim (1 = main, 2+ = shares)
        workflow: Name of the workflow claiming the workspace
        cl_name: Optional ChangeSpec name being worked on

    Returns:
        True if claim was successful, False otherwise
    """
    if not os.path.exists(project_file):
        return False

    try:
        with changespec_lock(project_file):
            with open(project_file, encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")

            new_claim = _WorkspaceClaim(
                workspace_num=workspace_num,
                workflow=workflow,
                cl_name=cl_name,
            )

            # Find RUNNING field or insert it after BUG field
            running_field_idx = -1
            bug_field_idx = -1
            running_end_idx = -1

            for i, line in enumerate(lines):
                if line.startswith("BUG:"):
                    bug_field_idx = i
                elif line.startswith("RUNNING:"):
                    running_field_idx = i
                    # Find end of RUNNING field
                    for j in range(i + 1, len(lines)):
                        if lines[j].startswith("  ") and (
                            lines[j].strip().startswith("#")
                            or lines[j].strip().startswith("|")
                        ):
                            running_end_idx = j
                        else:
                            if running_end_idx == -1:
                                running_end_idx = i
                            break
                    else:
                        if running_end_idx == -1:
                            running_end_idx = i
                    break

            if running_field_idx >= 0:
                # RUNNING field exists - add new claim
                # Insert after the last continuation line
                insert_idx = running_end_idx + 1
                lines.insert(insert_idx, new_claim.to_line())
            else:
                # RUNNING field doesn't exist - create it
                if bug_field_idx >= 0:
                    # Insert after BUG field
                    insert_idx = bug_field_idx + 1
                    lines.insert(insert_idx, f"RUNNING:\n{new_claim.to_line()}")
                else:
                    # No BUG field - insert at the beginning
                    lines.insert(0, f"RUNNING:\n{new_claim.to_line()}\n")

            # Normalize blank lines around RUNNING field
            result_content = "\n".join(lines)
            result_content = _normalize_running_field_spacing(result_content)

            # Write atomically
            cl_part = f" for {cl_name}" if cl_name else ""
            write_changespec_atomic(
                project_file,
                result_content,
                f"Claim workspace #{workspace_num} ({workflow}){cl_part}",
            )
            return True
    except Exception:
        return False


def release_workspace(
    project_file: str,
    workspace_num: int,
    workflow: str | None = None,
    cl_name: str | None = None,
) -> bool:
    """Release a workspace by removing it from the RUNNING field.

    Acquires a lock for the entire read-modify-write cycle.

    Args:
        project_file: Path to the ProjectSpec file
        workspace_num: Workspace number to release
        workflow: Optional workflow name to match (for more specific release)
        cl_name: Optional ChangeSpec name to match (for more specific release)

    Returns:
        True if release was successful, False otherwise
    """
    if not os.path.exists(project_file):
        return False

    try:
        with changespec_lock(project_file):
            with open(project_file, encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")

            new_lines: list[str] = []
            in_running_field = False
            running_field_idx = -1
            has_remaining_claims = False

            for line in lines:
                if line.startswith("RUNNING:"):
                    in_running_field = True
                    running_field_idx = len(new_lines)
                    new_lines.append(line)
                    continue

                if in_running_field and line.startswith("  "):
                    claim = _WorkspaceClaim.from_line(line)
                    if claim:
                        # Check if this is the claim to remove
                        should_remove = claim.workspace_num == workspace_num
                        if workflow and claim.workflow != workflow:
                            should_remove = False
                        if cl_name and claim.cl_name != cl_name:
                            should_remove = False

                        if should_remove:
                            # Skip this line (remove the claim)
                            continue
                        else:
                            has_remaining_claims = True
                else:
                    in_running_field = False

                new_lines.append(line)

            # If RUNNING field is now empty, remove it entirely
            if running_field_idx >= 0 and not has_remaining_claims:
                # Remove the RUNNING: line
                del new_lines[running_field_idx]

            # Normalize blank lines (clean up extra blanks after RUNNING field or where it was)
            result_content = "\n".join(new_lines)
            if has_remaining_claims:
                # Normalize spacing around remaining RUNNING field
                result_content = _normalize_running_field_spacing(result_content)
            else:
                # Clean up orphaned blank lines where RUNNING field was removed
                result_content = _clean_orphaned_blank_lines(result_content)

            # Write atomically
            write_changespec_atomic(
                project_file,
                result_content,
                f"Release workspace #{workspace_num}",
            )
            return True
    except Exception:
        return False


def update_running_field_cl_name(
    project_file: str,
    old_cl_name: str,
    new_cl_name: str,
) -> bool:
    """Update the cl_name in RUNNING field entries.

    This is used when a ChangeSpec is renamed (e.g., during restore) to
    ensure the RUNNING field entries reference the new name.
    Acquires a lock for the entire read-modify-write cycle.

    Args:
        project_file: Path to the ProjectSpec file
        old_cl_name: The old ChangeSpec name to replace
        new_cl_name: The new ChangeSpec name

    Returns:
        True if update was successful, False otherwise
    """
    if not os.path.exists(project_file):
        return False

    try:
        with changespec_lock(project_file):
            with open(project_file, encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")

            new_lines: list[str] = []
            in_running_field = False
            updated = False

            for line in lines:
                if line.startswith("RUNNING:"):
                    in_running_field = True
                    new_lines.append(line)
                    continue

                if in_running_field and line.startswith("  "):
                    claim = _WorkspaceClaim.from_line(line)
                    if claim and claim.cl_name == old_cl_name:
                        # Update the cl_name
                        updated_claim = _WorkspaceClaim(
                            workspace_num=claim.workspace_num,
                            workflow=claim.workflow,
                            cl_name=new_cl_name,
                        )
                        new_lines.append(updated_claim.to_line())
                        updated = True
                        continue
                else:
                    in_running_field = False

                new_lines.append(line)

            if not updated:
                # No changes needed
                return True

            # Write atomically
            write_changespec_atomic(
                project_file,
                "\n".join(new_lines),
                f"Rename {old_cl_name} to {new_cl_name} in RUNNING field",
            )
            return True
    except Exception:
        return False


def get_first_available_workspace(project_file: str, max_workspaces: int = 99) -> int:
    """Find the first available (unclaimed) workspace number.

    Args:
        project_file: Path to the ProjectSpec file
        max_workspaces: Maximum workspace number to check (1-99)

    Returns:
        First available workspace number (1 = main, 2+ = shares)
    """
    claims = get_claimed_workspaces(project_file)
    claimed_nums = {claim.workspace_num for claim in claims}

    # Find first unclaimed workspace number
    for n in range(1, max_workspaces + 1):
        if n not in claimed_nums:
            return n

    # All workspaces claimed - return 1 as fallback
    return 1


def get_first_available_loop_workspace(
    project_file: str, min_workspace: int = 100, max_workspace: int = 199
) -> int:
    """Find the first available (unclaimed) workspace number for loop hooks.

    Loop hooks use workspace numbers >= 100 to avoid conflicts with regular
    workflows that use workspaces 1-99.

    Args:
        project_file: Path to the ProjectSpec file
        min_workspace: Minimum workspace number to consider (default: 100)
        max_workspace: Maximum workspace number to consider (default: 199)

    Returns:
        First available workspace number in the loop range (100-199)
    """
    claims = get_claimed_workspaces(project_file)
    claimed_nums = {claim.workspace_num for claim in claims}

    # Find first unclaimed workspace number in loop range
    for n in range(min_workspace, max_workspace + 1):
        if n not in claimed_nums:
            return n

    # All loop workspaces claimed - return min_workspace as fallback
    return min_workspace


def get_workspace_directory_for_num(
    workspace_num: int, project_basename: str
) -> tuple[str, str | None]:
    """Get the workspace directory path for a given workspace number.

    Calls bb_get_workspace to get the directory path, which will create
    workspace shares if they don't exist.

    Args:
        workspace_num: Workspace number (1 = main, 2+ = shares)
        project_basename: Project name

    Returns:
        Tuple of (workspace_directory, workspace_suffix)
        - workspace_directory: Full path to workspace directory
        - workspace_suffix: Suffix like "fig_3" or None for main workspace

    Raises:
        RuntimeError: If bb_get_workspace command fails
    """
    workspace_dir = get_workspace_directory(project_basename, workspace_num)

    if workspace_num == 1:
        return (workspace_dir, None)
    else:
        workspace_suffix = f"{project_basename}_{workspace_num}"
        return (workspace_dir, workspace_suffix)


def get_workspace_directory(project: str, workspace_num: int = 1) -> str:
    """Get the workspace directory path by calling bb_get_workspace.

    This is the primary function for getting workspace directories. It calls
    the bb_get_workspace command which handles creating workspace shares
    if they don't exist.

    Args:
        project: Project name (e.g., "foobar")
        workspace_num: Workspace number (1 = main, 2+ = shares)

    Returns:
        Full path to workspace directory

    Raises:
        RuntimeError: If bb_get_workspace command fails
    """
    try:
        result = subprocess.run(
            ["bb_get_workspace", project, str(workspace_num)],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        error_msg = f"bb_get_workspace failed (exit code {e.returncode})"
        if e.stderr:
            error_msg += f": {e.stderr.strip()}"
        raise RuntimeError(error_msg) from e
    except FileNotFoundError as e:
        raise RuntimeError("bb_get_workspace command not found") from e
