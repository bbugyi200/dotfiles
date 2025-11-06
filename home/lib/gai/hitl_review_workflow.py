"""Workflow for human-in-the-loop review of ProjectSpec files."""

import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich_utils import print_status, print_workflow_header
from shared_utils import run_shell_command
from workflow_base import BaseWorkflow

# All valid STATUS values for ChangeSpecs
_VALID_STATUSES = [
    "Not Started",
    "In Progress",
    "Failed to Create CL",
    "TDD CL Created",
    "Fixing Tests",
    "Failed to Fix Tests",
    "Pre-Mailed",
    "Mailed",
    "Submitted",
]

# STATUS values that should be flagged for review (in priority order)
_REVIEW_STATUSES = [
    "Pre-Mailed",
    "TDD CL Created",
    "Failed to Fix Tests",
    "Failed to Create CL",
]


def _extract_bug_id(bug_value: str) -> str:
    """
    Extract bug ID from a BUG field value.

    Supports formats:
    - Plain ID: "12345" -> "12345"
    - URL format: "http://b/12345" -> "12345"
    - URL format: "https://b/12345" -> "12345"

    Args:
        bug_value: Raw BUG field value

    Returns:
        Extracted bug ID
    """
    bug_value = bug_value.strip()

    # Handle URL format: http://b/12345 or https://b/12345
    if bug_value.startswith("http://b/") or bug_value.startswith("https://b/"):
        prefix = "https://b/" if bug_value.startswith("https://") else "http://b/"
        return bug_value[len(prefix) :]

    # Plain ID format
    return bug_value


def _extract_cl_id(cl_value: str) -> str:
    """
    Extract CL ID from a CL field value.

    Supports formats:
    - Plain ID: "12345" -> "12345"
    - Legacy format: "cl/12345" -> "12345"
    - URL format: "http://cl/12345" -> "12345"
    - URL format: "https://cl/12345" -> "12345"

    Args:
        cl_value: Raw CL field value

    Returns:
        Extracted CL ID
    """
    cl_value = cl_value.strip()

    # Handle URL format: http://cl/12345 or https://cl/12345
    if cl_value.startswith("http://cl/") or cl_value.startswith("https://cl/"):
        prefix = "https://cl/" if cl_value.startswith("https://") else "http://cl/"
        return cl_value[len(prefix) :]

    # Handle legacy format: cl/12345
    if cl_value.startswith("cl/"):
        return cl_value[3:]

    # Plain ID format
    return cl_value


def _get_projects_dir() -> str:
    """Get the path to the ~/.gai/projects directory."""
    return os.path.expanduser("~/.gai/projects")


def _find_project_files() -> list[str]:
    """Find all ProjectSpec files in ~/.gai/projects directory."""
    projects_dir = _get_projects_dir()
    if not os.path.isdir(projects_dir):
        return []

    project_files = []
    for file_path in Path(projects_dir).glob("*.md"):
        if file_path.is_file():
            project_files.append(str(file_path))

    return sorted(project_files)


def _parse_project_spec(content: str) -> tuple[str | None, list[dict[str, str]]]:
    """
    Parse a ProjectSpec file into a BUG ID and a list of ChangeSpec dictionaries.

    This is a copy of the function from work_projects_workflow.workflow_nodes
    to avoid circular imports.

    Returns:
        Tuple of (bug_id, changespecs)
    """
    lines = content.split("\n")
    bug_id = None
    changespecs = []
    current_cs: dict[str, str] = {}
    current_field = None
    current_value_lines: list[str] = []

    # Check if first line is BUG field (handle both "BUG:" and "BUG " formats)
    if lines and (lines[0].startswith("BUG:") or lines[0].startswith("BUG ")):
        if lines[0].startswith("BUG:"):
            bug_id = lines[0][4:].strip()  # Extract bug ID (everything after "BUG:")
        else:
            bug_id = lines[0][4:].strip()  # Extract bug ID (everything after "BUG ")
        lines = lines[1:]  # Remove the BUG line

    for line in lines:
        # Check if this is a field header
        if line and not line.startswith(" ") and ":" in line:
            # Save previous field if exists
            if current_field:
                current_cs[current_field] = "\n".join(current_value_lines).strip()
                current_value_lines = []

            # Parse new field
            field, value = line.split(":", 1)
            current_field = field.strip()
            value = value.strip()

            if value:  # Single-line field value
                current_cs[current_field] = value
                current_field = None
            # else: multi-line field, continue collecting lines

        elif line.startswith("  ") and current_field:
            # Continuation of multi-line field (2-space indented)
            current_value_lines.append(line[2:])  # Remove 2-space indent

        elif not line.strip():
            # Blank line
            if current_field:
                # Blank line inside a multi-line field - preserve it
                current_value_lines.append("")
            else:
                # Blank line between ChangeSpecs - end current ChangeSpec
                if current_cs:
                    changespecs.append(current_cs)
                    current_cs = {}

    # Don't forget the last ChangeSpec if file doesn't end with blank line
    if current_field:
        current_cs[current_field] = "\n".join(current_value_lines).strip()
    if current_cs:
        changespecs.append(current_cs)

    return bug_id, changespecs


