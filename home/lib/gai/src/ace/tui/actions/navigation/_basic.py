"""Basic navigation mixin for scrolling and tab switching."""

from __future__ import annotations

from textual.containers import VerticalScroll

from ._types import AxeViewType, NavigationMixinBase


class BasicNavigationMixin(NavigationMixinBase):
    """Mixin providing basic navigation, scrolling, and tab switching."""

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
        elif self.current_tab == "agents":
            if len(self._agents) == 0:
                return
            if self.current_idx < len(self._agents) - 1:
                self.current_idx += 1
            else:
                self.current_idx = 0
        else:  # axe tab
            # Get list of items: "axe" first, then bgcmd slots
            items: list[AxeViewType] = ["axe"]
            items.extend(slot for slot, _ in self._bgcmd_slots)

            if len(items) <= 1:
                return  # Nothing to navigate

            # Find current index
            try:
                current_idx = items.index(self._axe_current_view)
            except ValueError:
                current_idx = 0

            # Calculate next index (with wrapping)
            next_idx = (current_idx + 1) % len(items)

            # Update view
            self._switch_to_axe_view(items[next_idx])  # type: ignore[attr-defined]

    def action_prev_changespec(self) -> None:
        """Navigate to the previous item, cycling to end if at start."""
        if self.current_tab == "changespecs":
            if len(self.changespecs) == 0:
                return
            if self.current_idx > 0:
                self.current_idx -= 1
            else:
                self.current_idx = len(self.changespecs) - 1
        elif self.current_tab == "agents":
            if len(self._agents) == 0:
                return
            if self.current_idx > 0:
                self.current_idx -= 1
            else:
                self.current_idx = len(self._agents) - 1
        else:  # axe tab
            # Get list of items: "axe" first, then bgcmd slots
            items: list[AxeViewType] = ["axe"]
            items.extend(slot for slot, _ in self._bgcmd_slots)

            if len(items) <= 1:
                return  # Nothing to navigate

            # Find current index
            try:
                current_idx = items.index(self._axe_current_view)
            except ValueError:
                current_idx = 0

            # Calculate previous index (with wrapping)
            prev_idx = (current_idx - 1) % len(items)

            # Update view
            self._switch_to_axe_view(items[prev_idx])  # type: ignore[attr-defined]

    def action_scroll_detail_down(self) -> None:
        """Scroll the detail panel down by half a page (vim Ctrl+D style)."""
        if self.current_tab == "changespecs":
            scroll_container = self.query_one("#detail-scroll", VerticalScroll)  # type: ignore[attr-defined]
        elif self.current_tab == "agents":
            scroll_container = self.query_one("#agent-diff-scroll", VerticalScroll)  # type: ignore[attr-defined]
        else:  # axe
            self._axe_pinned_to_bottom = False
            scroll_container = self.query_one("#axe-output-scroll", VerticalScroll)  # type: ignore[attr-defined]
        height = scroll_container.scrollable_content_region.height
        scroll_container.scroll_relative(y=height // 2, animate=False)

    def action_scroll_detail_up(self) -> None:
        """Scroll the detail panel up by half a page (vim Ctrl+U style)."""
        if self.current_tab == "changespecs":
            scroll_container = self.query_one("#detail-scroll", VerticalScroll)  # type: ignore[attr-defined]
        elif self.current_tab == "agents":
            scroll_container = self.query_one("#agent-diff-scroll", VerticalScroll)  # type: ignore[attr-defined]
        else:  # axe
            self._axe_pinned_to_bottom = False
            scroll_container = self.query_one("#axe-output-scroll", VerticalScroll)  # type: ignore[attr-defined]
        height = scroll_container.scrollable_content_region.height
        scroll_container.scroll_relative(y=-(height // 2), animate=False)

    def action_scroll_prompt_down(self) -> None:
        """Scroll prompt panel (Agents) or full page (Axe)."""
        if self.current_tab == "agents":
            scroll_container = self.query_one("#agent-prompt-scroll", VerticalScroll)  # type: ignore[attr-defined]
            height = scroll_container.scrollable_content_region.height
            scroll_container.scroll_relative(y=height // 2, animate=False)
        elif self.current_tab == "axe":
            self._axe_pinned_to_bottom = False
            scroll_container = self.query_one("#axe-output-scroll", VerticalScroll)  # type: ignore[attr-defined]
            height = scroll_container.scrollable_content_region.height
            scroll_container.scroll_relative(y=height, animate=False)  # Full page

    def action_scroll_prompt_up(self) -> None:
        """Scroll prompt panel (Agents) or full page (Axe)."""
        if self.current_tab == "agents":
            scroll_container = self.query_one("#agent-prompt-scroll", VerticalScroll)  # type: ignore[attr-defined]
            height = scroll_container.scrollable_content_region.height
            scroll_container.scroll_relative(y=-(height // 2), animate=False)
        elif self.current_tab == "axe":
            self._axe_pinned_to_bottom = False
            scroll_container = self.query_one("#axe-output-scroll", VerticalScroll)  # type: ignore[attr-defined]
            height = scroll_container.scrollable_content_region.height
            scroll_container.scroll_relative(y=-height, animate=False)  # Full page

    def action_scroll_to_top(self) -> None:
        """Scroll to the top of the current scrollable area (Axe tab)."""
        if self.current_tab != "axe":
            return
        self._axe_pinned_to_bottom = False
        scroll_container = self.query_one("#axe-output-scroll", VerticalScroll)  # type: ignore[attr-defined]
        scroll_container.scroll_home(animate=False)

    def action_scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the current scrollable area (Axe tab).

        Also pins the scroll to bottom so auto-refresh keeps showing latest output.
        """
        if self.current_tab != "axe":
            return
        self._axe_pinned_to_bottom = True
        scroll_container = self.query_one("#axe-output-scroll", VerticalScroll)  # type: ignore[attr-defined]
        scroll_container.scroll_end(animate=False)

    # --- Tab Switching Actions ---

    def _get_clamped_changespecs_idx(self) -> int:
        """Get changespecs index clamped to valid range."""
        if not self.changespecs:
            return 0
        return min(self._changespecs_last_idx, len(self.changespecs) - 1)

    def _get_clamped_agents_idx(self) -> int:
        """Get agents index clamped to valid range."""
        if not self._agents:
            return 0
        return min(self._agents_last_idx, len(self._agents) - 1)

    def action_next_tab(self) -> None:
        """Switch to the next tab (cycling: CLs -> Agents -> Axe -> CLs)."""
        self._save_current_tab_position()
        if self.current_tab == "changespecs":
            self.current_tab = "agents"  # type: ignore[assignment]
            self.current_idx = self._get_clamped_agents_idx()
        elif self.current_tab == "agents":
            self.current_tab = "axe"  # type: ignore[assignment]
            self.current_idx = 0  # Axe has no list
        else:  # axe
            self.current_tab = "changespecs"  # type: ignore[assignment]
            self.current_idx = self._get_clamped_changespecs_idx()

    def action_prev_tab(self) -> None:
        """Switch to the previous tab (cycling: CLs <- Agents <- Axe <- CLs)."""
        self._save_current_tab_position()
        if self.current_tab == "changespecs":
            self.current_tab = "axe"  # type: ignore[assignment]
            self.current_idx = 0  # Axe has no list
        elif self.current_tab == "agents":
            self.current_tab = "changespecs"  # type: ignore[assignment]
            self.current_idx = self._get_clamped_changespecs_idx()
        else:  # axe
            self.current_tab = "agents"  # type: ignore[assignment]
            self.current_idx = self._get_clamped_agents_idx()

    def _save_current_tab_position(self) -> None:
        """Save the current position before switching tabs."""
        if self.current_tab == "changespecs":
            self._changespecs_last_idx = self.current_idx
        elif self.current_tab == "agents":
            self._agents_last_idx = self.current_idx
        # Axe tab has no position to save
