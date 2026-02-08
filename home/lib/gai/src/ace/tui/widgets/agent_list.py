"""Agent list widget for the ace TUI."""

from typing import Any

from rich.text import Text
from textual.message import Message
from textual.widgets import OptionList
from textual.widgets.option_list import Option
from xprompt.workflow_output import get_substep_suffix

from ..models.agent import Agent, AgentType

# Color mapping for agent types
_AGENT_TYPE_COLORS: dict[AgentType, str] = {
    AgentType.RUNNING: "#87AFFF",  # Blue
    AgentType.FIX_HOOK: "#FFAF00",  # Orange
    AgentType.SUMMARIZE: "#D7AF5F",  # Gold
    AgentType.MENTOR: "#AF87D7",  # Purple
    AgentType.CRS: "#00D787",  # Cyan-green
    AgentType.WORKFLOW: "#FF87D7",  # Pink for workflow agent steps
}

# Icon for dismissible (completed) agents
_DONE_ICON = "✘"
_DISMISSIBLE_STATUSES = (
    "DONE",
    "REVIVED",
    "FAILED",
)

# Indentation prefix for workflow child agents
_CHILD_INDENT = "  └─ "


def _is_foldable_parent(agent: Agent) -> bool:
    """Check if an agent is a foldable workflow parent.

    Args:
        agent: The agent to check.

    Returns:
        True if this agent is a workflow parent that can be folded.
    """
    return (
        agent.agent_type == AgentType.WORKFLOW
        and not agent.is_workflow_child
        and not agent.appears_as_agent
    )


def _calculate_entry_display_width(
    agent: Agent,
    fold_annotation: str = "",
) -> int:
    """Calculate display width of an Agent entry in terminal cells.

    Args:
        agent: The Agent to measure
        fold_annotation: Fold annotation text to append

    Returns:
        Width in terminal cells
    """
    # Format: "[indent][step_num][icon] [{display_type}] {cl_name} ({status}) - #{wks}"
    parts = []
    # Add indentation for workflow children
    if agent.is_workflow_child:
        parts.append(_CHILD_INDENT)
        # Add step number if available
        if agent.step_index is not None:
            if (
                agent.parent_step_index is not None
                and agent.parent_total_steps is not None
            ):
                # Embedded step: format as "1a/7 "
                parent_num = agent.parent_step_index + 1
                suffix = get_substep_suffix(agent.step_index)
                parts.append(f"{parent_num}{suffix}/{agent.parent_total_steps} ")
            elif agent.total_steps is not None:
                # Regular step: format as "1/3 "
                step_num = agent.step_index + 1
                parts.append(f"{step_num}/{agent.total_steps} ")
    if agent.status in _DISMISSIBLE_STATUSES:
        parts.append(f"{_DONE_ICON} ")
    parts.extend([f"[{agent.display_type}] ", agent.cl_name, " ", f"({agent.status})"])
    if agent.workspace_num is not None:
        parts.append(f" - #{agent.workspace_num}")
    if fold_annotation:
        parts.append(fold_annotation)
    text = Text("".join(parts))
    return text.cell_len