def _update_changespec_status(
    project_file: str, changespec_name: str, new_status: str
) -> None:
    """
    Update the STATUS field of a specific ChangeSpec in the project file.

    This is a copy of the function from work_projects_workflow.workflow_nodes
    to avoid circular imports.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update
        new_status: New STATUS value (e.g., "In Progress")
    """
    with open(project_file) as f:
        lines = f.readlines()

    # Find the ChangeSpec and update its STATUS
    updated_lines = []
    in_target_changespec = False
    current_name = None

    for line in lines:
        # Check if this is a NAME field
        if line.startswith("NAME:"):
            current_name = line.split(":", 1)[1].strip()
            in_target_changespec = current_name == changespec_name

        # Update STATUS if we're in the target ChangeSpec
        if in_target_changespec and line.startswith("STATUS:"):
            # Replace the STATUS line
            updated_lines.append(f"STATUS: {new_status}\n")
            in_target_changespec = False  # Done updating this ChangeSpec
        else:
            updated_lines.append(line)

    # Write the updated content back to the file
    with open(project_file, "w") as f:
        f.writelines(updated_lines)


def _find_changespecs_for_review(
    project_files: list[str],
) -> list[tuple[str, dict[str, str], str]]:
    """
    Find all ChangeSpecs that need review across all project files.

    Returns:
        List of tuples: (project_file, changespec_dict, current_status)
    """
    changespecs_for_review = []

    for project_file in project_files:
        try:
            with open(project_file) as f:
                content = f.read()

            bug_id, changespecs = _parse_project_spec(content)
            if not changespecs:
                continue

            for cs in changespecs:
                status = cs.get("STATUS", "").strip()
                if status in _REVIEW_STATUSES:
                    changespecs_for_review.append((project_file, cs, status))

        except Exception as e:
            print_status(f"Error reading {project_file}: {e}", "error")
            continue

    # Sort by STATUS priority (order in _REVIEW_STATUSES)
    def _status_priority(item: tuple[str, dict[str, str], str]) -> int:
        status = item[2]
        try:
            return _REVIEW_STATUSES.index(status)
        except ValueError:
            return len(_REVIEW_STATUSES)  # Put unknown statuses at the end

    changespecs_for_review.sort(key=_status_priority)

    return changespecs_for_review


def _change_to_project_directory(project_file: str) -> bool:
    """
    Change to the project's repository directory.

    The directory is constructed as: $GOOG_CLOUD_DIR/<PROJECT>/$GOOG_SRC_DIR_BASE
    where <PROJECT> is the basename of the project file without extension.

    Args:
        project_file: Path to the ProjectSpec file

    Returns:
        True if directory change was successful, False otherwise
    """
    # Get environment variables
    goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
    goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")

    if not goog_cloud_dir or not goog_src_dir_base:
        print_status(
            "GOOG_CLOUD_DIR or GOOG_SRC_DIR_BASE environment variables not set",
            "warning",
        )
        return False

    # Extract project name from project file path
    project_name = Path(project_file).stem  # e.g., "yserve" from "yserve.md"

    # Construct the target directory
    target_dir = os.path.join(goog_cloud_dir, project_name, goog_src_dir_base)

    # Check if directory exists
    if not os.path.isdir(target_dir):
        print_status(
            f"Project directory does not exist: {target_dir}",
            "warning",
        )
        return False

    # Change to the directory
    try:
        os.chdir(target_dir)
        print_status(f"Changed to project directory: {target_dir}", "info")
        return True
    except Exception as e:
        print_status(f"Failed to change to directory {target_dir}: {e}", "error")
        return False


def _get_test_output_file_path(project_file: str, changespec_name: str) -> str:
    """
    Get the path for the test output file for a ChangeSpec.

    This mirrors the function from work_projects_workflow.workflow_nodes.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec

    Returns:
        Path to the test output file for this ChangeSpec
    """
    project_dir = os.path.dirname(os.path.abspath(project_file))
    test_outputs_dir = os.path.join(project_dir, ".test_outputs")

    # Sanitize changespec name for use in filename
    safe_name = changespec_name.replace("/", "_").replace(" ", "_")
    return os.path.join(test_outputs_dir, f"{safe_name}.txt")


