"""Navigation mixin for the ace TUI app."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from textual.containers import VerticalScroll

if TYPE_CHECKING:
    from ...changespec import ChangeSpec
    from ..models import Agent

# Type alias for tab names
TabName = Literal["changespecs", "agents", "axe"]


class NavigationMixin:
    """Mixin providing navigation, scrolling, and fold mode actions."""

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

    # --- Navigation Actions ---

    def action_next_changespec(self) -> None:
        """Navigate to the next item, cycling to start if at end."""
        if self.current_tab == "changespecs":
            if len(self.changespecs) == 0:
                return
            if self.current_idx < len(self.changespecs) - 1:
                self.current_idx += 1
            else:
                self.current_idx = 0
        else:
            if len(self._agents) == 0:
                return
            if self.current_idx < len(self._agents) - 1:
                self.current_idx += 1
            else:
                self.current_idx = 0

    def action_prev_changespec(self) -> None:
        """Navigate to the previous item, cycling to end if at start."""
        if self.current_tab == "changespecs":
            if len(self.changespecs) == 0:
                return
            if self.current_idx > 0:
                self.current_idx -= 1
            else:
                self.current_idx = len(self.changespecs) - 1
        else:
            if len(self._agents) == 0:
                return
            if self.current_idx > 0:
                self.current_idx -= 1
            else:
                self.current_idx = len(self._agents) - 1

    def action_scroll_detail_down(self) -> None:
        """Scroll the detail panel down by half a page (vim Ctrl+D style)."""
        if self.current_tab == "changespecs":
            scroll_container = self.query_one("#detail-scroll", VerticalScroll)  # type: ignore[attr-defined]
        else:
            scroll_container = self.query_one("#agent-diff-scroll", VerticalScroll)  # type: ignore[attr-defined]
        height = scroll_container.scrollable_content_region.height
        scroll_container.scroll_relative(y=height // 2, animate=False)

    def action_scroll_detail_up(self) -> None:
        """Scroll the detail panel up by half a page (vim Ctrl+U style)."""
        if self.current_tab == "changespecs":
            scroll_container = self.query_one("#detail-scroll", VerticalScroll)  # type: ignore[attr-defined]
        else:
            scroll_container = self.query_one("#agent-diff-scroll", VerticalScroll)  # type: ignore[attr-defined]
        height = scroll_container.scrollable_content_region.height
        scroll_container.scroll_relative(y=-(height // 2), animate=False)

    def action_scroll_prompt_down(self) -> None:
        """Scroll the agent prompt panel down by half a page (Agents tab only)."""
        if self.current_tab != "agents":
            return
        scroll_container = self.query_one("#agent-prompt-scroll", VerticalScroll)  # type: ignore[attr-defined]
        height = scroll_container.scrollable_content_region.height
        scroll_container.scroll_relative(y=height // 2, animate=False)

    def action_scroll_prompt_up(self) -> None:
        """Scroll the agent prompt panel up by half a page (Agents tab only)."""
        if self.current_tab != "agents":
            return
        scroll_container = self.query_one("#agent-prompt-scroll", VerticalScroll)  # type: ignore[attr-defined]
        height = scroll_container.scrollable_content_region.height
        scroll_container.scroll_relative(y=-(height // 2), animate=False)

    # --- Tab Switching Actions ---

    def action_next_tab(self) -> None:
        """Switch to the next tab (cycling: CLs -> Agents -> Axe -> CLs)."""
        self._save_current_tab_position()
        if self.current_tab == "changespecs":
            self.current_idx = self._agents_last_idx
            self.current_tab = "agents"  # type: ignore[assignment]
        elif self.current_tab == "agents":
            self.current_idx = 0  # Axe has no list
            self.current_tab = "axe"  # type: ignore[assignment]
        else:  # axe
            self.current_idx = self._changespecs_last_idx
            self.current_tab = "changespecs"  # type: ignore[assignment]

    def action_prev_tab(self) -> None:
        """Switch to the previous tab (cycling: CLs <- Agents <- Axe <- CLs)."""
        self._save_current_tab_position()
        if self.current_tab == "changespecs":
            self.current_idx = 0  # Axe has no list
            self.current_tab = "axe"  # type: ignore[assignment]
        elif self.current_tab == "agents":
            self.current_idx = self._changespecs_last_idx
            self.current_tab = "changespecs"  # type: ignore[assignment]
        else:  # axe
            self.current_idx = self._agents_last_idx
            self.current_tab = "agents"  # type: ignore[assignment]

    def _save_current_tab_position(self) -> None:
        """Save the current position before switching tabs."""
        if self.current_tab == "changespecs":
            self._changespecs_last_idx = self.current_idx
        elif self.current_tab == "agents":
            self._agents_last_idx = self.current_idx
        # Axe tab has no position to save

    # --- Fold Mode Actions ---

    def action_start_fold_mode(self) -> None:
        """Enter fold mode - waiting for sub-key (c/h/z)."""
        self._fold_mode_active = True

    def _handle_fold_key(self, key: str) -> bool:
        """Handle fold sub-key. Returns True if handled."""
        if not self._fold_mode_active:
            return False

        self._fold_mode_active = False

        if key == "c":
            self.commits_collapsed = not self.commits_collapsed
            self._refresh_display()  # type: ignore[attr-defined]
            return True
        elif key == "h":
            self.hooks_collapsed = not self.hooks_collapsed
            self._refresh_display()  # type: ignore[attr-defined]
            return True
        elif key == "m":
            self.mentors_collapsed = not self.mentors_collapsed
            self._refresh_display()  # type: ignore[attr-defined]
            return True
        elif key == "z":
            # Toggle all - if different states, collapse all
            if self.commits_collapsed == self.hooks_collapsed == self.mentors_collapsed:
                new_state = not self.commits_collapsed
            else:
                new_state = True  # Default to collapsed if mismatched
            self.commits_collapsed = new_state
            self.hooks_collapsed = new_state
            self.mentors_collapsed = new_state
            self._refresh_display()  # type: ignore[attr-defined]
            return True
        else:
            # Invalid key - cancel fold mode
            return True
