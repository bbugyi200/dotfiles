"""Tree navigation mixin for ancestry/child/sibling navigation."""

from __future__ import annotations

from ._types import NavigationMixinBase


class TreeNavigationMixin(NavigationMixinBase):
    """Mixin providing ancestry/child/sibling tree navigation."""

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

    def action_start_sibling_mode(self) -> None:
        """Enter sibling navigation mode (~ key pressed)."""
        if self.current_tab != "changespecs" or not self.changespecs:
            return

        if not self._sibling_keys:
            return

        # If only one sibling with key "~", navigate directly
        if len(self._sibling_keys) == 1 and "~" in self._sibling_keys:
            target = self._sibling_keys["~"]
            self._navigate_to_changespec(target, is_ancestor=False, is_sibling=True)
        else:
            self._sibling_mode_active = True

    def _handle_ancestry_key(self, key: str) -> bool:
        """Handle key in ancestor/child/sibling navigation mode.

        Returns True if the key was handled.
        """
        if self._ancestor_mode_active:
            return self._process_ancestor_key(key)
        elif self._child_mode_active:
            return self._process_child_key(key)
        elif self._sibling_mode_active:
            return self._process_sibling_key(key)
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

    def _process_sibling_key(self, key: str) -> bool:
        """Process key in sibling mode.

        Handles sequences like ~~, ~a, ~b, etc.
        """
        self._sibling_mode_active = False

        if key in ("tilde", "~"):
            # ~~ - go to first sibling
            if "~~" in self._sibling_keys:
                target = self._sibling_keys["~~"]
                self._navigate_to_changespec(target, is_ancestor=False, is_sibling=True)
            return True
        elif len(key) == 1 and key.isalpha() and key.islower():
            # ~a, ~b, etc. - find matching sibling
            expected_key = f"~{key}"
            if expected_key in self._sibling_keys:
                target = self._sibling_keys[expected_key]
                self._navigate_to_changespec(target, is_ancestor=False, is_sibling=True)
            return True

        return True  # Consume the key regardless

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

    def _navigate_to_changespec(
        self, target_name: str, is_ancestor: bool, is_sibling: bool = False
    ) -> None:
        """Navigate to a ChangeSpec by name.

        If target is in current filtered list, just jump to it.
        If not, change query to ancestor:<name> or sibling:<base_name> and jump.
        """
        # Push current ChangeSpec to history before navigating away
        self._push_changespec_to_history()  # type: ignore[attr-defined]

        # Check if target is in current filtered list
        target_idx = self._find_in_current_list(target_name)

        if target_idx is not None:
            # Target is visible - just jump to it
            self.current_idx = target_idx
        else:
            # Target not in current list - change query
            self._change_query_for_navigation(target_name, is_ancestor, is_sibling)

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
        is_sibling: bool = False,
    ) -> None:
        """Change query to navigate to a target not in current list.

        Uses appropriate query based on navigation type:
        - For sibling navigation: sibling:<base_name> (strips __<N> suffix)
        - For ancestor navigation: ancestor:<ancestor_name>
        - For child navigation: ancestor:<current_name>
        """
        from gai_utils import strip_reverted_suffix

        from ....query import parse_query, to_canonical_string
        from ....query_history import push_to_prev_stack, save_query_history

        if is_sibling:
            # For sibling navigation: use sibling:<base_name>
            current_cs = self.changespecs[self.current_idx]
            base_name = strip_reverted_suffix(current_cs.name)
            new_query = f"sibling:{base_name}"
        elif is_ancestor:
            # Going to ancestor: use ancestor's name
            new_query = f"ancestor:{target_name}"
        else:
            # Going to child: use current ChangeSpec's name
            # This shows all descendants of current
            current_cs = self.changespecs[self.current_idx]
            new_query = f"ancestor:{current_cs.name}"

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
