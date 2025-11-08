"""ChangeSpec parsing and display utilities."""

import re
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


@dataclass
class ChangeSpec:
    """Represents a single ChangeSpec."""

    name: str
    description: str
    parent: str | None
    cl: str | None
    status: str
    test_targets: list[str] | None
    file_path: str
    line_number: int


def _parse_changespec_from_lines(
    lines: list[str], start_idx: int, file_path: str
) -> tuple[ChangeSpec | None, int]:
    """Parse a single ChangeSpec from lines starting at start_idx.

    Returns:
        Tuple of (ChangeSpec or None, next_index_to_process)
    """
    name: str | None = None
    description_lines: list[str] = []
    parent: str | None = None
    cl: str | None = None
    status: str | None = None
    test_targets: list[str] = []
    line_number = start_idx + 1  # Convert to 1-based line numbering

    in_description = False
    in_test_targets = False
    idx = start_idx
    consecutive_blank_lines = 0

    while idx < len(lines):
        line = lines[idx]

        # Check for end of ChangeSpec (next ChangeSpec header or 2 blank lines)
        if line.strip().startswith("##") and idx > start_idx:
            break
        if line.strip() == "":
            consecutive_blank_lines += 1
            # 2 blank lines indicate end of ChangeSpec
            if consecutive_blank_lines >= 2:
                break
        else:
            consecutive_blank_lines = 0

        # Parse field lines
        if line.startswith("NAME: "):
            name = line[6:].strip()
            in_description = False
            in_test_targets = False
        elif line.startswith("DESCRIPTION:"):
            in_description = True
            in_test_targets = False
            # Check if description is on the same line
            desc_inline = line[12:].strip()
            if desc_inline:
                description_lines.append(desc_inline)
        elif line.startswith("PARENT: "):
            parent_value = line[8:].strip()
            parent = parent_value if parent_value != "None" else None
            in_description = False
            in_test_targets = False
        elif line.startswith("CL: "):
            cl_value = line[4:].strip()
            cl = cl_value if cl_value != "None" else None
            in_description = False
            in_test_targets = False
        elif line.startswith("STATUS: "):
            status = line[8:].strip()
            in_description = False
            in_test_targets = False
        elif line.startswith("TEST TARGETS:"):
            in_test_targets = True
            in_description = False
            # Check if targets are on the same line
            targets_inline = line[13:].strip()
            if targets_inline and targets_inline != "None":
                # Parse space-separated targets
                test_targets.extend(targets_inline.split())
        elif in_description and line.startswith("  "):
            # Description continuation (2-space indented)
            description_lines.append(line[2:])
        elif in_test_targets and line.startswith("  "):
            # Test targets continuation (2-space indented)
            target = line.strip()
            if target:
                test_targets.append(target)
        elif line.strip() == "":
            # Blank line - preserve in description if we're in description mode
            if in_description:
                description_lines.append("")
        else:
            # Any other content ends the special parsing modes
            if not line.startswith("#"):  # Ignore comment lines
                in_description = False
                in_test_targets = False

        idx += 1

    # Create ChangeSpec if we found required fields
    if name and status:
        description = "\n".join(description_lines).strip()
        return (
            ChangeSpec(
                name=name,
                description=description,
                parent=parent,
                cl=cl,
                status=status,
                test_targets=test_targets if test_targets else None,
                file_path=file_path,
                line_number=line_number,
            ),
            idx,
        )

    return None, idx


def parse_project_file(file_path: str) -> list[ChangeSpec]:
    """Parse all ChangeSpecs from a project file.

    Args:
        file_path: Path to the project markdown file

    Returns:
        List of ChangeSpec objects
    """
    changespecs: list[ChangeSpec] = []

    try:
        with open(file_path) as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")
        return []

    idx = 0
    while idx < len(lines):
        line = lines[idx]

        # Look for ChangeSpec headers (## ChangeSpec or similar)
        if re.match(r"^##\s+ChangeSpec", line.strip()):
            # Skip the header line and parse the ChangeSpec
            changespec, next_idx = _parse_changespec_from_lines(
                lines, idx + 1, file_path
            )
            if changespec:
                changespecs.append(changespec)
            idx = next_idx
        else:
            idx += 1

    return changespecs


