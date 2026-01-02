"""Handler functions for the work subcommand."""

from .tool_handlers import (
    handle_edit_hooks,
    handle_findreviewers,
    handle_mail,
    handle_reword,
    handle_run_query,
    handle_show_diff,
)
from .workflow_handlers import (
    handle_run_crs_workflow,
    handle_run_fix_hook_workflow,
    handle_run_fix_tests_workflow,
    handle_run_qa_workflow,
    handle_run_workflow,
)

__all__ = [
    # Workflow handlers
    "handle_run_workflow",
    "handle_run_qa_workflow",
    "handle_run_fix_hook_workflow",
    "handle_run_fix_tests_workflow",
    "handle_run_crs_workflow",
    # Tool handlers
    "handle_show_diff",
    "handle_edit_hooks",
    "handle_findreviewers",
    "handle_mail",
    "handle_reword",
    "handle_run_query",
]
