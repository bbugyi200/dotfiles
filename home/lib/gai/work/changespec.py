"""ChangeSpec parsing and display utilities."""

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from running_field import get_claimed_workspaces


@dataclass
class HistoryEntry:
    """Represents a single entry in the HISTORY field."""

    number: int
    note: str
    chat: str | None = None
    diff: str | None = None


@dataclass
class HookEntry:
    """Represents a single hook command entry in the HOOKS field.

    Format in file:
      some_command
        | YYmmddHHMMSS: RUNNING/PASSED/FAILED/ZOMBIE (XmYs)
    """

    command: str
    timestamp: str | None = None
    status: str | None = None  # RUNNING, PASSED, FAILED, ZOMBIE
    duration: str | None = None  # e.g., "1m23s"


def _build_history_entry(entry_dict: dict[str, str | int | None]) -> HistoryEntry:
    """Build a HistoryEntry from a dict with proper type handling."""
    number_val = entry_dict.get("number", 0)
    number = int(number_val) if number_val is not None else 0

    note_val = entry_dict.get("note", "")
    note = str(note_val) if note_val is not None else ""

    chat_val = entry_dict.get("chat")
    chat = str(chat_val) if chat_val is not None else None

    diff_val = entry_dict.get("diff")
    diff = str(diff_val) if diff_val is not None else None

    return HistoryEntry(number=number, note=note, chat=chat, diff=diff)