def find_all_changespecs() -> list[ChangeSpec]:
    """Find all ChangeSpecs in all project files.

    Returns:
        List of all ChangeSpec objects from ~/.gai/projects/*.md files
    """
    projects_dir = Path.home() / ".gai" / "projects"

    if not projects_dir.exists():
        return []

    all_changespecs: list[ChangeSpec] = []
    for md_file in sorted(projects_dir.glob("*.md")):
        changespecs = parse_project_file(str(md_file))
        all_changespecs.extend(changespecs)

    return all_changespecs


def _get_status_color(status: str) -> str:
    """Get the color for a given status based on vim syntax file.

    Color mapping from gaiproject.vim:
    - Blocked: #AF5F00 (dark orange/brown)
    - Not Started: #D7AF00 (gold)
    - In Progress: #5FD7FF (light cyan)
    - TDD CL Created: #AF87FF (purple)
    - Fixing Tests: #FFD75F (yellow)
    - Pre-Mailed: #87D700 (green)
    - Mailed: #00D787 (cyan-green)
    - Submitted: #00AF00 (green)
    - Failed to Create CL: #FF5F5F (red)
    - Failed to Fix Tests: #FF8787 (light red)
    """
    status_colors = {
        "Blocked": "#AF5F00",
        "Not Started": "#D7AF00",
        "In Progress": "#5FD7FF",
        "TDD CL Created": "#AF87FF",
        "Fixing Tests": "#FFD75F",
        "Pre-Mailed": "#87D700",
        "Mailed": "#00D787",
        "Submitted": "#00AF00",
        "Failed to Create CL": "#FF5F5F",
        "Failed to Fix Tests": "#FF8787",
    }
    return status_colors.get(status, "#FFFFFF")


def display_changespec(changespec: ChangeSpec, console: Console) -> None:
    """Display a ChangeSpec using rich formatting.

    Color scheme from gaiproject.vim:
    - Field keys (NAME:, DESCRIPTION:, etc.): bold #87D7FF (cyan)
    - NAME/PARENT values: bold #00D7AF (cyan-green)
    - CL values: bold #5FD7FF (light cyan)
    - DESCRIPTION values: #D7D7AF (tan/beige)
    - STATUS values: status-specific colors
    - TEST TARGETS: bold #AFD75F (green)
    """
    # Build the display text
    text = Text()

    # NAME field
    text.append("NAME: ", style="bold #87D7FF")
    text.append(f"{changespec.name}\n", style="bold #00D7AF")

    # DESCRIPTION field
    text.append("DESCRIPTION:\n", style="bold #87D7FF")
    for line in changespec.description.split("\n"):
        text.append(f"  {line}\n", style="#D7D7AF")

    # PARENT field
    text.append("PARENT: ", style="bold #87D7FF")
    parent_value = changespec.parent if changespec.parent else "None"
    text.append(f"{parent_value}\n", style="bold #00D7AF")

    # CL field
    text.append("CL: ", style="bold #87D7FF")
    cl_value = changespec.cl if changespec.cl else "None"
    text.append(f"{cl_value}\n", style="bold #5FD7FF")

    # STATUS field
    text.append("STATUS: ", style="bold #87D7FF")
    status_color = _get_status_color(changespec.status)
    text.append(f"{changespec.status}\n", style=f"bold {status_color}")

    # TEST TARGETS field
    text.append("TEST TARGETS: ", style="bold #87D7FF")
    if changespec.test_targets:
        if len(changespec.test_targets) == 1:
            text.append(f"{changespec.test_targets[0]}\n", style="bold #AFD75F")
        else:
            text.append("\n")
            for target in changespec.test_targets:
                text.append(f"  {target}\n", style="bold #AFD75F")
    else:
        text.append("None\n", style="bold #AFD75F")

    # File location
    file_location = f"{changespec.file_path}:{changespec.line_number}"
    text.append(f"\n[dim]Location: {file_location}[/dim]")

    # Display in a panel
    console.print(
        Panel(
            text,
            title="📋 ChangeSpec",
            border_style="cyan",
            padding=(1, 2),
        )
    )
