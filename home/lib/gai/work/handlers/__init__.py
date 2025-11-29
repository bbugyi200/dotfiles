"""Handler functions for the work subcommand."""

from .tool_handlers import (
    handle_findreviewers,
    handle_mail,
    handle_run_query,
    handle_show_diff,
    handle_tricorder,
)
from .workflow_handlers import (
    handle_run_crs_workflow,
    handle_run_fix_tests_workflow,
    handle_run_qa_workflow,
    handle_run_tdd_feature_workflow,
    handle_run_workflow,
)

__all__ = [
    # Workflow handlers
    "handle_run_workflow",
    "handle_run_tdd_feature_workflow",
    "handle_run_qa_workflow",
    "handle_run_fix_tests_workflow",
    "handle_run_crs_workflow",
    # Tool handlers
    "handle_show_diff",
    "handle_tricorder",
    "handle_findreviewers",
    "handle_mail",
    "handle_run_query",
]
