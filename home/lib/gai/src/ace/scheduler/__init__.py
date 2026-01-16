"""Scheduler utilities for checking ChangeSpec status updates.

This package provides shared utilities used by the gai axe scheduler for:
- Checking CL submission and comment status
- Starting and monitoring hooks in the background
- Detecting zombie and stale hooks
- Managing mentor workflows
- Cleaning up stale RUNNING entries
"""

from .orphan_cleanup import cleanup_orphaned_workspace_claims
from .stale_running_cleanup import cleanup_stale_running_entries

__all__ = [
    "cleanup_orphaned_workspace_claims",
    "cleanup_stale_running_entries",
]
