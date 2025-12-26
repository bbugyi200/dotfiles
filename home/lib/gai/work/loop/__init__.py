"""Loop workflow for continuously checking ChangeSpec status updates.

This package provides the LoopWorkflow class for running continuous loops that:
- Check CL submission and comment status
- Start and monitor hooks in the background
- Detect zombie and stale hooks
"""

from .core import (
    ZOMBIE_CHECK_INTERVAL_SECONDS,
    LoopWorkflow,
)

__all__ = [
    "ZOMBIE_CHECK_INTERVAL_SECONDS",
    "LoopWorkflow",
]
