"""Navigation mixin for the ace TUI app."""

from ._advanced import AdvancedNavigationMixin
from ._basic import BasicNavigationMixin
from ._tree import TreeNavigationMixin
from ._types import AxeViewType, TabName


class NavigationMixin(
    BasicNavigationMixin,
    TreeNavigationMixin,
    AdvancedNavigationMixin,
):
    """Mixin providing navigation, scrolling, and fold mode actions."""

    pass


__all__ = [
    "AxeViewType",
    "NavigationMixin",
    "TabName",
]
