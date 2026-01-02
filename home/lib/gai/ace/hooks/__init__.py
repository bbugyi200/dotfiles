"""Hook execution utilities for running and tracking ChangeSpec hooks.

This package provides utilities for:
- Managing hook status lines and timestamps
- Running hooks in the background
- Checking hook completion status
- Managing test target hooks
- Setting and clearing hook suffixes
"""

from gai_utils import generate_timestamp

from .core import (
    calculate_duration_from_timestamps,
    entry_has_running_hooks,
    format_duration,
    format_timestamp_display,
    get_entries_needing_hook_run,
    get_history_entry_by_id,
    get_hook_age_seconds,
    get_hook_file_age_seconds_from_timestamp,
    get_last_accepted_history_entry_id,
    get_last_history_entry,
    get_last_history_entry_id,
    has_running_hooks,
    hook_has_any_running_status,
    hook_needs_run,
    is_hook_zombie,
    is_process_running,
    is_proposal_entry,
    is_suffix_stale,
    is_timestamp_suffix,
    kill_running_processes_for_hooks,
)
from .execution import (
    check_hook_completion,
    get_hook_output_path,
    merge_hook_updates,
    start_hook_background,
    update_changespec_hooks_field,
    update_hook_status_line_suffix_type,
)
from .queries import (
    add_hook_to_changespec,
    add_test_target_hooks_to_changespec,
    clear_failed_test_target_hook_status,
    clear_hook_suffix,
    get_failing_hook_entries_for_fix,
    get_failing_hook_entries_for_summarize,
    get_failing_hooks_for_fix,
    get_failing_hooks_for_summarize,
    get_failing_test_target_hooks,
    get_test_target_from_hook,
    has_failing_hooks_for_fix,
    has_failing_test_target_hooks,
    set_hook_suffix,
)

__all__ = [
    # Core functions
    "calculate_duration_from_timestamps",
    "entry_has_running_hooks",
    "format_duration",
    "format_timestamp_display",
    "generate_timestamp",
    "get_entries_needing_hook_run",
    "get_history_entry_by_id",
    "get_hook_age_seconds",
    "get_hook_file_age_seconds_from_timestamp",
    "get_last_accepted_history_entry_id",
    "get_last_history_entry",
    "get_last_history_entry_id",
    "has_running_hooks",
    "hook_has_any_running_status",
    "hook_needs_run",
    "is_hook_zombie",
    "is_process_running",
    "is_proposal_entry",
    "is_suffix_stale",
    "is_timestamp_suffix",
    "kill_running_processes_for_hooks",
    # Operations functions
    "add_hook_to_changespec",
    "add_test_target_hooks_to_changespec",
    "check_hook_completion",
    "clear_failed_test_target_hook_status",
    "clear_hook_suffix",
    "get_failing_hook_entries_for_fix",
    "get_failing_hook_entries_for_summarize",
    "get_failing_hooks_for_fix",
    "get_failing_hooks_for_summarize",
    "get_failing_test_target_hooks",
    "get_hook_output_path",
    "get_test_target_from_hook",
    "has_failing_hooks_for_fix",
    "merge_hook_updates",
    "has_failing_test_target_hooks",
    "set_hook_suffix",
    "start_hook_background",
    "update_changespec_hooks_field",
    "update_hook_status_line_suffix_type",
]
