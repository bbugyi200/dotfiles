"""Shared type hints for hint action mixins."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# Import ChangeSpec unconditionally since it's used as a type annotation
# in attribute declarations (not just in function signatures)
from ....changespec import ChangeSpec


class HintMixinBase:
    """Base class providing shared type hints for all hint action mixins.

    These type hints declare attributes that are defined at runtime by AceApp.
    All hint action sub-mixins should inherit from this class.
    """

    # ChangeSpec state
    changespecs: list[ChangeSpec]
    current_idx: int

    # Hint mode state
    _hint_mode_active: bool
    _hint_mode_hints_for: str | None
    _hint_mappings: dict[int, str]
    _hook_hint_to_idx: dict[int, int]
    _hint_to_entry_id: dict[int, str]
    _hint_changespec_name: str

    # Accept mode state
    _accept_mode_active: bool
    _accept_last_base: str | None

    # Failed hooks state
    _failed_hooks_targets: list[str]
    _failed_hooks_file_path: str | None
