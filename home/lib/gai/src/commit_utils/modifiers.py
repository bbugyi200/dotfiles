"""Functions for modifying existing COMMITS entries in ChangeSpecs."""

import re

from ace.changespec import changespec_lock, write_changespec_atomic

# Ready to mail suffix constant
_READY_TO_MAIL_SUFFIX = " - (!: READY TO MAIL)"


def reject_proposals_and_set_status_atomic(
    project_file: str,
    cl_name: str,
    final_status: str,
) -> bool:
    """Reject all new proposals and set STATUS in a single atomic write.

    This combines reject_all_new_proposals and status transition into one
    atomic operation. Use this when you want to:
    - Reject all new proposals
    - Set status to "Mailed" or add READY TO MAIL suffix
    All in one lock acquisition and file write.

    Args:
        project_file: Path to the project file.
        cl_name: The CL name to update.
        final_status: The final status to set. Should be either:
            - "Mailed" to set status directly to Mailed
            - None or empty to add READY TO MAIL suffix to current status

    Returns:
        True if successful, False otherwise.
    """
    try:
        with changespec_lock(project_file):
            with open(project_file, encoding="utf-8") as f:
                lines = f.readlines()

            # Track state while parsing
            in_target_changespec = False
            in_commits = False
            rejected_count = 0
            status_line_idx: int | None = None
            current_status: str | None = None

            for i, line in enumerate(lines):
                if line.startswith("NAME: "):
                    current_name = line[6:].strip()
                    in_target_changespec = current_name == cl_name
                    in_commits = False
                elif in_target_changespec:
                    if line.startswith("STATUS:"):
                        # Capture the status line index and current value
                        status_line_idx = i
                        current_status = line[7:].strip()
                        in_commits = False
                    elif line.startswith("COMMITS:"):
                        in_commits = True
                    elif line.startswith(
                        (
                            "NAME:",
                            "DESCRIPTION:",
                            "PARENT:",
                            "CL:",
                            "TEST TARGETS:",
                            "KICKSTART:",
                            "HOOKS:",
                            "COMMENTS:",
                            "MENTORS:",
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

            # Must have found the status line
            if status_line_idx is None or current_status is None:
                return False

            # Update the status line based on final_status
            if final_status == "Mailed":
                # Set status directly to "Mailed"
                new_status = "Mailed"
            else:
                # Add READY TO MAIL suffix if not already present
                if "(!: READY TO MAIL)" in current_status:
                    new_status = current_status  # Already has suffix
                else:
                    new_status = current_status + _READY_TO_MAIL_SUFFIX

            lines[status_line_idx] = f"STATUS: {new_status}\n"

            # Write atomically
            write_changespec_atomic(
                project_file,
                "".join(lines),
                f"Reject {rejected_count} proposal(s) and set status to "
                f"'{new_status}' for {cl_name}",
            )
            return True
    except Exception:
        return False


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


def mark_proposal_broken(
    project_file: str,
    cl_name: str,
    entry_id: str,
) -> bool:
    """Mark a proposal as broken by changing (!: NEW PROPOSAL) to (~!: BROKEN PROPOSAL).

    This is called when a proposal's diff fails to apply to a workspace.
    Broken proposals are skipped in future hook runs.

    Args:
        project_file: Path to the project file.
        cl_name: The CL name to update.
        entry_id: The proposal entry ID (e.g., "2a").

    Returns:
        True if successful, False otherwise.
    """
    try:
        with changespec_lock(project_file):
            with open(project_file, encoding="utf-8") as f:
                lines = f.readlines()

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
                            "MENTORS:",
                        )
                    ):
                        in_commits = False
                        if line.startswith("NAME:"):
                            in_target_changespec = False
                    elif in_commits:
                        stripped = line.strip()
                        # Match: (Na) Note text - (!: NEW PROPOSAL)
                        entry_match = re.match(
                            rf"^\(({re.escape(entry_id)})\)\s+(.+?)\s+-\s+\(!:\s*NEW PROPOSAL\)$",
                            stripped,
                        )
                        if entry_match:
                            matched_id = entry_match.group(1)
                            note_text = entry_match.group(2)
                            leading_ws = line[: len(line) - len(line.lstrip())]
                            # Change to (~!: BROKEN PROPOSAL)
                            new_line = (
                                f"{leading_ws}({matched_id}) {note_text} - "
                                f"(~!: BROKEN PROPOSAL)\n"
                            )
                            lines[i] = new_line
                            updated = True
                            break

            if not updated:
                return False

            write_changespec_atomic(
                project_file,
                "".join(lines),
                f"Mark proposal {entry_id} as broken for {cl_name}",
            )
            return True
    except Exception:
        return False
