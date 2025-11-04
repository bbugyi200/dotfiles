"""Workflow nodes for the work-project workflow."""

import os
import subprocess
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from rich_utils import print_status

from .state import WorkProjectState


def initialize_work_project_workflow(state: WorkProjectState) -> WorkProjectState:
    """
    Initialize the work-project workflow.

    Reads and parses the ProjectSpec file.
    """
    project_file = state["project_file"]

    # Validate project file exists
    if not os.path.isfile(project_file):
        return {
            **state,
            "failure_reason": f"Project file '{project_file}' does not exist",
        }

    # Extract project name from filename
    project_name = Path(project_file).stem
    state["project_name"] = project_name

    # Read and parse the ProjectSpec file
    try:
        with open(project_file) as f:
            content = f.read()

        changespecs = _parse_project_spec(content)
        if not changespecs:
            return {
                **state,
                "failure_reason": "No ChangeSpecs found in project file",
            }

        state["changespecs"] = changespecs
        print_status(
            f"Parsed {len(changespecs)} ChangeSpecs from {project_file}", "success"
        )

    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error reading project file: {e}",
        }

    return state


def select_next_changespec(state: WorkProjectState) -> WorkProjectState:
    """
    Select the next eligible ChangeSpec to work on.

    Finds the FIRST "Not Started" ChangeSpec that either:
    - Does NOT have any parent (PARENT == "None"), OR
    - Has a parent ChangeSpec that is "Pre-Mailed", "Mailed", or "Submitted"
    """
    changespecs = state["changespecs"]

    # Build a map of NAME -> ChangeSpec for easy lookup
    changespec_map = {cs.get("NAME", ""): cs for cs in changespecs if cs.get("NAME")}

    # Find the first eligible ChangeSpec
    for cs in changespecs:
        name = cs.get("NAME", "")
        status = cs.get("STATUS", "").strip()
        parent = cs.get("PARENT", "").strip()

        # Skip if no NAME field
        if not name:
            print_status("Skipping ChangeSpec with no NAME field", "warning")
            continue

        # Skip if not "Not Started"
        if status != "Not Started":
            continue

        # Check if no parent or parent is completed
        if parent == "None":
            # No parent - eligible
            state["selected_changespec"] = cs
            print_status(f"Selected ChangeSpec: {name} (no parent)", "success")
            return state

        # Check if parent is in a completed state
        if parent in changespec_map:
            parent_status = changespec_map[parent].get("STATUS", "").strip()
            if parent_status in ["Pre-Mailed", "Mailed", "Submitted"]:
                state["selected_changespec"] = cs
                print_status(
                    f"Selected ChangeSpec: {name} (parent {parent} is {parent_status})",
                    "success",
                )
                return state

    # No eligible ChangeSpec found
    return {
        **state,
        "failure_reason": "No eligible ChangeSpec found (all are either completed or blocked by incomplete parents)",
    }


def invoke_create_cl(state: WorkProjectState) -> WorkProjectState:
    """
    Invoke the create-cl workflow with the selected ChangeSpec.

    Calls `gai create-cl` with the ChangeSpec on STDIN.
    If dry_run is True, just prints the ChangeSpec without invoking create-cl.
    """
    selected_cs = state["selected_changespec"]
    if not selected_cs:
        return {
            **state,
            "failure_reason": "No ChangeSpec selected to invoke create-cl",
        }

    # Format the ChangeSpec for create-cl
    changespec_text = _format_changespec(selected_cs)

    # Get the project name and design docs dir
    project_name = state["project_name"]
    design_docs_dir = state["design_docs_dir"]
    project_file = state["project_file"]
    dry_run = state.get("dry_run", False)
    cs_name = selected_cs.get("NAME", "UNKNOWN")

    if dry_run:
        # Dry run mode - just print the ChangeSpec
        from rich.panel import Panel
        from rich_utils import console

        print_status(f"[DRY RUN] Would invoke create-cl for {cs_name}", "info")
        print_status(f"Project: {project_name}", "info")
        print_status(f"Design docs: {design_docs_dir}", "info")

        console.print(
            Panel(
                changespec_text,
                title="ChangeSpec that would be sent to create-cl",
                border_style="yellow",
                padding=(1, 2),
            )
        )
        state["success"] = True
        return state

    # Update the ChangeSpec STATUS to "In Progress" in the project file
    print_status(f"Updating STATUS to 'In Progress' for {cs_name}...", "progress")
    try:
        _update_changespec_status(project_file, cs_name, "In Progress")
        print_status(f"Updated STATUS in {project_file}", "success")
    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error updating project file: {e}",
        }

    print_status(f"Invoking create-cl workflow for {cs_name}...", "progress")
    print_status(f"Project: {project_name}", "info")
    print_status(f"Design docs: {design_docs_dir}", "info")

    try:
        # Invoke gai create-cl with the ChangeSpec on STDIN
        result = subprocess.run(
            ["gai", "create-cl", project_name, design_docs_dir],
            input=changespec_text,
            text=True,
            check=False,
            capture_output=True,
        )

        # Print the output from create-cl
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if result.returncode == 0:
            # Parse the CL-ID from the output
            cl_id = _parse_cl_id_from_output(result.stdout)
            if cl_id:
                print_status(f"Captured CL-ID: {cl_id}", "success")
                # Update the CL field in the project file
                try:
                    _update_changespec_cl(project_file, cs_name, cl_id)
                    print_status(f"Updated CL field in {project_file}", "success")
                except Exception as e:
                    print_status(f"Could not update CL field: {e}", "warning")

            state["success"] = True
            print_status(f"Successfully created CL for {cs_name}", "success")
        else:
            return {
                **state,
                "failure_reason": f"create-cl workflow failed with exit code {result.returncode}",
            }

    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error invoking create-cl: {e}",
        }

    return state


