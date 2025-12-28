"""Workflow background execution for the loop command (crs and fix-hook).

This package provides functionality to start, monitor, and complete
background workflows for the loop command.
"""

from .completer import check_and_complete_workflows
from .monitor import WORKFLOW_COMPLETE_MARKER
from .starter import LogCallback, start_stale_workflows

__all__ = [
    "LogCallback",
    "WORKFLOW_COMPLETE_MARKER",
    "check_and_complete_workflows",
    "start_stale_workflows",
]
