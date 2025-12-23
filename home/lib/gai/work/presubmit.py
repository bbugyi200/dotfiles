"""Presubmit workflow for running bb_hg_presubmit as a background process."""

import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from running_field import get_workspace_directory as get_workspace_dir

from .changespec import ChangeSpec


def _get_workspace_directory(
    changespec: ChangeSpec, workspace_suffix: str | None = None
) -> str | None:
    """Get the workspace directory for a ChangeSpec.

    Args:
        changespec: The ChangeSpec to get the workspace directory for.
        workspace_suffix: Optional workspace suffix (e.g., "project_2") for alternate workspaces.

    Returns:
        The workspace directory path, or None if bb_get_workspace fails.
    """
    # Extract project basename from file path
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Determine workspace number from suffix if provided
    workspace_num = 1
    if workspace_suffix:
        # Extract number from suffix like "project_2"
        parts = workspace_suffix.rsplit("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            workspace_num = int(parts[1])

    try:
        return get_workspace_dir(project_basename, workspace_num)
    except RuntimeError:
        return None


def _get_presubmit_path(changespec: ChangeSpec) -> str:
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


def _update_changespec_presubmit_field(
    project_file: str,
    changespec_name: str,
    presubmit_path: str,
) -> bool:
    """Update the PRESUBMIT field in the project file.

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        presubmit_path: Path to the presubmit output log file.

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
        found_presubmit = False

        for i, line in enumerate(lines):
            # Check if this is a NAME field
            if line.startswith("NAME:"):
                current_name = line.split(":", 1)[1].strip()
                in_target_changespec = current_name == changespec_name
                updated_lines.append(line)
                continue

            # If we're in the target ChangeSpec
            if in_target_changespec:
                # Update PRESUBMIT if it exists
                if line.startswith("PRESUBMIT:"):
                    updated_lines.append(f"PRESUBMIT: {presubmit_path}\n")
                    found_presubmit = True
                    continue
                # If we hit the next NAME or end of changespec, insert field if not found
                if line.startswith("NAME:") or (
                    line.strip() == ""
                    and i + 1 < len(lines)
                    and lines[i + 1].strip() == ""
                ):
                    if not found_presubmit:
                        updated_lines.append(f"PRESUBMIT: {presubmit_path}\n")
                        found_presubmit = True
                    in_target_changespec = False

            updated_lines.append(line)

        # If we reached end of file while still in target changespec
        if in_target_changespec:
            if not found_presubmit:
                updated_lines.append(f"PRESUBMIT: {presubmit_path}\n")

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
    # Get workspace directory (using the workspace suffix if provided)
    workspace_dir = _get_workspace_directory(changespec, workspace_suffix)
    if not workspace_dir:
        console.print("[red]Error: Failed to get workspace directory[/red]")
        return False

    if not os.path.isdir(workspace_dir):
        console.print(
            f"[red]Error: Workspace directory does not exist: {workspace_dir}[/red]"
        )
        return False

    # Get output file path
    presubmit_path = _get_presubmit_path(changespec)

    console.print(f"[cyan]Starting presubmit for '{changespec.name}'...[/cyan]")
    console.print(f"[dim]Output will be written to: {presubmit_path}[/dim]")

    try:
        # Create a wrapper script that runs bb_hg_presubmit and writes exit code
        # to the output file when complete
        wrapper_script = """#!/bin/bash
bb_hg_presubmit "$@" 2>&1
exit_code=$?
echo ""
echo "===PRESUBMIT_COMPLETE=== EXIT_CODE: $exit_code"
exit $exit_code
"""
        # Write wrapper script to temp file
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False
        ) as wrapper_file:
            wrapper_file.write(wrapper_script)
            wrapper_path = wrapper_file.name

        os.chmod(wrapper_path, 0o755)

        # Start the wrapper as a background process
        with open(presubmit_path, "w") as output_file:
            process = subprocess.Popen(
                [wrapper_path],
                cwd=workspace_dir,
                stdout=output_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

        pid = process.pid
        console.print(f"[green]Presubmit started with PID {pid}[/green]")

        # Update the ChangeSpec with presubmit path (use ~ for home directory)
        presubmit_path_with_tilde = presubmit_path.replace(str(Path.home()), "~")
        if not _update_changespec_presubmit_field(
            changespec.file_path,
            changespec.name,
            presubmit_path_with_tilde,
        ):
            console.print(
                "[yellow]Warning: Failed to update presubmit field in project file[/yellow]"
            )

        return True

    except FileNotFoundError:
        console.print("[red]Error: bb_hg_presubmit command not found[/red]")
        return False
    except Exception as e:
        console.print(f"[red]Error starting presubmit: {e}[/red]")
        return False