def handle_success(state: WorkProjectState) -> WorkProjectState:
    """Handle successful workflow completion."""
    from rich_utils import print_workflow_success

    print_workflow_success(
        "work-project", "Work-project workflow completed successfully!"
    )
    return state


def handle_failure(state: WorkProjectState) -> WorkProjectState:
    """Handle workflow failure."""
    from rich_utils import print_workflow_failure

    failure_reason = state.get("failure_reason", "Unknown error")
    print_workflow_failure(
        "work-project", "Work-project workflow failed", failure_reason
    )
    return state


def _parse_project_spec(content: str) -> list[dict[str, str]]:
    """
    Parse a ProjectSpec file into a list of ChangeSpec dictionaries.

    Each ChangeSpec is separated by a blank line and contains fields:
    NAME, DESCRIPTION, PARENT, CL, STATUS
    """
    changespecs = []
    current_cs: dict[str, str] = {}
    current_field = None
    current_value_lines: list[str] = []

    for line in content.split("\n"):
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

    return changespecs


def _format_changespec(cs: dict[str, str]) -> str:
    """
    Format a ChangeSpec dictionary back into the ChangeSpec text format.

    This is used to pass to create-cl via STDIN.
    """
    lines = []

    # NAME field
    lines.append(f"NAME: {cs.get('NAME', '')}")

    # DESCRIPTION field (multi-line, 2-space indented)
    lines.append("DESCRIPTION:")
    description = cs.get("DESCRIPTION", "")
    for desc_line in description.split("\n"):
        lines.append(f"  {desc_line}")

    # PARENT field
    lines.append(f"PARENT: {cs.get('PARENT', 'None')}")

    # CL field
    lines.append(f"CL: {cs.get('CL', 'None')}")

    # STATUS field
    lines.append(f"STATUS: {cs.get('STATUS', 'Not Started')}")

    return "\n".join(lines)


def _update_changespec_status(
    project_file: str, changespec_name: str, new_status: str
) -> None:
    """
    Update the STATUS field of a specific ChangeSpec in the project file.

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


def _update_changespec_cl(project_file: str, changespec_name: str, cl_id: str) -> None:
    """
    Update the CL field of a specific ChangeSpec in the project file.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update
        cl_id: CL-ID value (e.g., changeset hash)
    """
    with open(project_file) as f:
        lines = f.readlines()

    # Find the ChangeSpec and update its CL field
    updated_lines = []
    in_target_changespec = False
    current_name = None

    for line in lines:
        # Check if this is a NAME field
        if line.startswith("NAME:"):
            current_name = line.split(":", 1)[1].strip()
            in_target_changespec = current_name == changespec_name

        # Update CL if we're in the target ChangeSpec
        if in_target_changespec and line.startswith("CL:"):
            # Replace the CL line
            updated_lines.append(f"CL: {cl_id}\n")
            in_target_changespec = False  # Done updating this ChangeSpec
        else:
            updated_lines.append(line)

    # Write the updated content back to the file
    with open(project_file, "w") as f:
        f.writelines(updated_lines)


def _parse_cl_id_from_output(output: str) -> str | None:
    """
    Parse the CL-ID from create-cl workflow output.

    Looks for the pattern ##CL-ID:{cl_id}## in the output.

    Args:
        output: The stdout from create-cl workflow

    Returns:
        The CL-ID if found, None otherwise
    """
    import re

    match = re.search(r"##CL-ID:([^#]+)##", output)
    if match:
        return match.group(1)
    return None
