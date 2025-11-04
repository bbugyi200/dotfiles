"""Workflow nodes for the work-project workflow."""

import os
import subprocess
import sys
from pathlib import Path

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
        print(f"Parsed {len(changespecs)} ChangeSpecs from {project_file}")

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
    changespec_map = {cs["NAME"]: cs for cs in changespecs}

    # Find the first eligible ChangeSpec
    for cs in changespecs:
        status = cs.get("STATUS", "").strip()
        parent = cs.get("PARENT", "").strip()

        # Skip if not "Not Started"
        if status != "Not Started":
            continue

        # Check if no parent or parent is completed
        if parent == "None":
            # No parent - eligible
            state["selected_changespec"] = cs
            print(f"Selected ChangeSpec: {cs['NAME']} (no parent)")
            return state

        # Check if parent is in a completed state
        if parent in changespec_map:
            parent_status = changespec_map[parent].get("STATUS", "").strip()
            if parent_status in ["Pre-Mailed", "Mailed", "Submitted"]:
                state["selected_changespec"] = cs
                print(
                    f"Selected ChangeSpec: {cs['NAME']} (parent {parent} is {parent_status})"
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
    dry_run = state.get("dry_run", False)

    if dry_run:
        # Dry run mode - just print the ChangeSpec
        print(f"\n[DRY RUN] Would invoke create-cl for {selected_cs['NAME']}")
        print(f"Project: {project_name}")
        print(f"Design docs: {design_docs_dir}")
        print("\n" + "=" * 80)
        print("ChangeSpec that would be sent to create-cl:")
        print("=" * 80)
        print(changespec_text)
        print("=" * 80)
        state["success"] = True
        return state

    print(f"\nInvoking create-cl workflow for {selected_cs['NAME']}...")
    print(f"Project: {project_name}")
    print(f"Design docs: {design_docs_dir}")
    print("\n" + "=" * 80)

    try:
        # Invoke gai create-cl with the ChangeSpec on STDIN
        result = subprocess.run(
            ["gai", "create-cl", project_name, design_docs_dir],
            input=changespec_text,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            state["success"] = True
            print("\n" + "=" * 80)
            print(f"Successfully created CL for {selected_cs['NAME']}")
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
    print("\n✓ work-project workflow completed successfully")
    return state


def handle_failure(state: WorkProjectState) -> WorkProjectState:
    """Handle workflow failure."""
    failure_reason = state.get("failure_reason", "Unknown error")
    print(f"\n✗ work-project workflow failed: {failure_reason}", file=sys.stderr)
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
            # Blank line - end of current ChangeSpec
            if current_field:
                current_cs[current_field] = "\n".join(current_value_lines).strip()
                current_value_lines = []
                current_field = None

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
