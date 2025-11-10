"""ChangeSpec operations for updating, extracting, and validating."""

import os
import re
import subprocess
import sys
import tempfile

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from status_state_machine import transition_changespec_status

from .changespec import ChangeSpec, find_all_changespecs


def update_test_targets(
    project_file: str, changespec_name: str, test_targets: str
) -> tuple[bool, str | None]:
    """Update the TEST TARGETS field of a specific ChangeSpec in the project file.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update
        test_targets: Test targets value (space-separated or newline-separated)

    Returns:
        Tuple of (success, error_message)
    """
    try:
        with open(project_file) as f:
            lines = f.readlines()

        # Find the ChangeSpec and add/update its TEST TARGETS
        updated_lines = []
        in_target_changespec = False
        current_name = None
        test_targets_updated = False

        # Parse test_targets to determine format
        if "\n" in test_targets:
            # Multi-line format
            targets_list = [t.strip() for t in test_targets.split("\n") if t.strip()]
            test_targets_lines = ["TEST TARGETS:\n"] + [
                f"  {target}\n" for target in targets_list
            ]
        else:
            # Single-line format
            test_targets_lines = [f"TEST TARGETS: {test_targets}\n"]

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check if this is a NAME field
            if line.startswith("NAME:"):
                current_name = line.split(":", 1)[1].strip()
                in_target_changespec = current_name == changespec_name
                updated_lines.append(line)
                i += 1
                continue

            # If we're in the target changespec
            if in_target_changespec:
                # Skip existing TEST TARGETS field if present
                if line.startswith("TEST TARGETS:"):
                    # Skip this line and any following indented lines
                    i += 1
                    while i < len(lines) and lines[i].startswith("  "):
                        i += 1
                    continue

                # Insert TEST TARGETS before STATUS field
                if line.startswith("STATUS:") and not test_targets_updated:
                    updated_lines.extend(test_targets_lines)
                    test_targets_updated = True
                    in_target_changespec = False
                    updated_lines.append(line)
                    i += 1
                    continue

            updated_lines.append(line)
            i += 1

        if not test_targets_updated:
            return (
                False,
                f"Could not find ChangeSpec '{changespec_name}' or STATUS field to insert TEST TARGETS",
            )

        # Write the updated content back to the file
        with open(project_file, "w") as f:
            f.writelines(updated_lines)

        return (True, None)
    except Exception as e:
        return (False, f"Error updating TEST TARGETS: {e}")


def should_show_run_option(changespec: ChangeSpec) -> bool:
    """Check if the 'r' (run) option should be shown for this ChangeSpec.

    The run option is shown for ChangeSpecs that have:
    - STATUS = "Unstarted (EZ)" - Runs new-ez-feature workflow
    - STATUS = "Unstarted (TDD)" - Runs new-failing-tests workflow

    Args:
        changespec: The ChangeSpec object to check

    Returns:
        True if run option should be shown, False otherwise
    """
    return changespec.status in ["Unstarted (EZ)", "Unstarted (TDD)"]


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
) -> tuple[bool, str | None]:
    """Update working directory to the specified ChangeSpec.

    This function:
    1. Changes to $GOOG_CLOUD_DIR/<project>/$GOOG_SRC_DIR_BASE
    2. Runs bb_hg_update <revision>

    Args:
        changespec: The ChangeSpec object to update to
        console: Optional Rich Console object for error output
        revision: Specific revision to update to. If None, uses parent or p4head.
                  Common values: changespec.name (for diff), changespec.parent (for workflow)

    Returns:
        Tuple of (success, error_message)
    """
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


def _parse_bug_id_from_project_file(project_file: str) -> str | None:
    """Parse the BUG field from a project file.

    The BUG field is expected at the top of the file in one of these formats:
    - BUG: 12345
    - BUG: http://b/12345
    - BUG: https://b/12345

    Args:
        project_file: Path to the ProjectSpec file

    Returns:
        The bug ID (e.g., "12345"), or None if not found
    """
    try:
        with open(project_file) as f:
            # Read first few lines to find BUG field
            for _ in range(10):  # Check first 10 lines
                line = f.readline()
                if not line:
                    break
                if line.startswith("BUG:"):
                    bug_value = line[4:].strip()
                    # Extract ID from URL format or use as-is
                    # Supports: 12345, http://b/12345, https://b/12345
                    match = re.search(r"(\d+)", bug_value)
                    if match:
                        return match.group(1)
                    break
        return None
    except Exception:
        return None


def _update_cl_field(
    project_file: str, changespec_name: str, cl_number: str
) -> tuple[bool, str | None]:
    """Update the CL field of a specific ChangeSpec in the project file.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update
        cl_number: CL number to set (e.g., "12345")

    Returns:
        Tuple of (success, error_message)
    """
    try:
        with open(project_file) as f:
            lines = f.readlines()

        # Find the ChangeSpec and update its CL field
        updated_lines = []
        in_target_changespec = False
        current_name = None
        cl_updated = False

        for line in lines:
            # Check if this is a NAME field
            if line.startswith("NAME:"):
                current_name = line.split(":", 1)[1].strip()
                in_target_changespec = current_name == changespec_name
                updated_lines.append(line)
                continue

            # If we're in the target changespec and found CL field, update it
            if in_target_changespec and line.startswith("CL:"):
                updated_lines.append(f"CL: {cl_number}\n")
                cl_updated = True
                in_target_changespec = False
                continue

            updated_lines.append(line)

        if not cl_updated:
            return (
                False,
                f"Could not find ChangeSpec '{changespec_name}' or CL field to update",
            )

        # Write the updated content back to the file
        with open(project_file, "w") as f:
            f.writelines(updated_lines)

        return (True, None)
    except Exception as e:
        return (False, f"Error updating CL field: {e}")