def _has_test_output(project_file: str, cs: dict[str, str]) -> bool:
    """
    Check if test output is available for a ChangeSpec.

    Args:
        project_file: Path to the ProjectSpec file
        cs: ChangeSpec dictionary

    Returns:
        True if test output file exists
    """
    cs_name = cs.get("NAME", "")
    if not cs_name:
        return False

    test_output_file = _get_test_output_file_path(project_file, cs_name)
    return os.path.exists(test_output_file)


def _view_test_output(project_file: str, cs: dict[str, str]) -> None:
    """
    View the test output for a ChangeSpec using less.

    Args:
        project_file: Path to the ProjectSpec file
        cs: ChangeSpec dictionary
    """
    cs_name = cs.get("NAME", "")
    test_output_file = _get_test_output_file_path(project_file, cs_name)

    if not os.path.exists(test_output_file):
        print_status(f"Test output not found: {test_output_file}", "error")
        return

    # Use less to view the test output
    try:
        subprocess.run(["less", test_output_file], check=False)
    except Exception as e:
        print_status(f"Error viewing test output: {e}", "error")


def _view_cl_diff(cs: dict[str, str]) -> None:
    """
    View the CL diff using hg_update and branch_diff.

    Args:
        cs: ChangeSpec dictionary
    """
    cs_name = cs.get("NAME", "").strip()
    if not cs_name:
        print_status("No NAME available for this ChangeSpec", "warning")
        return

    cl_value = cs.get("CL", "").strip()
    if not cl_value or cl_value.lower() == "none":
        print_status("No CL available for this ChangeSpec", "warning")
        return

    # Extract CL ID from the CL field for display purposes
    cl_id = _extract_cl_id(cl_value)

    print_status(f"Checking out CL {cs_name} (CL#{cl_id})...", "progress")

    # Run hg_update to checkout the CL using its NAME
    result = run_shell_command(f"hg_update {cs_name}", capture_output=True)
    if result.returncode != 0:
        print_status(f"Failed to checkout CL {cs_name}: {result.stderr}", "error")
        return

    print_status("Generating diff...", "progress")

    # Run branch_diff and pipe to less
    try:
        subprocess.run(
            "branch_diff --color=always | less -R",
            shell=True,
            check=False,
        )
    except Exception as e:
        print_status(f"Error viewing diff: {e}", "error")


def _format_changespec_for_display(cs: dict[str, str]) -> str:
    """
    Format a ChangeSpec dictionary for display.

    Args:
        cs: ChangeSpec dictionary

    Returns:
        Formatted string representation of the ChangeSpec
    """
    lines = []
    for key, value in cs.items():
        if "\n" in value:
            # Multi-line value - indent continuation lines
            lines.append(f"[bold]{key}:[/bold]")
            for line in value.split("\n"):
                lines.append(f"  {line}")
        else:
            # Single-line value
            lines.append(f"[bold]{key}:[/bold] {value}")
    return "\n".join(lines)


def _prompt_status_change(console: Console, current_status: str) -> str | None:
    """
    Prompt the user to select a new status for the ChangeSpec.

    Args:
        console: Rich console for output
        current_status: Current STATUS value

    Returns:
        New status value, or None to cancel
    """
    # Get all valid statuses except the current one
    available_statuses = [s for s in _VALID_STATUSES if s != current_status]

    console.print("\n[bold]Select new STATUS:[/bold]")
    for i, status in enumerate(available_statuses, 1):
        console.print(f"  {i}. {status}")
    console.print("  c. Cancel")

    choice = Prompt.ask(
        "\nSelect an option",
        choices=[str(i) for i in range(1, len(available_statuses) + 1)] + ["c"],
        default="c",
    )

    if choice == "c":
        return None

    # Convert choice to status
    idx = int(choice) - 1
    return available_statuses[idx]


