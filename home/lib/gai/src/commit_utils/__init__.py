"""Utility functions for managing COMMITS entries in ChangeSpecs.

This package provides functions for:
- Adding commit entries (entries.py)
- Modifying existing entries (modifiers.py)
- Workspace and diff management (workspace.py)
"""

from commit_utils.entries import (
    add_commit_entry,
    add_proposed_commit_entry,
    get_next_commit_number,
)
from commit_utils.modifiers import (
    mark_proposal_broken,
    reject_all_new_proposals,
    reject_proposals_and_set_status_atomic,
    update_commit_entry_suffix,
)
from commit_utils.workspace import (
    apply_diff_to_workspace,
    apply_diffs_to_workspace,
    clean_workspace,
    run_bb_hg_clean,
    save_diff,
)

__all__ = [
    "add_commit_entry",
    "add_proposed_commit_entry",
    "apply_diff_to_workspace",
    "apply_diffs_to_workspace",
    "clean_workspace",
    "get_next_commit_number",
    "mark_proposal_broken",
    "reject_all_new_proposals",
    "reject_proposals_and_set_status_atomic",
    "run_bb_hg_clean",
    "save_diff",
    "update_commit_entry_suffix",
]
