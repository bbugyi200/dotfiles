"""Comments operations - tracking Critique code review comments."""

from gai_utils import generate_timestamp

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


# Backward compatibility alias
def generate_comments_timestamp() -> str:
    """Backward compatibility alias for generate_timestamp."""
    return generate_timestamp()


__all__ = [
    # core.py
    "comment_needs_crs",
    "generate_comments_timestamp",
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
