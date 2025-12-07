"""Presubmit workflow for running bb_hg_presubmit as a background process."""

import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from status_state_machine import transition_changespec_status

from .changespec import ChangeSpec


def _get_workspace_directory(changespec: ChangeSpec) -> str | None:
    """Get the workspace directory for a ChangeSpec.

    Args:
        changespec: The ChangeSpec to get the workspace directory for.

    Returns:
        The workspace directory path, or None if environment variables are not set.
    """
    # Extract project basename from file path
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Get required environment variables
    goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
    goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")

    if not goog_cloud_dir or not goog_src_dir_base:
        return None

    return os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)


def _get_presubmit_output_path(changespec: ChangeSpec) -> str:
    """Get the path for storing presubmit output.

    Uses a timestamp in the filename to preserve history.

    Args:
        changespec: The ChangeSpec to get the output path for.

    Returns:
        Full path to the presubmit output log file.
    """
    # Extract project basename from file path
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Create output directory
    output_dir = (
        Path.home() / ".gai" / "projects" / project_basename / "presubmit_output"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = changespec.name.replace("/", "_").replace(" ", "_")
    filename = f"{safe_name}_{timestamp}.log"

    return str(output_dir / filename)


def _update_changespec_presubmit_fields(
    project_file: str,
    changespec_name: str,
    presubmit_output: str,
    presubmit_pid: int,
) -> bool:
    """Update the PRESUBMIT OUTPUT and PRESUBMIT PID fields in the project file.

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        presubmit_output: Path to the presubmit output log file.
        presubmit_pid: PID of the presubmit process.

    Returns:
        True if update succeeded, False otherwise.
    """
    try:
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()

        # Find the ChangeSpec and update/add fields
        updated_lines = []
        in_target_changespec = False
        current_name = None
        found_presubmit_output = False
        found_presubmit_pid = False

        for i, line in enumerate(lines):
            # Check if this is a NAME field
            if line.startswith("NAME:"):
                current_name = line.split(":", 1)[1].strip()
                in_target_changespec = current_name == changespec_name
                updated_lines.append(line)
                continue

            # If we're in the target ChangeSpec
            if in_target_changespec:
                # Update PRESUBMIT OUTPUT if it exists
                if line.startswith("PRESUBMIT OUTPUT:"):
                    updated_lines.append(f"PRESUBMIT OUTPUT: {presubmit_output}\n")
                    found_presubmit_output = True
                    continue
                # Update PRESUBMIT PID if it exists
                if line.startswith("PRESUBMIT PID:"):
                    updated_lines.append(f"PRESUBMIT PID: {presubmit_pid}\n")
                    found_presubmit_pid = True
                    continue
                # If we hit the next NAME or end of changespec, insert fields if not found
                if line.startswith("NAME:") or (
                    line.strip() == ""
                    and i + 1 < len(lines)
                    and lines[i + 1].strip() == ""
                ):
                    if not found_presubmit_output:
                        updated_lines.append(f"PRESUBMIT OUTPUT: {presubmit_output}\n")
                        found_presubmit_output = True
                    if not found_presubmit_pid:
                        updated_lines.append(f"PRESUBMIT PID: {presubmit_pid}\n")
                        found_presubmit_pid = True
                    in_target_changespec = False

            updated_lines.append(line)

        # If we reached end of file while still in target changespec
        if in_target_changespec:
            if not found_presubmit_output:
                updated_lines.append(f"PRESUBMIT OUTPUT: {presubmit_output}\n")
            if not found_presubmit_pid:
                updated_lines.append(f"PRESUBMIT PID: {presubmit_pid}\n")

        # Write to temp file then atomically rename
        project_dir = os.path.dirname(project_file)
        fd, temp_path = tempfile.mkstemp(dir=project_dir, prefix=".tmp_", suffix=".txt")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.writelines(updated_lines)
            os.replace(temp_path, project_file)
            return True
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    except Exception:
        return False


def run_presubmit(
    changespec: ChangeSpec,
    console: Console,
    workspace_suffix: str | None = None,
) -> bool:
    """Run bb_hg_presubmit as a disowned background process.

    Args:
        changespec: The ChangeSpec to run presubmit for.
        console: Rich Console object for output.
        workspace_suffix: Optional workspace suffix to append to status.

    Returns:
        True if presubmit was started successfully, False otherwise.
    """
    # Get workspace directory
    workspace_dir = _get_workspace_directory(changespec)
    if not workspace_dir:
        console.print(
            "[red]Error: GOOG_CLOUD_DIR or GOOG_SRC_DIR_BASE environment variable not set[/red]"
        )
        return False

    if not os.path.isdir(workspace_dir):
        console.print(
            f"[red]Error: Workspace directory does not exist: {workspace_dir}[/red]"
        )
        return False

    # Get output file path
    output_path = _get_presubmit_output_path(changespec)

    console.print(f"[cyan]Starting presubmit for '{changespec.name}'...[/cyan]")
    console.print(f"[dim]Output will be written to: {output_path}[/dim]")

    try:
        # Open output file for writing
        with open(output_path, "w") as output_file:
            # Start bb_hg_presubmit as a background process
            # Use start_new_session=True to fully detach from parent
            process = subprocess.Popen(
                ["bb_hg_presubmit"],
                cwd=workspace_dir,
                stdout=output_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

        pid = process.pid
        console.print(f"[green]Presubmit started with PID {pid}[/green]")

        # Update the ChangeSpec with presubmit output path and PID
        if not _update_changespec_presubmit_fields(
            changespec.file_path,
            changespec.name,
            output_path,
            pid,
        ):
            console.print(
                "[yellow]Warning: Failed to update presubmit fields in project file[/yellow]"
            )

        # Transition status to "Running Presubmits..."
        new_status = "Running Presubmits..."
        if workspace_suffix:
            new_status = f"Running Presubmits... ({workspace_suffix})"

        success, old_status, error_msg = transition_changespec_status(
            changespec.file_path,
            changespec.name,
            new_status,
            validate=True,
        )

        if success:
            console.print(f"[green]Status updated: {old_status} → {new_status}[/green]")
            return True
        else:
            console.print(f"[red]Error updating status: {error_msg}[/red]")
            return False

    except FileNotFoundError:
        console.print("[red]Error: bb_hg_presubmit command not found[/red]")
        return False
    except Exception as e:
        console.print(f"[red]Error starting presubmit: {e}[/red]")
        return False
