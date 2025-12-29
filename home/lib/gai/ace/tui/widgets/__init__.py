"""Widgets for the ace TUI."""

from .changespec_detail import ChangeSpecDetail, SearchQueryPanel
from .changespec_info_panel import ChangeSpecInfoPanel
from .changespec_list import ChangeSpecList
from .keybinding_footer import KeybindingFooter

__all__ = [
    "ChangeSpecDetail",
    "ChangeSpecInfoPanel",
    "ChangeSpecList",
    "KeybindingFooter",
    "SearchQueryPanel",
]
