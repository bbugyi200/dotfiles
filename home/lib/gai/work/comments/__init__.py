"""Comments operations - tracking Critique code review comments."""

from .core import (
    CRS_STALE_THRESHOLD_SECONDS,
    comment_needs_crs,
    generate_comments_timestamp,
    get_comments_directory,
    get_comments_file_path,
    is_comments_suffix_stale,
    is_timestamp_suffix,
)
from .operations import (
    add_comment_entry,
    clear_comment_suffix,
    remove_comment_entry,
    save_critique_comments,
    set_comment_suffix,
    update_changespec_comments_field,
)

__all__ = [
    # core.py
    "CRS_STALE_THRESHOLD_SECONDS",
    "comment_needs_crs",
    "generate_comments_timestamp",
    "get_comments_directory",
    "get_comments_file_path",
    "is_comments_suffix_stale",
    "is_timestamp_suffix",
    # operations.py
    "add_comment_entry",
    "clear_comment_suffix",
    "remove_comment_entry",
    "save_critique_comments",
    "set_comment_suffix",
    "update_changespec_comments_field",
]
