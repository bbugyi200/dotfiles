"""Workflow for human-in-the-loop review of ProjectSpec files."""

import os
import sys
from pathlib import Path
from typing import NoReturn

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich_utils import print_status, print_workflow_header
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
    "Failed to Fix Tests",
    "Failed to Create CL",
]


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


def _prompt_user_for_status(
    console: Console, cs: dict[str, str], current_status: str
) -> str | None:
    """
    Prompt the user to select a new status for the ChangeSpec.

    Args:
        console: Rich console for output
        cs: Full ChangeSpec dictionary
        current_status: Current STATUS value

    Returns:
        New status value, "skip", "quit", or None if invalid input
    """
    # Get all valid statuses except the current one
    available_statuses = [s for s in _VALID_STATUSES if s != current_status]

    # Format the full ChangeSpec for display
    cs_display = _format_changespec_for_display(cs)

    console.print(
        Panel(
            cs_display,
            title="Review Required",
            border_style="yellow",
        )
    )

    console.print("\n[bold]Available options:[/bold]")
    for i, status in enumerate(available_statuses, 1):
        console.print(f"  {i}. {status}")
    console.print("  s. Skip to next ChangeSpec")
    console.print("  q. Quit review process")

    choice = Prompt.ask(
        "\nSelect an option",
        choices=[str(i) for i in range(1, len(available_statuses) + 1)] + ["s", "q"],
        default="s",
    )

    if choice == "q":
        return "quit"
    elif choice == "s":
        return "skip"
    else:
        # Convert choice to status
        idx = int(choice) - 1
        return available_statuses[idx]


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

        # Process each ChangeSpec
        reviewed_count = 0
        skipped_count = 0

        for project_file, cs, current_status in changespecs_for_review:
            cs_name = cs.get("NAME", "UNKNOWN")
            project_name = Path(project_file).stem

            console.print(
                f"\n[bold cyan]Project:[/bold cyan] {project_name} ({project_file})"
            )

            # Prompt user for action
            result = _prompt_user_for_status(console, cs, current_status)

            if result == "quit":
                print_status("\nReview process aborted by user", "warning")
                break
            elif result == "skip":
                print_status(f"Skipped {cs_name}", "info")
                skipped_count += 1
                continue
            elif result:
                # Update the STATUS
                try:
                    _update_changespec_status(project_file, cs_name, result)
                    print_status(
                        f"Updated {cs_name} STATUS: {current_status} → {result}",
                        "success",
                    )
                    reviewed_count += 1
                except Exception as e:
                    print_status(
                        f"Error updating {cs_name} in {project_file}: {e}", "error"
                    )

        # Print summary
        console.print(
            f"\n[bold]Review Summary:[/bold] {reviewed_count} updated, {skipped_count} skipped"
        )

        return True


def main() -> NoReturn:
    """Main entry point for the HITL review workflow."""
    workflow = HITLReviewWorkflow()
    success = workflow.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
