"""Commit-related operations for ChangeSpecs."""

import os
import re
import subprocess
import tempfile

from commit_workflow import CommitWorkflow
from rich.console import Console

from .changespec import ChangeSpec


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
    project_file: str, changespec_name: str, cl_url: str
) -> tuple[bool, str | None]:
    """Update the CL field of a specific ChangeSpec in the project file.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update
        cl_url: CL URL to set (e.g., "http://cl/12345")

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
                updated_lines.append(f"CL: {cl_url}\n")
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


def _run_gai_commit(
    cl_description: str,
    project_name: str,
    bug_number: str,
    cl_name: str,
    target_dir: str,
) -> tuple[bool, str | None]:
    """Run gai commit to create a commit.

    Args:
        cl_description: The CL description text
        project_name: Project name (basename of project file)
        bug_number: Bug ID
        cl_name: NAME field value for the CL
        target_dir: Directory to run the command in

    Returns:
        Tuple of (success, error_message)
    """
    # Create temp file with CL description
    temp_file_path = None
    original_dir = os.getcwd()
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as temp_file:
            temp_file.write(cl_description)
            temp_file_path = temp_file.name

        # Change to target directory for the commit
        os.chdir(target_dir)

        # Run CommitWorkflow directly
        workflow = CommitWorkflow(
            cl_name=cl_name,
            file_path=temp_file_path,
            bug=bug_number,
            project=project_name,
        )
        success = workflow.run()

        if success:
            return (True, None)
        else:
            return (False, "CommitWorkflow.run() returned False")
    except Exception as e:
        return (False, f"Unexpected error running commit workflow: {str(e)}")
    finally:
        # Restore original directory
        os.chdir(original_dir)
        # Clean up temp file
        try:
            if temp_file_path:
                os.unlink(temp_file_path)
        except Exception:
            pass


def _get_cl_from_branch_number(target_dir: str) -> tuple[bool, str | None, str | None]:
    """Run branch_number command to get the current branch's CL number.

    Args:
        target_dir: Directory to run the command in

    Returns:
        Tuple of (success, cl_number, error_message)
    """
    try:
        result = subprocess.run(
            ["branch_number"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            check=True,
        )

        cl_number = result.stdout.strip()
        if cl_number and cl_number.isdigit():
            return (True, cl_number, None)
        else:
            return (
                False,
                None,
                f"branch_number succeeded but output was not a valid CL number: {cl_number}",
            )
    except subprocess.CalledProcessError as e:
        error_msg = f"branch_number failed (exit code {e.returncode})"
        if e.stderr:
            error_msg += f": {e.stderr.strip()}"
        elif e.stdout:
            error_msg += f": {e.stdout.strip()}"
        return (False, None, error_msg)
    except FileNotFoundError:
        return (False, None, "branch_number command not found")
    except Exception as e:
        return (False, None, f"Unexpected error running branch_number: {str(e)}")


def run_bb_hg_upload(target_dir: str, console: Console) -> tuple[bool, str | None]:
    """Run bb_hg_upload to upload changes to Critique.

    Args:
        target_dir: Directory to run the command in
        console: Rich Console object for status output

    Returns:
        Tuple of (success, error_message)
    """
    console.print("[cyan]Uploading to Critique...[/cyan]")
    try:
        subprocess.run(
            ["bb_hg_upload"],
            cwd=target_dir,
            check=True,
        )
        console.print("[green]Upload completed successfully![/green]")
        return (True, None)
    except subprocess.CalledProcessError as e:
        return (False, f"bb_hg_upload failed (exit code {e.returncode})")
    except FileNotFoundError:
        return (False, "bb_hg_upload command not found")
    except Exception as e:
        return (False, f"Unexpected error running bb_hg_upload: {str(e)}")


def run_gai_commit_and_update_cl(
    changespec: ChangeSpec, console: Console | None = None
) -> tuple[bool, str | None]:
    """Run gai commit and update the CL field in the ChangeSpec.

    This function:
    1. Parses the BUG field from the project file
    2. Creates a temp file with the CL description (from DESCRIPTION field)
    3. Runs gai commit with project name, bug number, and CL name
    4. Runs branch_number to get the CL number
    5. Updates the CL field in the ChangeSpec with http://cl/{cl_number}

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

    # Run gai commit to create the commit
    if console:
        console.print("[cyan]Running gai commit to create commit...[/cyan]")

    success, error_msg = _run_gai_commit(
        cl_description=changespec.description,
        project_name=project_basename,
        bug_number=bug_number,
        cl_name=changespec.name,
        target_dir=target_dir,
    )

    if not success:
        return (False, error_msg)

    if console:
        console.print("[green]Commit created successfully![/green]")

    # Run branch_number to get the CL number
    if console:
        console.print("[cyan]Running branch_number to get CL number...[/cyan]")

    success, cl_number, error_msg = _get_cl_from_branch_number(target_dir)

    if not success:
        return (False, error_msg)

    # At this point, cl_number should not be None since success is True
    assert cl_number is not None, "cl_number should not be None when success is True"

    # Format as URL
    cl_url = f"http://cl/{cl_number}"

    if console:
        console.print(f"[green]Got CL number from branch_number: {cl_url}[/green]")

    # Update CL field in ChangeSpec with the URL
    success, error_msg = _update_cl_field(changespec.file_path, changespec.name, cl_url)

    if not success:
        return (False, f"Commit created but failed to update CL field: {error_msg}")

    if console:
        console.print("[green]CL field updated successfully![/green]")

    return (True, None)
