"""Agent list widget for the ace TUI."""

from typing import Any

from rich.text import Text
from textual.message import Message
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from ..models.agent import Agent, AgentType

# Color mapping for agent types
_AGENT_TYPE_COLORS: dict[AgentType, str] = {
    AgentType.RUNNING: "#87AFFF",  # Blue
    AgentType.FIX_HOOK: "#FFAF00",  # Orange
    AgentType.SUMMARIZE: "#D7AF5F",  # Gold
    AgentType.MENTOR: "#AF87D7",  # Purple
    AgentType.CRS: "#00D787",  # Cyan-green
}


class AgentList(OptionList):
    """Left sidebar showing list of running agents."""

    class SelectionChanged(Message):
        """Message sent when selection changes."""

        def __init__(self, index: int) -> None:
            self.index = index
            super().__init__()

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the agent list."""
        super().__init__(**kwargs)
        self._agents: list[Agent] = []
        self._programmatic_update: bool = False

    def update_list(self, agents: list[Agent], current_idx: int) -> None:
        """Update the list with new agents.

        Args:
            agents: List of Agents to display
            current_idx: Index of currently selected agent
        """
        self._programmatic_update = True
        try:
            self._agents = agents
            self.clear_options()

            for i, agent in enumerate(agents):
                option = self._format_agent_option(
                    agent, i, is_selected=(i == current_idx)
                )
                self.add_option(option)

            # Highlight the current item
            if agents and 0 <= current_idx < len(agents):
                self.highlighted = current_idx
        finally:
            self._programmatic_update = False

    def _format_agent_option(
        self, agent: Agent, index: int, is_selected: bool
    ) -> Option:
        """Format an agent as an option for display.

        Args:
            agent: The Agent to format
            is_selected: Whether this is the currently selected item

        Returns:
            An Option for the OptionList
        """
        text = Text()

        # Agent type indicator with color
        color = _AGENT_TYPE_COLORS.get(agent.agent_type, "#FFFFFF")
        text.append(f"[{agent.display_type}] ", style=f"bold {color}")

        # CL name
        name_style = "bold #00D7AF" if is_selected else "#00D7AF"
        text.append(agent.cl_name, style=name_style)

        # Status
        text.append(" ", style="")
        if agent.status == "RUNNING":
            text.append(agent.status, style="bold #FFD700")  # Gold
        elif agent.status == "DONE":
            text.append(agent.status, style="bold #00D787")  # Green
        else:
            text.append(agent.status, style="dim")

        if not agent.start_time:
            # For RUNNING field agents, show workspace number
            if agent.workspace_num is not None:
                text.append(" (#", style="dim")
                text.append(str(agent.workspace_num), style="#5FD7FF")
                text.append(")", style="dim")

        return Option(text, id=f"{index}:{agent.agent_type.value}:{agent.cl_name}")

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Handle option highlight (keyboard navigation)."""
        # Only post message for user-initiated navigation, not programmatic updates
        if event.option_index is not None and not self._programmatic_update:
            self.post_message(self.SelectionChanged(event.option_index))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection (mouse click or Enter)."""
        if event.option_index is not None:
            self.post_message(self.SelectionChanged(event.option_index))