@dataclass
class ChangeSpec:
    """Represents a single ChangeSpec."""

    name: str
    description: str
    parent: str | None
    cl: str | None
    status: str
    test_targets: list[str] | None
    kickstart: str | None
    file_path: str
    line_number: int
    presubmit: str | None = None
    history: list[HistoryEntry] | None = None
    hooks: list[HookEntry] | None = None


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
    kickstart_lines: list[str] = []
    presubmit: str | None = None
    history_entries: list[HistoryEntry] = []
    current_history_entry: dict[str, str | int | None] | None = None
    hook_entries: list[HookEntry] = []
    current_hook_entry: HookEntry | None = None
    line_number = start_idx + 1  # Convert to 1-based line numbering

    in_description = False
    in_test_targets = False
    in_kickstart = False
    in_history = False
    in_hooks = False
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
            # Save any pending hook entry before starting new ChangeSpec
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            name = line[6:].strip()
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_history = False
            in_hooks = False
        elif line.startswith("DESCRIPTION:"):
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            in_description = True
            in_test_targets = False
            in_kickstart = False
            in_history = False
            in_hooks = False
            # Check if description is on the same line
            desc_inline = line[12:].strip()
            if desc_inline:
                description_lines.append(desc_inline)
        elif line.startswith("KICKSTART:"):
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            in_kickstart = True
            in_description = False
            in_test_targets = False
            in_history = False
            in_hooks = False
            # Check if kickstart is on the same line
            kickstart_inline = line[10:].strip()
            if kickstart_inline:
                kickstart_lines.append(kickstart_inline)
        elif line.startswith("PARENT: "):
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            parent = line[8:].strip()
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_history = False
            in_hooks = False
        elif line.startswith("CL: "):
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            cl = line[4:].strip()
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_history = False
            in_hooks = False
        elif line.startswith("STATUS: "):
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            status = line[8:].strip()
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_history = False
            in_hooks = False
        elif line.startswith("PRESUBMIT: "):
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            presubmit = line[11:].strip() or None
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_history = False
            in_hooks = False
        elif line.startswith("HISTORY:"):
            # Save any pending history entry before starting new field
            if current_history_entry is not None:
                history_entries.append(_build_history_entry(current_history_entry))
                current_history_entry = None
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            in_history = True
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_hooks = False
        elif line.startswith("HOOKS:"):
            # Save any pending history entry
            if current_history_entry is not None:
                history_entries.append(_build_history_entry(current_history_entry))
                current_history_entry = None
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            in_hooks = True
            in_history = False
            in_description = False
            in_test_targets = False
            in_kickstart = False
        elif line.startswith("TEST TARGETS:"):
            # Save any pending history entry
            if current_history_entry is not None:
                history_entries.append(_build_history_entry(current_history_entry))
                current_history_entry = None
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            in_test_targets = True
            in_description = False
            in_kickstart = False
            in_history = False
            in_hooks = False
            # Check if targets are on the same line
            targets_inline = line[13:].strip()
            if targets_inline:
                # Treat as single target (may contain spaces like "target (FAILED)")
                test_targets.append(targets_inline)
        elif in_hooks:
            # Parse HOOKS entries
            # Format:
            #   some_command
            #     | YYmmddHHMMSS: RUNNING/PASSED/FAILED/ZOMBIE (XmYs)
            stripped = line.strip()
            if line.startswith("  ") and not line.startswith("    "):
                # This is a command line (2-space indented, not 4-space)
                # Only if it doesn't start with '|'
                if not stripped.startswith("|"):
                    # Save previous hook entry if exists
                    if current_hook_entry is not None:
                        hook_entries.append(current_hook_entry)
                    # Start new hook entry
                    current_hook_entry = HookEntry(command=stripped)
            elif line.startswith("    ") and stripped.startswith("|"):
                # This is a status line (4-space indented with | prefix)
                # Format: | YYmmddHHMMSS: STATUS (XmYs)
                status_part = stripped[1:].strip()  # Remove leading |
                # Parse: YYmmddHHMMSS: STATUS (XmYs) or YYmmddHHMMSS: STATUS
                status_match = re.match(
                    r"^(\d{12}):\s*(RUNNING|PASSED|FAILED|ZOMBIE)(?:\s+\(([^)]+)\))?$",
                    status_part,
                )
                if status_match and current_hook_entry is not None:
                    current_hook_entry.timestamp = status_match.group(1)
                    current_hook_entry.status = status_match.group(2)
                    current_hook_entry.duration = status_match.group(3)
        elif in_history:
            # Parse HISTORY entries
            stripped = line.strip()
            # Check for new history entry: (N) Note text
            history_match = re.match(r"^\((\d+)\)\s+(.+)$", stripped)
            if history_match:
                # Save previous entry if exists
                if current_history_entry is not None:
                    history_entries.append(_build_history_entry(current_history_entry))
                # Start new entry
                current_history_entry = {
                    "number": int(history_match.group(1)),
                    "note": history_match.group(2),
                    "chat": None,
                    "diff": None,
                }
            elif stripped.startswith("| CHAT:"):
                if current_history_entry is not None:
                    current_history_entry["chat"] = stripped[7:].strip()
            elif stripped.startswith("| DIFF:"):
                if current_history_entry is not None:
                    current_history_entry["diff"] = stripped[7:].strip()
            # If line doesn't match history format, stay in history mode
            # (blank lines or other content will be ignored)
        elif in_description and line.startswith("  "):
            # Description continuation (2-space indented)
            # Strip trailing newline since we'll add them back with join
            description_lines.append(line[2:].rstrip("\n"))
        elif in_kickstart and line.startswith("  "):
            # Kickstart continuation (2-space indented)
            # Strip trailing newline since we'll add them back with join
            kickstart_lines.append(line[2:].rstrip("\n"))
        elif in_test_targets and line.startswith("  "):
            # Test targets continuation (2-space indented)
            target = line.strip()
            if target:
                test_targets.append(target)
        elif line.strip() == "":
            # Blank line - preserve in description or kickstart if we're in those modes
            if in_description:
                description_lines.append("")
            elif in_kickstart:
                kickstart_lines.append("")
        else:
            # Any other content ends the special parsing modes
            if not line.startswith("#"):  # Ignore comment lines
                in_description = False
                in_test_targets = False
                in_kickstart = False
                in_history = False
                in_hooks = False

        idx += 1

    # Save any pending history entry
    if current_history_entry is not None:
        history_entries.append(_build_history_entry(current_history_entry))

    # Save any pending hook entry
    if current_hook_entry is not None:
        hook_entries.append(current_hook_entry)

    # Create ChangeSpec if we found required fields
    if name and status:
        description = "\n".join(description_lines).strip()
        kickstart = "\n".join(kickstart_lines).strip() if kickstart_lines else None
        return (
            ChangeSpec(
                name=name,
                description=description,
                parent=parent,
                cl=cl,
                status=status,
                test_targets=test_targets if test_targets else None,
                kickstart=kickstart,
                file_path=file_path,
                line_number=line_number,
                presubmit=presubmit,
                history=history_entries if history_entries else None,
                hooks=hook_entries if hook_entries else None,
            ),
            idx,
        )

    return None, idx


def _parse_project_file(file_path: str) -> list[ChangeSpec]:
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

        # Look for ChangeSpec start by detecting NAME: field
        # (ChangeSpecs can start with ## ChangeSpec header OR directly with NAME:)
        if re.match(r"^##\s+ChangeSpec", line.strip()):
            # Skip the header line and parse the ChangeSpec
            changespec, next_idx = _parse_changespec_from_lines(
                lines, idx + 1, file_path
            )
            if changespec:
                changespecs.append(changespec)
            idx = next_idx
        elif line.startswith("NAME: "):
            # ChangeSpec starts directly with NAME field (no header)
            changespec, next_idx = _parse_changespec_from_lines(lines, idx, file_path)
            if changespec:
                changespecs.append(changespec)
            idx = next_idx
        else:
            idx += 1

    return changespecs


