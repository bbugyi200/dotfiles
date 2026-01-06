"""Widgets for the ace TUI."""

from .changespec_detail import ChangeSpecDetail, SearchQueryPanel
from .changespec_info_panel import ChangeSpecInfoPanel
from .changespec_list import ChangeSpecList
from .hint_input_bar import HintInputBar
from .keybinding_footer import KeybindingFooter
from .saved_queries_panel import SavedQueriesPanel

__all__ = [
    "ChangeSpecDetail",
    "ChangeSpecInfoPanel",
    "ChangeSpecList",
    "HintInputBar",
    "KeybindingFooter",
    "SavedQueriesPanel",
    "SearchQueryPanel",
]
