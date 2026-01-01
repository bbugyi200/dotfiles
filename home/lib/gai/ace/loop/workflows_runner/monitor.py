"""Workflow completion detection logic for the loop command."""

import os
import re

from ...changespec import ChangeSpec
from ...hooks.core import is_proposal_entry

# Workflow completion marker (same pattern as hooks)
WORKFLOW_COMPLETE_MARKER = "===WORKFLOW_COMPLETE=== PROPOSAL_ID: "


def check_workflow_completion(output_path: str) -> tuple[bool, str | None, int | None]:
    """Check if a workflow has completed by reading its output file.

    Args:
        output_path: Path to the workflow output file.

    Returns:
        Tuple of (completed, proposal_id, exit_code).
    """
    if not os.path.exists(output_path):
        return (False, None, None)

    try:
        with open(output_path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return (False, None, None)

    marker_pos = content.rfind(WORKFLOW_COMPLETE_MARKER)
    if marker_pos == -1:
        return (False, None, None)

    # Parse: PROPOSAL_ID: <id> EXIT_CODE: <code>
    try:
        after_marker = content[marker_pos + len(WORKFLOW_COMPLETE_MARKER) :].strip()
        parts = after_marker.split()
        proposal_id = parts[0] if parts and parts[0] != "None" else None
        exit_code = int(parts[2]) if len(parts) > 2 else 1
    except (ValueError, IndexError):
        return (True, None, 1)

    return (True, proposal_id, exit_code)


def get_running_crs_workflows(changespec: ChangeSpec) -> list[tuple[str, str]]:
    """Get running CRS workflows for a ChangeSpec.

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        List of (reviewer_type, suffix) tuples for running CRS workflows.
    """
    running: list[tuple[str, str]] = []
    if changespec.comments:
        for entry in changespec.comments:
            if entry.reviewer in ("critique", "critique:me") and entry.suffix:
                # Check for new format: crs-YYmmdd_HHMMSS
                if re.match(r"^crs-\d{6}_\d{6}$", entry.suffix):
                    running.append((entry.reviewer, entry.suffix))
                # Legacy format: YYmmdd_HHMMSS (13 chars with underscore)
                elif re.match(r"^\d{6}_\d{6}$", entry.suffix):
                    running.append((entry.reviewer, entry.suffix))
    return running


def get_running_fix_hook_workflows(
    changespec: ChangeSpec,
) -> list[tuple[str, str, str, str | None]]:
    """Get running fix-hook workflows for a ChangeSpec.

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        List of (hook_command, timestamp, entry_id, summary) tuples for running fix-hook workflows.
        The timestamp is extracted from the suffix (e.g., "fix_hook-12345-251230_151429" -> "251230_151429").
    """
    running: list[tuple[str, str, str, str | None]] = []
    if changespec.hooks:
        for hook in changespec.hooks:
            if not hook.status_lines:
                continue
            for sl in hook.status_lines:
                # Only non-proposal entries are fix-hook workflows
                if not sl.suffix or is_proposal_entry(sl.commit_entry_num):
                    continue
                # Check for suffix_type to ensure it's a running agent
                if sl.suffix_type != "running_agent":
                    continue
                # Check for new format with PID: fix_hook-<PID>-YYmmdd_HHMMSS
                pid_match = re.match(r"^fix_hook-\d+-(\d{6}_\d{6})$", sl.suffix)
                if pid_match:
                    running.append(
                        (
                            hook.command,
                            pid_match.group(1),
                            sl.commit_entry_num,
                            sl.summary,
                        )
                    )
                    continue
                # Check for format without PID: fix_hook-YYmmdd_HHMMSS
                no_pid_match = re.match(r"^fix_hook-(\d{6}_\d{6})$", sl.suffix)
                if no_pid_match:
                    running.append(
                        (
                            hook.command,
                            no_pid_match.group(1),
                            sl.commit_entry_num,
                            sl.summary,
                        )
                    )
                    continue
                # Legacy format: YYmmdd_HHMMSS (13 chars with underscore)
                legacy_match = re.match(r"^(\d{6}_\d{6})$", sl.suffix)
                if legacy_match:
                    running.append(
                        (
                            hook.command,
                            legacy_match.group(1),
                            sl.commit_entry_num,
                            sl.summary,
                        )
                    )
    return running


def get_running_summarize_hook_workflows(
    changespec: ChangeSpec,
) -> list[tuple[str, str, str]]:
    """Get running summarize-hook workflows for a ChangeSpec.

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        List of (hook_command, timestamp, entry_id) tuples for running summarize-hook workflows.
        The timestamp is extracted from the suffix (e.g., "summarize_hook-12345-251230_151429" -> "251230_151429").
    """
    running: list[tuple[str, str, str]] = []
    if changespec.hooks:
        for hook in changespec.hooks:
            if not hook.status_lines:
                continue
            for sl in hook.status_lines:
                # Summarize workflows can run on ANY entry (proposal or non-proposal)
                if not sl.suffix:
                    continue
                # Check for suffix_type to ensure it's a running agent
                if sl.suffix_type != "running_agent":
                    continue
                # Check for new format with PID: summarize_hook-<PID>-YYmmdd_HHMMSS
                pid_match = re.match(r"^summarize_hook-\d+-(\d{6}_\d{6})$", sl.suffix)
                if pid_match:
                    running.append(
                        (hook.command, pid_match.group(1), sl.commit_entry_num)
                    )
                    continue
                # Check for format without PID: summarize_hook-YYmmdd_HHMMSS
                no_pid_match = re.match(r"^summarize_hook-(\d{6}_\d{6})$", sl.suffix)
                if no_pid_match:
                    running.append(
                        (hook.command, no_pid_match.group(1), sl.commit_entry_num)
                    )
    return running