def find_all_changespecs() -> list[ChangeSpec]:
    """Find all ChangeSpecs in all project files.

    Returns:
        List of all ChangeSpec objects from ~/.gai/projects/<project>/<project>.gp files
    """
    projects_dir = Path.home() / ".gai" / "projects"

    if not projects_dir.exists():
        return []

    all_changespecs: list[ChangeSpec] = []

    # Iterate through project directories
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue

        # Look for <project>.gp file inside the project directory
        project_name = project_dir.name
        gp_file = project_dir / f"{project_name}.gp"

        if gp_file.exists():
            changespecs = _parse_project_file(str(gp_file))
            all_changespecs.extend(changespecs)

    return all_changespecs


def _get_bug_field(project_file: str) -> str | None:
    """Get the BUG field value from a project file.

    Args:
        project_file: Path to the ProjectSpec file

    Returns:
        BUG field value or None if not found
    """
    if not os.path.exists(project_file):
        return None

    try:
        with open(project_file, encoding="utf-8") as f:
            for line in f:
                if line.startswith("BUG:"):
                    return line.split(":", 1)[1].strip()
                # Stop if we hit a NAME field (end of header section)
                if line.startswith("NAME:"):
                    break
    except Exception:
        pass

    return None


def _get_status_color(status: str) -> str:
    """Get the color for a given status based on vim syntax file.

    Workspace suffixes (e.g., " (fig_3)") are stripped before color lookup.

    Color mapping:
    - Making Change Requests...: #87AFFF (blue/purple)
    - Running QA...: #87AFFF (blue/purple)
    - Drafted: #87D700 (green)
    - Mailed: #00D787 (cyan-green)
    - Changes Requested: #FFAF00 (orange)
    - Submitted: #00AF00 (green)
    - Reverted: #808080 (gray)
    """
    # Strip workspace suffix before looking up color
    # Pattern: " (<project>_<N>)" at the end of the status
    base_status = re.sub(r" \([a-zA-Z0-9_-]+_\d+\)$", "", status)

    status_colors = {
        "Drafted": "#87D700",
        "Mailed": "#00D787",
        "Changes Requested": "#FFAF00",
        "Submitted": "#00AF00",
        "Reverted": "#808080",
    }
    return status_colors.get(base_status, "#FFFFFF")


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

    # --- ProjectSpec fields (BUG, RUNNING) ---
    bug_field = _get_bug_field(changespec.file_path)
    running_claims = get_claimed_workspaces(changespec.file_path)

    if bug_field:
        text.append("BUG: ", style="bold #87D7FF")
        text.append(f"{bug_field}\n", style="#FFD700")

    if running_claims:
        text.append("RUNNING:\n", style="bold #87D7FF")
        for claim in running_claims:
            text.append(f"  #{claim.workspace_num} | {claim.workflow}", style="#87AFFF")
            if claim.cl_name:
                text.append(f" | {claim.cl_name}", style="#87AFFF")
            text.append("\n")

    # Add separator between ProjectSpec and ChangeSpec fields (two blank lines)
    if bug_field or running_claims:
        text.append("\n\n")

    # NAME field
    text.append("NAME: ", style="bold #87D7FF")
    text.append(f"{changespec.name}\n", style="bold #00D7AF")

    # DESCRIPTION field
    text.append("DESCRIPTION:\n", style="bold #87D7FF")
    for line in changespec.description.split("\n"):
        text.append(f"  {line}\n", style="#D7D7AF")

    # KICKSTART field (only display if present)
    if changespec.kickstart:
        text.append("KICKSTART:\n", style="bold #87D7FF")
        for line in changespec.kickstart.split("\n"):
            text.append(f"  {line}\n", style="#D7D7AF")

    # PARENT field (only display if present)
    if changespec.parent:
        text.append("PARENT: ", style="bold #87D7FF")
        text.append(f"{changespec.parent}\n", style="bold #00D7AF")

    # CL field (only display if present)
    if changespec.cl:
        text.append("CL: ", style="bold #87D7FF")
        text.append(f"{changespec.cl}\n", style="bold #5FD7FF")

    # STATUS field
    text.append("STATUS: ", style="bold #87D7FF")
    status_color = _get_status_color(changespec.status)
    text.append(f"{changespec.status}\n", style=f"bold {status_color}")

    # TEST TARGETS field (only display if present)
    if changespec.test_targets:
        text.append("TEST TARGETS: ", style="bold #87D7FF")
        if len(changespec.test_targets) == 1:
            # Check if the single value is "None" - if so, skip displaying
            if changespec.test_targets[0] != "None":
                target = changespec.test_targets[0]
                if "(FAILED)" in target:
                    # Split target to highlight (FAILED) in red
                    base_target = target.replace(" (FAILED)", "")
                    text.append(f"{base_target} ", style="bold #AFD75F")
                    text.append("(FAILED)\n", style="bold #FF5F5F")
                else:
                    text.append(f"{target}\n", style="bold #AFD75F")
            else:
                text.append("None\n")
        else:
            text.append("\n")
            for target in changespec.test_targets:
                if target != "None":
                    if "(FAILED)" in target:
                        # Split target to highlight (FAILED) in red
                        base_target = target.replace(" (FAILED)", "")
                        text.append(f"  {base_target} ", style="bold #AFD75F")
                        text.append("(FAILED)\n", style="bold #FF5F5F")
                    else:
                        text.append(f"  {target}\n", style="bold #AFD75F")

    # PRESUBMIT field (only display if present)
    if changespec.presubmit:
        text.append("PRESUBMIT: ", style="bold #87D7FF")
        # Replace home directory with ~ for cleaner display
        presubmit_path = changespec.presubmit.replace(str(Path.home()), "~")
        # Check for status markers and highlight them
        if "(FAILED)" in presubmit_path:
            base_path = presubmit_path.replace(" (FAILED)", "")
            text.append(f"{base_path} ", style="#AF87D7")
            text.append("(FAILED)\n", style="bold #FF5F5F")
        elif "(PASSED)" in presubmit_path:
            base_path = presubmit_path.replace(" (PASSED)", "")
            text.append(f"{base_path} ", style="#AF87D7")
            text.append("(PASSED)\n", style="bold #00AF00")
        elif "(ZOMBIE)" in presubmit_path:
            base_path = presubmit_path.replace(" (ZOMBIE)", "")
            text.append(f"{base_path} ", style="#AF87D7")
            text.append("(ZOMBIE)\n", style="bold #808080")
        else:
            text.append(f"{presubmit_path}\n", style="#AF87D7")

    # HISTORY field (only display if present)
    if changespec.history:
        text.append("HISTORY:\n", style="bold #87D7FF")
        for entry in changespec.history:
            # Entry number and note (2-space indented like other multi-line fields)
            text.append(f"  ({entry.number}) ", style="bold #D7AF5F")
            text.append(f"{entry.note}\n", style="#D7D7AF")
            # CHAT field (if present) - 6 spaces = 2 (base indent) + 4 (sub-field indent)
            if entry.chat:
                text.append("      | CHAT: ", style="#87AFFF")
                chat_path = entry.chat.replace(str(Path.home()), "~")
                text.append(f"{chat_path}\n", style="#87AFFF")
            # DIFF field (if present)
            if entry.diff:
                text.append("      | DIFF: ", style="#87AFFF")
                diff_path = entry.diff.replace(str(Path.home()), "~")
                text.append(f"{diff_path}\n", style="#87AFFF")

    # HOOKS field (only display if present)
    if changespec.hooks:
        text.append("HOOKS:\n", style="bold #87D7FF")
        for hook in changespec.hooks:
            # Hook command (2-space indented)
            text.append(f"  {hook.command}\n", style="#D7D7AF")
            # Status line (if present) - 4-space indented with | prefix
            if hook.timestamp and hook.status:
                text.append("    | ", style="#808080")
                text.append(f"{hook.timestamp}: ", style="#808080")
                # Color based on status
                if hook.status == "PASSED":
                    text.append(hook.status, style="bold #00AF00")
                elif hook.status == "FAILED":
                    text.append(hook.status, style="bold #FF5F5F")
                elif hook.status == "RUNNING":
                    text.append(hook.status, style="bold #87AFFF")
                elif hook.status == "ZOMBIE":
                    text.append(hook.status, style="bold #FFAF00")
                else:
                    text.append(hook.status)
                # Duration (if present)
                if hook.duration:
                    text.append(f" ({hook.duration})", style="#808080")
                text.append("\n")

    # Remove trailing newline to avoid extra blank lines in panel
    text.rstrip()

    # Display in a panel with file location as title
    # Replace home directory with ~ for cleaner display
    file_path = changespec.file_path.replace(str(Path.home()), "~")
    file_location = f"{file_path}:{changespec.line_number}"
    console.print(
        Panel(
            text,
            title=f"📋 {file_location}",
            border_style="cyan",
            padding=(1, 2),
        )
    )
