"""Workflow for accepting proposed HISTORY entries."""

import os
import re
import subprocess
import sys
import tempfile
from typing import Any, NoReturn

from history_utils import apply_diff_to_workspace, clean_workspace
from rich_utils import print_status
from shared_utils import run_shell_command
from work.changespec import ChangeSpec, HistoryEntry, parse_project_file
from workflow_base import BaseWorkflow


def _get_project_file_path(project: str) -> str:
    """Get the path to the project file for a given project.

    Args:
        project: Project name.

    Returns:
        Path to the project file (~/.gai/projects/<project>/<project>.gp).
    """
    return os.path.expanduser(f"~/.gai/projects/{project}/{project}.gp")


def _get_cl_name_from_branch() -> str | None:
    """Get the current CL name from branch_name command.

    Returns:
        The CL name, or None if not on a branch.
    """
    result = run_shell_command("branch_name", capture_output=True)
    if result.returncode != 0:
        return None
    branch_name = result.stdout.strip()
    return branch_name if branch_name else None


def _get_project_from_workspace() -> str | None:
    """Get the current project name from workspace_name command.

    Returns:
        The project name, or None if command fails.
    """
    result = run_shell_command("workspace_name", capture_output=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _parse_proposal_id(proposal_id: str) -> tuple[int, str] | None:
    """Parse a proposal ID into base number and letter.

    Args:
        proposal_id: The proposal ID (e.g., "2a", "2b").

    Returns:
        Tuple of (base_number, letter) or None if invalid.
    """
    match = re.match(r"^(\d+)([a-z])$", proposal_id)
    if not match:
        return None
    return int(match.group(1)), match.group(2)


def _get_changespec_from_file(project_file: str, cl_name: str) -> ChangeSpec | None:
    """Get a ChangeSpec from a project file by name.

    Args:
        project_file: Path to the project file.
        cl_name: The CL name to look for.

    Returns:
        The ChangeSpec if found, None otherwise.
    """
    changespecs = parse_project_file(project_file)
    for cs in changespecs:
        if cs.name == cl_name:
            return cs
    return None


def _find_proposal_entry(
    history: list[HistoryEntry] | None,
    base_number: int,
    letter: str,
) -> HistoryEntry | None:
    """Find a proposal entry in history by base number and letter.

    Args:
        history: List of history entries.
        base_number: The base number (e.g., 2 for "2a").
        letter: The proposal letter (e.g., "a" for "2a").

    Returns:
        The matching HistoryEntry or None if not found.
    """
    if not history:
        return None
    for entry in history:
        if entry.number == base_number and entry.proposal_letter == letter:
            return entry
    return None


def _renumber_history_entries(
    project_file: str,
    cl_name: str,
    accepted_proposals: list[tuple[int, str]],
) -> bool:
    """Renumber history entries after accepting proposals.

    Accepted proposals become the next regular numbers.
    Remaining proposals are renumbered to lowest available letters.

    Args:
        project_file: Path to the project file.
        cl_name: The CL name.
        accepted_proposals: List of (base_number, letter) tuples that were accepted,
            in the order they should become regular entries.

    Returns:
        True if successful, False otherwise.
    """
    try:
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return False

    # Find the ChangeSpec and its history section
    in_target_changespec = False
    history_start = -1
    history_end = -1

    for i, line in enumerate(lines):
        if line.startswith("NAME: "):
            current_name = line[6:].strip()
            if in_target_changespec:
                # We hit the next ChangeSpec
                if history_end < 0:
                    history_end = i
                break
            in_target_changespec = current_name == cl_name
        elif in_target_changespec:
            if line.startswith("HISTORY:"):
                history_start = i
            elif history_start >= 0:
                stripped = line.strip()
                # Check if still in HISTORY section
                if re.match(r"^\(\d+[a-z]?\)", stripped) or stripped.startswith("| "):
                    history_end = i + 1  # Track last history line
                elif stripped and not stripped.startswith("#"):
                    # Non-history content
                    break

    if history_start < 0:
        return False  # No HISTORY section found

    if history_end < 0:
        history_end = len(lines)

    # Parse current history entries
    history_lines = lines[history_start + 1 : history_end]
    entries: list[dict[str, Any]] = []
    current_entry: dict[str, Any] | None = None

    for line in history_lines:
        stripped = line.strip()
        # Match history entry: (N) or (Na) Note text
        entry_match = re.match(r"^\((\d+)([a-z])?\)\s+(.+)$", stripped)
        if entry_match:
            if current_entry:
                entries.append(current_entry)
            current_entry = {
                "number": int(entry_match.group(1)),
                "letter": entry_match.group(2),
                "note": entry_match.group(3),
                "chat": None,
                "diff": None,
                "raw_lines": [line],
            }
        elif stripped.startswith("| CHAT:") and current_entry:
            current_entry["chat"] = stripped[7:].strip()
            current_entry["raw_lines"].append(line)  # type: ignore[union-attr]
        elif stripped.startswith("| DIFF:") and current_entry:
            current_entry["diff"] = stripped[7:].strip()
            current_entry["raw_lines"].append(line)  # type: ignore[union-attr]
        elif current_entry and stripped == "":
            # Blank line within history section
            pass

    if current_entry:
        entries.append(current_entry)

    # Find max regular (non-proposal) number
    max_regular = 0
    for entry in entries:
        if entry["letter"] is None:
            max_regular = max(max_regular, int(entry["number"]))  # type: ignore[arg-type]

    # Determine new numbers for accepted proposals
    # They become next regular numbers in the order they were accepted
    next_regular = max_regular + 1
    accepted_set = set(accepted_proposals)

    # Group remaining proposals by base number
    remaining_proposals: list[dict[str, Any]] = []
    for entry in entries:
        if entry["letter"] is not None:
            key = (int(entry["number"]), str(entry["letter"]))
            if key not in accepted_set:
                remaining_proposals.append(entry)

    # Build new entries list
    new_entries: list[dict[str, Any]] = []

    # First, add all regular (non-proposal) entries unchanged
    for entry in entries:
        if entry["letter"] is None:
            new_entries.append(entry)

    # Add accepted proposals as new regular entries in acceptance order
    for base_num, letter in accepted_proposals:
        for entry in entries:
            if entry["number"] == base_num and entry["letter"] == letter:
                new_entry = entry.copy()
                new_entry["number"] = next_regular
                new_entry["letter"] = None
                new_entries.append(new_entry)
                next_regular += 1
                break

    # Add remaining proposals, renumbered with lowest available letters
    new_base = next_regular - 1  # Base number for remaining proposals
    letter_idx = 0
    for entry in remaining_proposals:
        new_entry = entry.copy()
        new_entry["number"] = new_base
        new_entry["letter"] = "abcdefghijklmnopqrstuvwxyz"[letter_idx]
        new_entries.append(new_entry)
        letter_idx += 1

    # Sort entries: regular entries by number, then proposals by base+letter
    def sort_key(e: dict[str, Any]) -> tuple[int, str]:
        num = int(e["number"]) if e["number"] is not None else 0
        letter = str(e["letter"]) if e["letter"] else ""
        return (num, letter)

    new_entries.sort(key=sort_key)

    # Rebuild history section
    new_history_lines = ["HISTORY:\n"]
    for entry in new_entries:
        num = entry["number"]
        letter = str(entry["letter"]) if entry["letter"] else ""
        note = entry["note"]
        new_history_lines.append(f"  ({num}{letter}) {note}\n")
        if entry["chat"]:
            new_history_lines.append(f"      | CHAT: {entry['chat']}\n")
        if entry["diff"]:
            new_history_lines.append(f"      | DIFF: {entry['diff']}\n")

    # Replace old history section with new one
    new_lines = lines[:history_start] + new_history_lines + lines[history_end:]

    # Write back atomically
    project_dir = os.path.dirname(project_file)
    fd, temp_path = tempfile.mkstemp(dir=project_dir, prefix=".tmp_", suffix=".gp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        os.replace(temp_path, project_file)
        return True
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        return False


class AcceptWorkflow(BaseWorkflow):
    """A workflow for accepting proposed HISTORY entries."""

    def __init__(
        self,
        proposals: list[str],
        cl_name: str | None = None,
    ) -> None:
        """Initialize the accept workflow.

        Args:
            proposals: List of proposal IDs to accept (e.g., ["2a", "2d"]).
            cl_name: Optional CL name. Defaults to current branch name.
        """
        self._proposals = proposals
        self._cl_name = cl_name

    @property
    def name(self) -> str:
        return "accept"

    @property
    def description(self) -> str:
        return "Accept proposed HISTORY entries"

    def run(self) -> bool:
        """Run the accept workflow.

        Returns:
            True if the workflow completed successfully, False otherwise.
        """
        # Get CL name
        cl_name = self._cl_name or _get_cl_name_from_branch()
        if not cl_name:
            print_status(
                "No CL name provided and not on a branch. "
                "Use 'gai accept <cl_name> <proposals>' to specify.",
                "error",
            )
            return False

        # Get project name
        project = _get_project_from_workspace()
        if not project:
            print_status(
                "Failed to get project name from 'workspace_name' command.", "error"
            )
            return False

        project_file = _get_project_file_path(project)
        if not os.path.isfile(project_file):
            print_status(f"Project file not found: {project_file}", "error")
            return False

        # Parse and validate all proposals
        parsed_proposals: list[tuple[int, str]] = []
        for proposal_id in self._proposals:
            parsed = _parse_proposal_id(proposal_id)
            if not parsed:
                print_status(
                    f"Invalid proposal ID: {proposal_id}. "
                    "Expected format like '2a', '2b'.",
                    "error",
                )
                return False
            parsed_proposals.append(parsed)

        # Get the ChangeSpec and validate proposals exist
        changespec = _get_changespec_from_file(project_file, cl_name)
        if not changespec:
            print_status(f"ChangeSpec not found: {cl_name}", "error")
            return False

        # Validate all proposals exist and have diffs
        for base_num, letter in parsed_proposals:
            entry = _find_proposal_entry(changespec.history, base_num, letter)
            if not entry:
                print_status(
                    f"Proposal ({base_num}{letter}) not found in HISTORY.", "error"
                )
                return False
            if not entry.diff:
                print_status(
                    f"Proposal ({base_num}{letter}) has no DIFF path.", "error"
                )
                return False

        # Apply proposals in order
        workspace_dir = os.getcwd()
        applied_count = 0

        for base_num, letter in parsed_proposals:
            entry = _find_proposal_entry(changespec.history, base_num, letter)
            if not entry or not entry.diff:
                continue  # Already validated above

            print_status(
                f"Applying proposal ({base_num}{letter}): {entry.note}", "progress"
            )

            success, error_msg = apply_diff_to_workspace(workspace_dir, entry.diff)
            if not success:
                print_status(
                    f"Failed to apply proposal ({base_num}{letter}): {error_msg}",
                    "error",
                )
                # Rollback if we applied any previous proposals
                if applied_count > 0:
                    print_status(
                        "Rolling back previously applied proposals...", "warning"
                    )
                    clean_workspace(workspace_dir)
                return False

            applied_count += 1
            print_status(f"Applied proposal ({base_num}{letter}).", "success")

        # All proposals applied successfully - amend the commit
        if applied_count > 0:
            print_status("Amending commit with accepted proposals...", "progress")

            # Build amend message from accepted proposal notes
            notes = []
            for base_num, letter in parsed_proposals:
                entry = _find_proposal_entry(changespec.history, base_num, letter)
                if entry:
                    notes.append(entry.note)

            combined_note = " | ".join(notes) if notes else "Accepted proposals"

            try:
                result = subprocess.run(
                    ["bb_hg_amend", combined_note],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    print_status(f"bb_hg_amend failed: {result.stderr}", "error")
                    return False
            except FileNotFoundError:
                print_status("bb_hg_amend command not found", "error")
                return False

        # Renumber history entries
        print_status("Renumbering HISTORY entries...", "progress")
        if _renumber_history_entries(project_file, cl_name, parsed_proposals):
            print_status("HISTORY entries renumbered successfully.", "success")
        else:
            print_status("Failed to renumber HISTORY entries.", "warning")

        print_status(f"Successfully accepted {applied_count} proposal(s)!", "success")
        return True


def main() -> NoReturn:
    """Main entry point for the accept workflow (standalone execution)."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Accept proposed HISTORY entries by applying their diffs."
    )
    parser.add_argument(
        "proposals",
        nargs="+",
        help="Proposal IDs to accept (e.g., '2a 2d'). Applied in order.",
    )
    parser.add_argument(
        "--cl",
        dest="cl_name",
        help="CL name (defaults to current branch name).",
    )

    args = parser.parse_args()

    workflow = AcceptWorkflow(
        proposals=args.proposals,
        cl_name=args.cl_name,
    )
    success = workflow.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
