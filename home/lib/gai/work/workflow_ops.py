"""Workflow-specific operations for ChangeSpecs."""

import os
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from status_state_machine import transition_changespec_status

from .changespec import ChangeSpec, find_all_changespecs

# Import workflow runners from workflows subpackage
from .workflows import (
    run_crs_workflow,
    run_fix_tests_workflow,
    run_qa_workflow,
    run_tdd_feature_workflow,
)

# Re-export workflow runners for backward compatibility
__all__ = [
    "run_crs_workflow",
    "run_fix_tests_workflow",
    "run_qa_workflow",
    "run_tdd_feature_workflow",
]