class AgentList(OptionList):
    """Left sidebar showing list of running agents."""

    class SelectionChanged(Message):
        """Message sent when selection changes."""

        def __init__(self, index: int) -> None:
            self.index = index
            super().__init__()

    class WidthChanged(Message):
        """Message sent when optimal width changes."""

        def __init__(self, width: int) -> None:
            self.width = width
            super().__init__()

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the agent list."""
        super().__init__(**kwargs)
        self._agents: list[Agent] = []
        self._programmatic_update: bool = False

    def update_list(
        self,
        agents: list[Agent],
        current_idx: int,
        fold_counts: dict[str, tuple[int, int]] | None = None,
    ) -> None:
        """Update the list with new agents.

        Args:
            agents: List of Agents to display
            current_idx: Index of currently selected agent
            fold_counts: Optional dict mapping workflow raw_suffix to
                (non_hidden_count, hidden_count) for fold annotations
        """
        self._programmatic_update = True
        self._agents = agents
        self.clear_options()

        # Determine which parents have visible children in the filtered list
        parents_with_visible_children: set[str] = set()
        for agent in agents:
            if agent.is_workflow_child and agent.parent_timestamp:
                parents_with_visible_children.add(agent.parent_timestamp)

        max_width = 0
        for i, agent in enumerate(agents):
            annotation = _compute_fold_annotation(
                agent, fold_counts, parents_with_visible_children
            )
            option = self._format_agent_option(
                agent, i, is_selected=(i == current_idx), fold_annotation=annotation
            )
            self.add_option(option)
            width = _calculate_entry_display_width(agent, fold_annotation=annotation)
            max_width = max(max_width, width)

        # Add padding for border, scrollbar, visual comfort (~8 cells)
        _PADDING = 8
        optimal_width = max_width + _PADDING
        self.post_message(self.WidthChanged(optimal_width))

        # Highlight the current item
        if agents and 0 <= current_idx < len(agents):
            self.highlighted = current_idx

        # Clear flag after event loop processes pending events
        self.call_later(self._clear_programmatic_flag)

    def _clear_programmatic_flag(self) -> None:
        """Clear programmatic update flag after event processing."""
        self._programmatic_update = False

    def _format_agent_option(
        self,
        agent: Agent,
        index: int,
        is_selected: bool,
        fold_annotation: str = "",
    ) -> Option:
        """Format an agent as an option for display.

        Args:
            agent: The Agent to format
            index: Index of the agent in the list
            is_selected: Whether this is the currently selected item
            fold_annotation: Fold annotation text to append

        Returns:
            An Option for the OptionList
        """
        text = Text()

        # Indentation for workflow child agents
        if agent.is_workflow_child:
            text.append(_CHILD_INDENT, style="dim #808080")
            # Add step number if available
            if agent.step_index is not None:
                if (
                    agent.parent_step_index is not None
                    and agent.parent_total_steps is not None
                ):
                    # Embedded step: format as "1a/7"
                    parent_num = agent.parent_step_index + 1
                    suffix = get_substep_suffix(agent.step_index)
                    text.append(
                        f"{parent_num}{suffix}/{agent.parent_total_steps} ",
                        style="dim #AAAAAA",
                    )
                elif agent.total_steps is not None:
                    # Regular step: format as "1/3"
                    step_num = agent.step_index + 1
                    text.append(f"{step_num}/{agent.total_steps} ", style="dim #AAAAAA")

        # Done icon for dismissible agents
        if agent.status in _DISMISSIBLE_STATUSES:
            text.append(f"{_DONE_ICON} ", style="bold red")

        # Agent type indicator with color
        # Workflows appearing as agents use RUNNING color
        if agent.appears_as_agent:
            color = _AGENT_TYPE_COLORS[AgentType.RUNNING]
        else:
            color = _AGENT_TYPE_COLORS.get(agent.agent_type, "#FFFFFF")
        text.append(f"[{agent.display_type}] ", style=f"bold {color}")

        # CL name
        name_style = "bold #00D7AF" if is_selected else "#00D7AF"
        text.append(agent.cl_name, style=name_style)

        # Status (wrapped in parentheses, parens are dim)
        text.append(" (", style="dim")
        if agent.status == "RUNNING":
            text.append(agent.status, style="bold #FFD700")  # Gold
        elif agent.status == "DONE":
            text.append(agent.status, style="bold #5FD75F")  # Green
        elif agent.status == "REVIVED":
            text.append(agent.status, style="bold #D7AF5F")  # Gold/amber
        elif agent.status == "FAILED":
            text.append(agent.status, style="bold #FF5F5F")  # Red
        else:
            text.append(agent.status, style="dim")
        text.append(")", style="dim")

        # Show workspace number if available
        if agent.workspace_num is not None:
            text.append(" - #", style="dim")
            text.append(str(agent.workspace_num), style="#5FD7FF")

        # Fold annotation for workflow parents
        if fold_annotation:
            if fold_annotation.startswith(" (+"):
                # EXPANDED: "(+N hidden)" in dim style
                text.append(fold_annotation, style="dim")
            else:
                # COLLAPSED: "+N" in dim cyan
                text.append(fold_annotation, style="dim #00D7D7")

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


def _compute_fold_annotation(
    agent: Agent,
    fold_counts: dict[str, tuple[int, int]] | None,
    parents_with_visible_children: set[str],
) -> str:
    """Compute fold annotation for a workflow parent.

    Args:
        agent: The agent to annotate.
        fold_counts: Fold counts mapping raw_suffix -> (non_hidden, hidden).
        parents_with_visible_children: Set of parent raw_suffixes that have
            visible children in the current filtered list.

    Returns:
        Annotation string, or empty string if not applicable.
    """
    if not fold_counts or not _is_foldable_parent(agent) or not agent.raw_suffix:
        return ""

    counts = fold_counts.get(agent.raw_suffix)
    if not counts:
        return ""

    non_hidden, hidden = counts
    total = non_hidden + hidden
    if total == 0:
        return ""

    has_visible_children = agent.raw_suffix in parents_with_visible_children

    if not has_visible_children:
        # COLLAPSED: show count of non-hidden children
        if non_hidden > 0:
            return f" +{non_hidden}"
        if hidden > 0:
            return f" +{hidden}"
        return ""

    # Children are visible (EXPANDED or FULLY_EXPANDED)
    if hidden > 0:
        # EXPANDED: some children still hidden
        return f" (+{hidden} hidden)"

    # FULLY_EXPANDED: all children visible, no annotation needed
    return ""
