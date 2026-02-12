"""Handler functions for the work subcommand."""

from .edit_hooks import handle_edit_hooks
from .mail import handle_mail
from .reword import handle_reword
from .show_diff import handle_show_diff
from .workflow_handlers import (
    handle_run_crs_workflow,
    handle_run_fix_hook_workflow,
    handle_run_workflow,
)

__all__ = [
    # Workflow handlers
    "handle_run_workflow",
    "handle_run_fix_hook_workflow",
    "handle_run_crs_workflow",
    # Tool handlers
    "handle_show_diff",
    "handle_edit_hooks",
    "handle_mail",
    "handle_reword",
]
