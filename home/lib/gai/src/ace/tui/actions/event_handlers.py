"""Event handler mixin for the ace TUI app."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from textual import events

from ..widgets import (
    AgentList,
    ChangeSpecList,
    TabBar,
)

if TYPE_CHECKING:
    from ...changespec import ChangeSpec
    from ..models import Agent

# Type alias for tab names
TabName = Literal["changespecs", "agents"]


class EventHandlersMixin:
    """Mixin providing event handlers and timer callbacks."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    current_idx: int
    current_tab: TabName
    refresh_interval: int
    _countdown_remaining: int
    _fold_mode_active: bool
    _agents: list[Agent]

    def _on_auto_refresh(self) -> None:
        """Auto-refresh handler called by timer."""
        self._countdown_remaining = self.refresh_interval
        if self.current_tab == "changespecs":
            self._reload_and_reposition()  # type: ignore[attr-defined]
        else:
            self._load_agents()  # type: ignore[attr-defined]

    def _on_countdown_tick(self) -> None:
        """Countdown tick handler called every second."""
        self._countdown_remaining -= 1
        if self._countdown_remaining < 0:
            self._countdown_remaining = self.refresh_interval
        if self.current_tab == "changespecs":
            self._update_info_panel()  # type: ignore[attr-defined]
        else:
            self._update_agents_info_panel()  # type: ignore[attr-defined]

    def on_key(self, event: events.Key) -> None:
        """Handle key events, including fold sub-keys."""
        if self._fold_mode_active:
            if self._handle_fold_key(event.key):  # type: ignore[attr-defined]
                event.prevent_default()
                event.stop()

    def on_change_spec_list_selection_changed(
        self, event: ChangeSpecList.SelectionChanged
    ) -> None:
        """Handle selection change in the ChangeSpec list widget."""
        if self.current_tab == "changespecs" and 0 <= event.index < len(
            self.changespecs
        ):
            self.current_idx = event.index

    def on_agent_list_selection_changed(
        self, event: AgentList.SelectionChanged
    ) -> None:
        """Handle selection change in the Agent list widget."""
        if self.current_tab == "agents" and 0 <= event.index < len(self._agents):
            self.current_idx = event.index

    def on_tab_bar_tab_clicked(self, event: TabBar.TabClicked) -> None:
        """Handle tab clicks from the tab bar."""
        if event.tab != self.current_tab:
            self.action_toggle_tab()  # type: ignore[attr-defined]

    def on_change_spec_list_width_changed(
        self, event: ChangeSpecList.WidthChanged
    ) -> None:
        """Handle width change from the list widget."""
        from ..app import _MAX_LIST_WIDTH, _MIN_LIST_WIDTH

        width = max(_MIN_LIST_WIDTH, min(_MAX_LIST_WIDTH, event.width))
        list_container = self.query_one("#list-container")  # type: ignore[attr-defined]
        list_container.styles.width = width

    def on_agent_list_width_changed(self, event: AgentList.WidthChanged) -> None:
        """Handle width change from the agent list widget."""
        from ..app import _MAX_AGENT_LIST_WIDTH, _MIN_AGENT_LIST_WIDTH

        width = max(_MIN_AGENT_LIST_WIDTH, min(_MAX_AGENT_LIST_WIDTH, event.width))
        agent_list_container = self.query_one("#agent-list-container")  # type: ignore[attr-defined]
        agent_list_container.styles.width = width
