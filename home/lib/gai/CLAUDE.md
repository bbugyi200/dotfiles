# Agent Prompt Guidelines

## File Size Limits

**CRITICAL**: When a Python file exceeds 750 lines, break it into a package with multiple modules. NEVER compress docstrings to fit the limit.

Group related functions logically, update `__init__.py` for backward compatibility, and split test files along the same module boundaries.