def _prompt_user_action(
    console: Console,
    project_file: str,
    cs: dict[str, str],
    current_status: str,
    current_index: int,
    total_count: int,
) -> tuple[str, str | None]:
    """
    Prompt the user for an action on the ChangeSpec.

    Args:
        console: Rich console for output
        project_file: Path to the ProjectSpec file
        cs: Full ChangeSpec dictionary
        current_status: Current STATUS value
        current_index: Current index in the list (0-based)
        total_count: Total number of ChangeSpecs to review

    Returns:
        Tuple of (action, new_status) where action is one of:
        - "next": Move to next ChangeSpec
        - "prev": Move to previous ChangeSpec
        - "update": Update STATUS to new_status value
        - "quit": Quit review process
    """
    # Format the full ChangeSpec for display
    cs_display = _format_changespec_for_display(cs)

    console.print(
        Panel(
            cs_display,
            title=f"Review Required ({current_index + 1}/{total_count})",
            border_style="yellow",
        )
    )

    # Build list of available options
    options = []
    option_descriptions = []

    if current_index > 0:
        options.append("p")
        option_descriptions.append("  p. Previous ChangeSpec")

    if current_index < total_count - 1:
        options.append("n")
        option_descriptions.append("  n. Next ChangeSpec")

    options.append("s")
    option_descriptions.append("  s. Change STATUS")

    # Check if CL diff is available
    cl_value = cs.get("CL", "").strip()
    has_cl = cl_value and cl_value.lower() != "none"
    if has_cl:
        options.append("d")
        option_descriptions.append("  d. View CL diff")

    # Check if test output is available
    if _has_test_output(project_file, cs):
        options.append("t")
        option_descriptions.append("  t. View test output")

    options.append("q")
    option_descriptions.append("  q. Quit review process")

    console.print("\n[bold]Available options:[/bold]")
    for desc in option_descriptions:
        console.print(desc)

    default_option = "n" if "n" in options else "q"
    choice = Prompt.ask(
        "\nSelect an option",
        choices=options,
        default=default_option,
    )

    if choice == "q":
        return ("quit", None)
    elif choice == "n":
        return ("next", None)
    elif choice == "p":
        return ("prev", None)
    elif choice == "s":
        new_status = _prompt_status_change(console, current_status)
        if new_status:
            return ("update", new_status)
        else:
            # User cancelled, stay on this ChangeSpec
            return _prompt_user_action(
                console, project_file, cs, current_status, current_index, total_count
            )
    elif choice == "d":
        _view_cl_diff(cs)
        # After viewing diff, prompt again
        return _prompt_user_action(
            console, project_file, cs, current_status, current_index, total_count
        )
    elif choice == "t":
        _view_test_output(project_file, cs)
        # After viewing test output, prompt again
        return _prompt_user_action(
            console, project_file, cs, current_status, current_index, total_count
        )

    # Should never reach here
    return ("quit", None)


class HITLReviewWorkflow(BaseWorkflow):
    """A workflow for human-in-the-loop review of ProjectSpec files."""

    def __init__(self) -> None:
        """Initialize the HITL review workflow."""
        pass

    @property
    def name(self) -> str:
        """Return the workflow name."""
        return "hitl-review"

    @property
    def description(self) -> str:
        """Return the workflow description."""
        return "Human-in-the-loop review of ProjectSpec files"

    def run(self) -> bool:
        """Run the HITL review workflow."""
        console = Console()

        # Print workflow header
        print_workflow_header("hitl-review", "")

        # Find all project files
        print_status("Scanning for ProjectSpec files...", "progress")
        project_files = _find_project_files()

        if not project_files:
            print_status(
                f"No ProjectSpec files found in {_get_projects_dir()}", "warning"
            )
            return True

        print_status(f"Found {len(project_files)} ProjectSpec file(s)", "success")

        # Find ChangeSpecs that need review
        print_status("Checking for ChangeSpecs that need review...", "progress")
        changespecs_for_review = _find_changespecs_for_review(project_files)

        if not changespecs_for_review:
            print_status("No ChangeSpecs require review!", "success")
            return True

        print_status(
            f"Found {len(changespecs_for_review)} ChangeSpec(s) requiring review",
            "info",
        )

        # Process ChangeSpecs with index-based navigation
        reviewed_count = 0
        current_index = 0
        last_project_file = None

        while current_index < len(changespecs_for_review):
            project_file, cs, current_status = changespecs_for_review[current_index]
            cs_name = cs.get("NAME", "UNKNOWN")
            project_name = Path(project_file).stem

            # Change to project directory if we're reviewing a new project
            if project_file != last_project_file:
                console.print(
                    f"\n[bold cyan]Project:[/bold cyan] {project_name} ({project_file})"
                )
                _change_to_project_directory(project_file)
                last_project_file = project_file

            # Prompt user for action
            action, new_status = _prompt_user_action(
                console,
                project_file,
                cs,
                current_status,
                current_index,
                len(changespecs_for_review),
            )

            if action == "quit":
                print_status("\nReview process aborted by user", "warning")
                break
            elif action == "next":
                current_index += 1
            elif action == "prev":
                current_index -= 1
            elif action == "update" and new_status:
                # Update the STATUS
                try:
                    _update_changespec_status(project_file, cs_name, new_status)
                    print_status(
                        f"Updated {cs_name} STATUS: {current_status} → {new_status}",
                        "success",
                    )
                    reviewed_count += 1
                    # Move to next after successful update
                    current_index += 1
                except Exception as e:
                    print_status(
                        f"Error updating {cs_name} in {project_file}: {e}", "error"
                    )
                    # Stay on current ChangeSpec on error

        # Print summary
        console.print(f"\n[bold]Review Summary:[/bold] {reviewed_count} updated")

        return True


def main() -> NoReturn:
    """Main entry point for the HITL review workflow."""
    workflow = HITLReviewWorkflow()
    success = workflow.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
