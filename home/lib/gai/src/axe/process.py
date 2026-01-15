"""Process control for gai axe scheduler.

This module provides functions for gai ace to start, stop, and monitor
the gai axe daemon process.
"""

import os
import shutil
import signal
import subprocess

from ace.hooks.processes import is_process_running

from .state import (
    AXE_STATE_DIR,
    read_pid_file,
    read_status,
    remove_pid_file,
)


def is_axe_running() -> bool:
    """Check if an axe daemon is currently running.

    Returns:
        True if axe is running, False otherwise.
    """
    pid = read_pid_file()
    if pid is None:
        return False

    if not is_process_running(pid):
        # Stale PID file - clean it up
        remove_pid_file()
        return False

    return True


def start_axe_daemon(
    full_check_interval: int = 300,
    hook_interval: int = 1,
    max_runners: int = 5,
    query: str = "",
    zombie_timeout: int = 7200,
) -> int | None:
    """Start axe as a background daemon process.

    Args:
        full_check_interval: Full check interval in seconds (default: 300).
        hook_interval: Hook check interval in seconds (default: 1).
        max_runners: Maximum concurrent runners (default: 5).
        query: Query string for filtering ChangeSpecs (default: "").
        zombie_timeout: Zombie detection timeout in seconds (default: 7200).

    Returns:
        PID of started process, or None if already running or failed to start.
    """
    # Check if already running
    if is_axe_running():
        return None

    # Find gai executable on PATH
    gai_cmd = shutil.which("gai")
    if gai_cmd is None:
        return None

    # Build command
    cmd = [
        gai_cmd,
        "axe",
        "--full-check-interval",
        str(full_check_interval),
        "--hook-interval",
        str(hook_interval),
        "-r",
        str(max_runners),
        "--zombie-timeout",
        str(zombie_timeout),
    ]
    if query:
        cmd.extend(["-q", query])

    # Ensure log directory exists
    log_dir = AXE_STATE_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "axe.log"

    # Start as daemon (detached from terminal)
    with open(log_file, "a") as log:
        process = subprocess.Popen(
            cmd,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # Detach from terminal
        )

    return process.pid


def stop_axe_daemon() -> bool:
    """Stop the running axe daemon.

    Sends SIGTERM for graceful shutdown.

    Returns:
        True if process was stopped, False if not running.
    """
    pid = read_pid_file()
    if pid is None:
        return False

    if not is_process_running(pid):
        remove_pid_file()
        return False

    try:
        # Send SIGTERM for graceful shutdown
        os.kill(pid, signal.SIGTERM)
        return True
    except (ProcessLookupError, PermissionError):
        remove_pid_file()
        return False


def get_axe_status() -> dict | None:
    """Get current axe daemon status for TUI display.

    Returns:
        Status dict with key metrics, or None if not running.
    """
    pid = read_pid_file()
    if pid is None:
        return None

    if not is_process_running(pid):
        remove_pid_file()
        return None

    status = read_status()
    if status is None:
        # Process is running but no status file yet
        return {"pid": pid, "status": "running (initializing)"}

    return {
        "pid": status.pid,
        "status": status.status,
        "uptime_seconds": status.uptime_seconds,
        "current_runners": status.current_runners,
        "max_runners": status.max_runners,
        "last_full_cycle": status.last_full_cycle,
        "next_full_cycle": status.next_full_cycle,
        "total_changespecs": status.total_changespecs,
        "filtered_changespecs": status.filtered_changespecs,
        "query": status.query,
    }


def get_axe_pid() -> int | None:
    """Get the PID of the running axe daemon.

    Returns:
        PID if running, None otherwise.
    """
    pid = read_pid_file()
    if pid is None:
        return None

    if not is_process_running(pid):
        remove_pid_file()
        return None

    return pid