def _run_bb_hg_commit(
    cl_description: str,
    project_name: str,
    bug_number: str,
    cl_name: str,
    target_dir: str,
) -> tuple[bool, str | None, str | None]:
    """Run bb_hg_commit to create a commit and return the CL number.

    Args:
        cl_description: The CL description text
        project_name: Project name (basename of project file)
        bug_number: Bug ID
        cl_name: NAME field value for the CL
        target_dir: Directory to run the command in

    Returns:
        Tuple of (success, cl_number, error_message)
    """
    # Create temp file with CL description
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as temp_file:
            temp_file.write(cl_description)
            temp_file_path = temp_file.name

        # Run bb_hg_commit
        result = subprocess.run(
            [
                "bb_hg_commit",
                temp_file_path,
                project_name,
                bug_number,
                cl_name,
            ],
            cwd=target_dir,
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse CL number from output (branch_number returns just the number)
        cl_number = result.stdout.strip()
        if cl_number and cl_number.isdigit():
            return (True, cl_number, None)
        else:
            return (
                False,
                None,
                f"bb_hg_commit succeeded but output was not a valid CL number: {cl_number}",
            )
    except subprocess.CalledProcessError as e:
        error_msg = f"bb_hg_commit failed (exit code {e.returncode})"
        if e.stderr:
            error_msg += f": {e.stderr.strip()}"
        elif e.stdout:
            error_msg += f": {e.stdout.strip()}"
        return (False, None, error_msg)
    except FileNotFoundError:
        return (False, None, "bb_hg_commit command not found")
    except Exception as e:
        return (False, None, f"Unexpected error running bb_hg_commit: {str(e)}")
    finally:
        # Clean up temp file
        try:
            if "temp_file_path" in locals():
                os.unlink(temp_file_path)
        except Exception:
            pass


def run_bb_hg_commit_and_update_cl(
    changespec: ChangeSpec, console: Console | None = None
) -> tuple[bool, str | None]:
    """Run bb_hg_commit and update the CL field in the ChangeSpec.

    This function:
    1. Parses the BUG field from the project file
    2. Creates a temp file with the CL description (from DESCRIPTION field)
    3. Runs bb_hg_commit with project name, bug number, and CL name
    4. Updates the CL field in the ChangeSpec with the returned CL number

    Args:
        changespec: The ChangeSpec object to process
        console: Optional Rich Console object for status output

    Returns:
        Tuple of (success, error_message)
    """
    # Extract project basename from file path
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Parse BUG field from project file
    bug_number = _parse_bug_id_from_project_file(changespec.file_path)
    if not bug_number:
        return (False, "Could not parse BUG field from project file")

    # Get target directory
    goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
    goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")

    if not goog_cloud_dir:
        return (False, "GOOG_CLOUD_DIR environment variable is not set")
    if not goog_src_dir_base:
        return (False, "GOOG_SRC_DIR_BASE environment variable is not set")

    target_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)

    # Run bb_hg_commit
    if console:
        console.print("[cyan]Running bb_hg_commit to create commit...[/cyan]")

    success, cl_number, error_msg = _run_bb_hg_commit(
        cl_description=changespec.description,
        project_name=project_basename,
        bug_number=bug_number,
        cl_name=changespec.name,
        target_dir=target_dir,
    )

    if not success:
        return (False, error_msg)

    # At this point, cl_number should not be None since success is True
    assert cl_number is not None, "cl_number should not be None when success is True"

    if console:
        console.print(f"[green]Created commit with CL number: {cl_number}[/green]")

    # Update CL field in ChangeSpec
    success, error_msg = _update_cl_field(
        changespec.file_path, changespec.name, cl_number
    )

    if not success:
        return (False, f"Commit created but failed to update CL field: {error_msg}")

    if console:
        console.print("[green]CL field updated successfully![/green]")

    return (True, None)


def unblock_child_changespecs(
    parent_changespec: ChangeSpec, console: Console | None = None
) -> int:
    """Unblock child ChangeSpecs when parent is moved to Pre-Mailed.

    When a ChangeSpec is moved to "Pre-Mailed", any ChangeSpecs that:
    - Have STATUS of "Blocked (EZ)" or "Blocked (TDD)"
    - Have PARENT field equal to the NAME of the parent ChangeSpec

    Will automatically have their STATUS changed to the corresponding Unstarted status:
    - "Blocked (EZ)" -> "Unstarted (EZ)"
    - "Blocked (TDD)" -> "Unstarted (TDD)"

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
        if cs.status in ["Blocked (EZ)", "Blocked (TDD)"]
        and cs.parent == parent_changespec.name
    ]

    if not blocked_children:
        return 0

    # Unblock each child
    unblocked_count = 0
    for child in blocked_children:
        # Determine the new status
        new_status = (
            "Unstarted (EZ)" if child.status == "Blocked (EZ)" else "Unstarted (TDD)"
        )

        # Update the status
        success, old_status, error_msg = transition_changespec_status(
            child.file_path,
            child.name,
            new_status,
            validate=False,  # Don't validate - we know this transition is valid
        )

        if success:
            unblocked_count += 1
            if console:
                console.print(
                    f"[green]Unblocked child ChangeSpec '{child.name}': {old_status} → {new_status}[/green]"
                )
        else:
            if console:
                console.print(
                    f"[yellow]Warning: Failed to unblock '{child.name}': {error_msg}[/yellow]"
                )

    return unblocked_count
