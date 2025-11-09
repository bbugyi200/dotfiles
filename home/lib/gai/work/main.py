"""Main workflow for the work subcommand.

This module re-exports the WorkWorkflow class for backward compatibility.
The actual implementation has been refactored into separate modules:
- workflow.py: Main WorkWorkflow class
- filters.py: Filter validation and application
- status.py: Status operations
- operations.py: ChangeSpec operations
"""

from .workflow import WorkWorkflow

__all__ = ["WorkWorkflow"]
