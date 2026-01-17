"""Background command state management for the ace TUI.

This module handles all state persistence for background commands,
enabling gai ace to run arbitrary shell commands in the background
and track their output.
"""

import json
import os
import signal
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from gai_utils import EASTERN_TZ

# State directory location
BGCMD_STATE_DIR = Path.home() / ".gai" / "axe" / "bgcmd"

# Number of slots available (1-9)
MAX_SLOTS = 9


@dataclass
class BackgroundCommandInfo:
    """Information about a running background command."""

    command: str
    project: str
    workspace_num: int
    workspace_dir: str
    started_at: str


def _get_slot_dir(slot: int) -> Path:
    """Get the state directory for a specific slot.

    Args:
        slot: Slot number (1-9).

    Returns:
        Path to the slot directory.
    """
    return BGCMD_STATE_DIR / str(slot)


def _ensure_slot_dir(slot: int) -> Path:
    """Ensure the slot directory exists.

    Args:
        slot: Slot number (1-9).

    Returns:
        Path to the slot directory.
    """
    slot_dir = _get_slot_dir(slot)
    slot_dir.mkdir(parents=True, exist_ok=True)
    return slot_dir


def _read_pid(slot: int) -> int | None:
    """Read the PID for a slot.

    Args:
        slot: Slot number (1-9).

    Returns:
        PID as integer, or None if not found.
    """
    pid_file = _get_slot_dir(slot) / "pid"
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return None


def _write_pid(slot: int, pid: int) -> None:
    """Write PID for a slot.

    Args:
        slot: Slot number (1-9).
        pid: Process ID.
    """
    _ensure_slot_dir(slot)
    pid_file = _get_slot_dir(slot) / "pid"
    pid_file.write_text(str(pid))


def _remove_pid(slot: int) -> None:
    """Remove PID file for a slot.

    Args:
        slot: Slot number (1-9).
    """
    pid_file = _get_slot_dir(slot) / "pid"
    try:
        pid_file.unlink()
    except OSError:
        pass


def _is_process_running(pid: int) -> bool:
    """Check if a process is running.

    Args:
        pid: Process ID.

    Returns:
        True if process is running, False otherwise.
    """
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def is_slot_running(slot: int) -> bool:
    """Check if a slot has a running background command.

    Args:
        slot: Slot number (1-9).

    Returns:
        True if the slot has a running process.
    """
    pid = _read_pid(slot)
    if pid is None:
        return False
    return _is_process_running(pid)


def get_slot_info(slot: int) -> BackgroundCommandInfo | None:
    """Get information about a slot's background command.

    Args:
        slot: Slot number (1-9).

    Returns:
        BackgroundCommandInfo or None if not found.
    """
    info_file = _get_slot_dir(slot) / "info.json"
    if not info_file.exists():
        return None
    try:
        with open(info_file) as f:
            data = json.load(f)
        return BackgroundCommandInfo(**data)
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def _write_info(slot: int, info: BackgroundCommandInfo) -> None:
    """Write info.json for a slot.

    Args:
        slot: Slot number (1-9).
        info: Command information.
    """
    _ensure_slot_dir(slot)
    info_file = _get_slot_dir(slot) / "info.json"
    with open(info_file, "w") as f:
        json.dump(asdict(info), f, indent=2)


def read_slot_output_tail(slot: int, lines: int = 1000) -> str:
    """Read the last N lines of a slot's output log.

    Args:
        slot: Slot number (1-9).
        lines: Number of lines to read (default: 1000).

    Returns:
        String containing the last N lines.
    """
    from collections import deque

    output_file = _get_slot_dir(slot) / "output.log"
    if not output_file.exists():
        return ""

    try:
        with open(output_file) as f:
            last_lines = deque(f, maxlen=lines)
        return "".join(last_lines)
    except OSError:
        return ""


def clear_slot_output(slot: int) -> None:
    """Clear the output log for a slot.

    Args:
        slot: Slot number (1-9).
    """
    output_file = _get_slot_dir(slot) / "output.log"
    if output_file.exists():
        try:
            output_file.write_text("")
        except OSError:
            pass


def get_running_slots() -> list[int]:
    """Get list of slots that have running background commands.

    Returns:
        List of slot numbers with running processes.
    """
    running = []
    for slot in range(1, MAX_SLOTS + 1):
        if is_slot_running(slot):
            running.append(slot)
    return running


def find_first_available_slot() -> int | None:
    """Find the first available slot for a new background command.

    Returns:
        First available slot number (1-9), or None if all slots are in use.
    """
    for slot in range(1, MAX_SLOTS + 1):
        if not is_slot_running(slot):
            return slot
    return None


def start_background_command(
    slot: int,
    command: str,
    project: str,
    workspace_num: int,
    workspace_dir: str,
) -> int | None:
    """Start a background command in a slot.

    Args:
        slot: Slot number (1-9).
        command: Shell command to run.
        project: Project name.
        workspace_num: Workspace number.
        workspace_dir: Workspace directory path.

    Returns:
        PID of the started process, or None on failure.
    """
    # Ensure slot directory exists
    slot_dir = _ensure_slot_dir(slot)
    output_file = slot_dir / "output.log"

    # Clear any old output
    output_file.write_text("")

    # Create info
    info = BackgroundCommandInfo(
        command=command,
        project=project,
        workspace_num=workspace_num,
        workspace_dir=workspace_dir,
        started_at=datetime.now(EASTERN_TZ).isoformat(),
    )
    _write_info(slot, info)

    try:
        # Open output file for writing
        with open(output_file, "w") as out_f:
            # Start the process with the workspace directory as cwd
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=workspace_dir,
                stdout=out_f,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,  # Detach from terminal
            )

        # Write PID
        _write_pid(slot, process.pid)
        return process.pid

    except Exception:
        return None


def stop_background_command(slot: int) -> bool:
    """Stop a background command in a slot.

    Args:
        slot: Slot number (1-9).

    Returns:
        True if successfully stopped, False otherwise.
    """
    pid = _read_pid(slot)
    if pid is None:
        return False

    if not _is_process_running(pid):
        # Already stopped, clean up
        _remove_pid(slot)
        return True

    try:
        # Send SIGTERM to the process group
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        _remove_pid(slot)
        return True
    except (OSError, ProcessLookupError):
        # Process already gone
        _remove_pid(slot)
        return True
