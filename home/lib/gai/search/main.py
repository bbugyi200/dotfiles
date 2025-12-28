"""Main workflow for the search subcommand.

This module re-exports the SearchWorkflow class for backward compatibility.
The actual implementation has been refactored into separate modules:
- workflow.py: Main SearchWorkflow class
- query/: Query language parsing and evaluation
- operations.py: ChangeSpec operations
"""

from .workflow import SearchWorkflow

__all__ = ["SearchWorkflow"]
