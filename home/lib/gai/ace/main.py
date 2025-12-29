"""Main workflow for the ace subcommand.

This module re-exports the AceWorkflow class for backward compatibility.
The actual implementation has been refactored into separate modules:
- workflow.py: Main AceWorkflow class
- query/: Query language parsing and evaluation
- operations.py: ChangeSpec operations
"""

from .workflow import AceWorkflow

__all__ = ["AceWorkflow"]
