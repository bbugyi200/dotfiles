"""Axe scheduler package for gai.

This package provides schedule-based ChangeSpec monitoring as an alternative
to the traditional gai loop command.
"""

from .core import AxeScheduler
from .process import (
    get_axe_pid,
    get_axe_status,
    is_axe_running,
    start_axe_daemon,
    stop_axe_daemon,
)
from .runner_pool import RunnerPool
from .state import (
    AxeMetrics,
    AxeStatus,
    CycleResult,
    read_cycle_result,
    read_errors,
    read_metrics,
    read_pid_file,
    read_status,
)

__all__ = [
    # Core
    "AxeScheduler",
    # Process control
    "get_axe_pid",
    "get_axe_status",
    "is_axe_running",
    "start_axe_daemon",
    "stop_axe_daemon",
    # Runner pool
    "RunnerPool",
    # State reading (for TUI)
    "AxeMetrics",
    "AxeStatus",
    "CycleResult",
    "read_cycle_result",
    "read_errors",
    "read_metrics",
    "read_pid_file",
    "read_status",
]
