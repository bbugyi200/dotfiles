"""Type definitions and base class for navigation mixin."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ....changespec import ChangeSpec
    from ....query.types import QueryExpr
    from ....query_history import QueryHistoryStacks
    from ...bgcmd import BackgroundCommandInfo
    from ...changespec_history import ChangeSpecHistoryStacks
    from ...models import Agent

# Type alias for axe view: "axe" for daemon view, int for bgcmd slot (1-9)
AxeViewType = Literal["axe"] | int

# Type alias for tab names
TabName = Literal["changespecs", "agents", "axe"]


class NavigationMixinBase:
    """Base class with type hints for attributes accessed from AceApp."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    current_idx: int
    current_tab: TabName
    hooks_collapsed: bool
    commits_collapsed: bool
    mentors_collapsed: bool
    _agents: list[Agent]
    _fold_mode_active: bool
    _changespecs_last_idx: int
    _agents_last_idx: int
    _axe_pinned_to_bottom: bool
    _ancestor_mode_active: bool
    _child_mode_active: bool
    _sibling_mode_active: bool
    _child_key_buffer: str
    _ancestor_keys: dict[str, str]
    _children_keys: dict[str, str]
    _sibling_keys: dict[str, str]
    _all_changespecs: list[ChangeSpec]
    _query_history: QueryHistoryStacks
    _changespec_history: ChangeSpecHistoryStacks
    query_string: str
    parsed_query: QueryExpr
    _axe_current_view: AxeViewType
    _bgcmd_slots: list[tuple[int, BackgroundCommandInfo]]
