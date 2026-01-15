"""Widgets for the ace TUI."""

from .agent_detail import AgentDetail
from .agent_info_panel import AgentInfoPanel
from .agent_list import AgentList
from .axe_dashboard import AxeDashboard
from .axe_info_panel import AxeInfoPanel
from .changespec_detail import ChangeSpecDetail, SearchQueryPanel
from .changespec_info_panel import ChangeSpecInfoPanel
from .changespec_list import ChangeSpecList
from .hint_input_bar import HintInputBar
from .keybinding_footer import KeybindingFooter
from .prompt_input_bar import PromptInputBar
from .tab_bar import TabBar

__all__ = [
    "AgentDetail",
    "AgentInfoPanel",
    "AgentList",
    "AxeDashboard",
    "AxeInfoPanel",
    "ChangeSpecDetail",
    "ChangeSpecInfoPanel",
    "ChangeSpecList",
    "HintInputBar",
    "KeybindingFooter",
    "PromptInputBar",
    "SearchQueryPanel",
    "TabBar",
]
