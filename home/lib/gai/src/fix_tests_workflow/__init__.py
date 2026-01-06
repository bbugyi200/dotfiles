"""
Fix-tests workflow package.

This package contains the new fix-tests workflow that uses planning, editor, and research agents
with persistent blackboard files to fix failing tests.
"""

from .main import FixTestsWorkflow

__all__ = ["FixTestsWorkflow"]
