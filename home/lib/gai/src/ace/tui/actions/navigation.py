"""Navigation mixin for the ace TUI app."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from textual.containers import VerticalScroll

if TYPE_CHECKING:
    from ...changespec import ChangeSpec
    from ...query.types import QueryExpr
    from ...query_history import QueryHistoryStacks
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
    _axe_pinned_to_bottom: bool
    _ancestor_mode_active: bool
    _child_mode_active: bool
    _child_key_buffer: str
    _ancestor_keys: dict[str, str]
    _children_keys: dict[str, str]
    _all_changespecs: list[ChangeSpec]
    _query_history: QueryHistoryStacks
    query_string: str
    parsed_query: QueryExpr

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
            from ..widgets import BgCmdList

            try:
                bgcmd_list = self.query_one("#bgcmd-list-panel", BgCmdList)  # type: ignore[attr-defined]
                bgcmd_list.action_cursor_down()
            except Exception:
                pass

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
            from ..widgets import BgCmdList

            try:
                bgcmd_list = self.query_one("#bgcmd-list-panel", BgCmdList)  # type: ignore[attr-defined]
                bgcmd_list.action_cursor_up()
            except Exception:
                pass

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

    # --- Help Action ---

    def action_show_help(self) -> None:
        """Show the help modal with all keybindings."""
        from ..modals import HelpModal

        self.push_screen(  # type: ignore[attr-defined]
            HelpModal(
                current_tab=self.current_tab,
                active_query=self.canonical_query_string,  # type: ignore[attr-defined]
            )
        )

    # --- Ancestry Navigation Actions ---

    def action_start_ancestor_mode(self) -> None:
        """Enter ancestor navigation mode (< key pressed)."""
        if self.current_tab != "changespecs" or not self.changespecs:
            return

        # If only one ancestor, navigate directly
        if len(self._ancestor_keys) == 1:
            target = list(self._ancestor_keys.keys())[0]
            self._navigate_to_changespec(target, is_ancestor=True)
        elif len(self._ancestor_keys) > 1:
            self._ancestor_mode_active = True

    def action_start_child_mode(self) -> None:
        """Enter child navigation mode (> key pressed)."""
        if self.current_tab != "changespecs" or not self.changespecs:
            return

        if not self._children_keys:
            return

        # If only one child with key ">" (single leaf child), navigate directly
        if len(self._children_keys) == 1 and ">" in self._children_keys:
            target = self._children_keys[">"]
            self._navigate_to_changespec(target, is_ancestor=False)
        else:
            self._child_key_buffer = ""
            self._child_mode_active = True

    def _handle_ancestry_key(self, key: str) -> bool:
        """Handle key in ancestor/child navigation mode.

        Returns True if the key was handled.
        """
        if self._ancestor_mode_active:
            return self._process_ancestor_key(key)
        elif self._child_mode_active:
            return self._process_child_key(key)
        return False

    def _process_ancestor_key(self, key: str) -> bool:
        """Process key in ancestor mode."""
        self._ancestor_mode_active = False

        if key in ("less_than_sign", "<"):
            # << - go to first ancestor (parent)
            if self._ancestor_keys:
                target = list(self._ancestor_keys.keys())[0]
                self._navigate_to_changespec(target, is_ancestor=True)
            return True
        elif len(key) == 1 and key.isalpha() and key.islower():
            # <a, <b, etc. - find matching ancestor
            expected_key = f"<{key}"
            for name, keybind in self._ancestor_keys.items():
                if keybind == expected_key:
                    self._navigate_to_changespec(name, is_ancestor=True)
                    return True
        return True  # Consume the key regardless

    def _process_child_key(self, key: str) -> bool:
        """Process key in child mode.

        Handles multi-character sequences like >>, >2, >2a, >2a., etc.
        The buffer accumulates characters until:
        - "." is pressed: navigate to non-leaf node matching buffer
        - Buffer matches a leaf node key: navigate to that node
        - Invalid key: cancel mode
        """
        if key in ("greater_than_sign", ">"):
            # >> - go to first child
            target_key = ">>"
            if target_key in self._children_keys:
                self._navigate_to_changespec(
                    self._children_keys[target_key], is_ancestor=False
                )
            self._child_key_buffer = ""
            self._child_mode_active = False
            return True

        if key in ("period", "full_stop", "."):
            # Navigate to non-leaf node
            target_key = ">" + self._child_key_buffer + "."
            if target_key in self._children_keys:
                self._navigate_to_changespec(
                    self._children_keys[target_key], is_ancestor=False
                )
            self._child_key_buffer = ""
            self._child_mode_active = False
            return True

        # Validate and accumulate the key
        if self._is_valid_next_child_key(key):
            self._child_key_buffer += key

            # Check if buffer matches a leaf node (no "." suffix)
            target_key = ">" + self._child_key_buffer
            if target_key in self._children_keys:
                self._navigate_to_changespec(
                    self._children_keys[target_key], is_ancestor=False
                )
                self._child_key_buffer = ""
                self._child_mode_active = False
                return True

            # Check if buffer could be a prefix for any key
            # If not, cancel the mode
            has_potential_match = any(
                k.startswith(target_key) for k in self._children_keys
            )
            if not has_potential_match:
                self._child_key_buffer = ""
                self._child_mode_active = False
                return True

            # Stay in mode, wait for more keys
            return True

        # Invalid key - cancel mode
        self._child_key_buffer = ""
        self._child_mode_active = False
        return True

    def _is_valid_next_child_key(self, key: str) -> bool:
        """Check if key is valid as the next character in child key sequence.

        Pattern:
        - Empty buffer: accept letter (a-z for >a, >b) OR digit (2-9 for >2, >3)
        - After letter: expect digit 2-9
        - After digit: expect letter a-z
        """
        if len(key) != 1:
            return False

        if not self._child_key_buffer:
            # First character can be letter (for >a, >b) or digit (for >2, >3)
            if key.isalpha() and key.islower():
                return True
            if key.isdigit() and "2" <= key <= "9":
                return True
            return False

        last_char = self._child_key_buffer[-1]
        if last_char.isdigit():
            # After digit, expect letter
            return key.isalpha() and key.islower()
        else:
            # After letter, expect digit
            return key.isdigit() and "2" <= key <= "9"

    def _navigate_to_changespec(self, target_name: str, is_ancestor: bool) -> None:
        """Navigate to a ChangeSpec by name.

        If target is in current filtered list, just jump to it.
        If not, change query to ancestor:<name> and jump.
        """
        # Check if target is in current filtered list
        target_idx = self._find_in_current_list(target_name)

        if target_idx is not None:
            # Target is visible - just jump to it
            self.current_idx = target_idx
        else:
            # Target not in current list - change query
            self._change_query_for_navigation(target_name, is_ancestor)

    def _find_in_current_list(self, name: str) -> int | None:
        """Find a ChangeSpec by name in current filtered list."""
        name_lower = name.lower()
        for idx, cs in enumerate(self.changespecs):
            if cs.name.lower() == name_lower:
                return idx
        return None

    def _change_query_for_navigation(
        self,
        target_name: str,
        is_ancestor: bool,
    ) -> None:
        """Change query to navigate to a target not in current list.

        Uses ancestor:<name> query where:
        - For ancestor navigation: name is the ancestor's name
        - For child navigation: name is the current ChangeSpec's name
        """
        from ...query import parse_query, to_canonical_string
        from ...query_history import push_to_prev_stack, save_query_history

        if is_ancestor:
            # Going to ancestor: use ancestor's name
            query_name = target_name
        else:
            # Going to child: use current ChangeSpec's name
            # This shows all descendants of current
            current_cs = self.changespecs[self.current_idx]
            query_name = current_cs.name

        new_query = f"ancestor:{query_name}"

        try:
            new_parsed = parse_query(new_query)
            new_canonical = to_canonical_string(new_parsed)
            current_canonical = self.canonical_query_string  # type: ignore[attr-defined]

            # Push to history
            if new_canonical != current_canonical:
                push_to_prev_stack(current_canonical, self._query_history)
                save_query_history(self._query_history)

            self.parsed_query = new_parsed
            self.query_string = new_query
            self._load_changespecs()  # type: ignore[attr-defined]
            self._save_current_query()  # type: ignore[attr-defined]

            # Find and select the target
            target_idx = self._find_in_current_list(target_name)
            if target_idx is not None:
                self.current_idx = target_idx

        except Exception as e:
            self.notify(f"Navigation error: {e}", severity="error")  # type: ignore[attr-defined]
