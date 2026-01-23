"""Hint tracking for ChangeSpec detail display."""

from typing import NamedTuple


class HintTracker(NamedTuple):
    """Tracks hint state during section building."""

    counter: int
    mappings: dict[int, str]
    hook_hint_to_idx: dict[int, int]
    hint_to_entry_id: dict[int, str]
    mentor_hint_to_info: dict[
        int, tuple[str, str]
    ]  # hint -> (mentor_name, profile_name)
