"""Comments operations - tracking Critique code review comments."""

from .core import (
    comment_needs_crs,
    get_comments_file_path,
    is_comments_suffix_stale,
    is_timestamp_suffix,
)
from .operations import (
    add_comment_entry,
    clear_comment_suffix,
    remove_comment_entry,
    set_comment_suffix,
    update_changespec_comments_field,
    update_comment_suffix_type,
)

__all__ = [
    # core.py
    "comment_needs_crs",
    "get_comments_file_path",
    "is_comments_suffix_stale",
    "is_timestamp_suffix",
    # operations.py
    "add_comment_entry",
    "clear_comment_suffix",
    "remove_comment_entry",
    "set_comment_suffix",
    "update_changespec_comments_field",
    "update_comment_suffix_type",
]
