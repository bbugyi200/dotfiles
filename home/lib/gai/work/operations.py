"""ChangeSpec operations for updating, extracting, and validating."""

import os
import subprocess

from rich.console import Console

from .changespec import ChangeSpec


def should_show_run_option(changespec: ChangeSpec) -> bool:
    """Check if the 'r' (run) option should be shown for this ChangeSpec.

    The run option is only shown for ChangeSpecs that:
    - Have STATUS = "Not Started"
    - Have TEST TARGETS = "None" (or None)

    Args:
        changespec: The ChangeSpec object to check

    Returns:
        True if run option should be shown, False otherwise
    """
    return changespec.status == "Not Started" and (
        changespec.test_targets is None or changespec.test_targets == ["None"]
    )


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
