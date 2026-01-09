"""Functions for modifying existing COMMITS entries in ChangeSpecs."""

import re

from ace.changespec import changespec_lock, write_changespec_atomic


def reject_all_new_proposals(
    project_file: str,
    cl_name: str,
) -> int:
    """Reject all new proposals by changing (!: NEW PROPOSAL) to (~!: NEW PROPOSAL).

    Acquires a lock for the entire read-modify-write cycle.

    Args:
        project_file: Path to the project file.
        cl_name: The CL name to update.

    Returns:
        Number of proposals rejected, or -1 on error.
    """
    try:
        with changespec_lock(project_file):
            with open(project_file, encoding="utf-8") as f:
                lines = f.readlines()

            # Find and update all new proposals
            in_target_changespec = False
            in_commits = False
            rejected_count = 0

            for i, line in enumerate(lines):
                if line.startswith("NAME: "):
                    current_name = line[6:].strip()
                    in_target_changespec = current_name == cl_name
                    in_commits = False
                elif in_target_changespec:
                    if line.startswith("COMMITS:"):
                        in_commits = True
                    elif line.startswith(
                        (
                            "NAME:",
                            "DESCRIPTION:",
                            "PARENT:",
                            "CL:",
                            "STATUS:",
                            "TEST TARGETS:",
                            "KICKSTART:",
                            "HOOKS:",
                            "COMMENTS:",
                        )
                    ):
                        in_commits = False
                        if line.startswith("NAME:"):
                            in_target_changespec = False
                    elif in_commits:
                        stripped = line.strip()
                        # Match: (Na) Note text - (!: NEW PROPOSAL)
                        entry_match = re.match(
                            r"^\((\d+[a-z])\)\s+(.+?)\s+-\s+\(!:\s*NEW PROPOSAL\)$",
                            stripped,
                        )
                        if entry_match:
                            matched_id = entry_match.group(1)
                            note_text = entry_match.group(2)
                            # Preserve leading whitespace
                            leading_ws = line[: len(line) - len(line.lstrip())]
                            # Change (!: NEW PROPOSAL) to (~!: NEW PROPOSAL)
                            new_line = (
                                f"{leading_ws}({matched_id}) {note_text} - "
                                f"(~!: NEW PROPOSAL)\n"
                            )
                            lines[i] = new_line
                            rejected_count += 1

            if rejected_count == 0:
                return 0

            # Write atomically
            write_changespec_atomic(
                project_file,
                "".join(lines),
                f"Reject {rejected_count} new proposal(s) for {cl_name}",
            )
            return rejected_count
    except Exception:
        return -1


def update_commit_entry_suffix(
    project_file: str,
    cl_name: str,
    entry_id: str,
    new_suffix_type: str,
) -> bool:
    """Update or remove the suffix of a COMMITS entry.

    Acquires a lock for the entire read-modify-write cycle.

    Args:
        project_file: Path to the project file.
        cl_name: The CL name to update.
        entry_id: The entry ID to update (e.g., "2a").
        new_suffix_type: The action - "remove" to remove suffix, "reject" to change
            (!: MSG) to (~!: MSG).

    Returns:
        True if successful, False otherwise.
    """
    if new_suffix_type not in ("remove", "reject"):
        return False

    try:
        with changespec_lock(project_file):
            with open(project_file, encoding="utf-8") as f:
                lines = f.readlines()

            # Find the target entry and update its suffix
            in_target_changespec = False
            in_commits = False
            updated = False

            for i, line in enumerate(lines):
                if line.startswith("NAME: "):
                    current_name = line[6:].strip()
                    in_target_changespec = current_name == cl_name
                    in_commits = False
                elif in_target_changespec:
                    if line.startswith("COMMITS:"):
                        in_commits = True
                    elif line.startswith(
                        (
                            "NAME:",
                            "DESCRIPTION:",
                            "PARENT:",
                            "CL:",
                            "STATUS:",
                            "TEST TARGETS:",
                            "KICKSTART:",
                            "HOOKS:",
                            "COMMENTS:",
                        )
                    ):
                        in_commits = False
                        if line.startswith("NAME:"):
                            in_target_changespec = False
                    elif in_commits:
                        stripped = line.strip()
                        # Match entry with this ID: (Na) Note text - (!: MSG) or - (~: MSG)
                        entry_match = re.match(
                            rf"^\(({re.escape(entry_id)})\)\s+(.+?)\s+-\s+\((!:|~:)\s*([^)]+)\)$",
                            stripped,
                        )
                        if entry_match:
                            matched_id = entry_match.group(1)
                            note_text = entry_match.group(2)
                            suffix_prefix = entry_match.group(3)
                            suffix_msg = entry_match.group(4)
                            # Preserve leading whitespace
                            leading_ws = line[: len(line) - len(line.lstrip())]
                            if new_suffix_type == "remove":
                                # Remove the suffix entirely
                                new_line = f"{leading_ws}({matched_id}) {note_text}\n"
                            else:  # reject
                                # Change (!: MSG) to (~!: MSG)
                                if suffix_prefix == "!:":
                                    new_line = (
                                        f"{leading_ws}({matched_id}) {note_text} - "
                                        f"(~!: {suffix_msg})\n"
                                    )
                                else:
                                    # Not an error suffix, don't change
                                    continue
                            lines[i] = new_line
                            updated = True
                            break

            if not updated:
                return False

            # Write atomically
            action = "Remove" if new_suffix_type == "remove" else "Reject"
            write_changespec_atomic(
                project_file,
                "".join(lines),
                f"{action} suffix from commit entry {entry_id} for {cl_name}",
            )
            return True
    except Exception:
        return False
