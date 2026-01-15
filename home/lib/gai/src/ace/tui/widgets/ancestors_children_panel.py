"""Ancestors and Children panel widget for the ace TUI."""

from typing import Any

from rich.text import Text
from textual.widgets import Static

from ...changespec import ChangeSpec


class AncestorsChildrenPanel(Static):
    """Panel showing ancestors and direct children of the current ChangeSpec."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._ancestors: list[str] = []  # Ordered: parent, grandparent, etc.
        self._children: list[str] = []  # Direct children only
        self._ancestor_keys: dict[str, str] = {}  # name -> key hint
        self._children_keys: dict[str, str] = {}  # name -> key hint

    def update_relationships(
        self,
        changespec: ChangeSpec,
        all_changespecs: list[ChangeSpec],
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Update with ancestors and children of current ChangeSpec.

        Args:
            changespec: Currently selected ChangeSpec
            all_changespecs: All changespecs (for finding children)

        Returns:
            Tuple of (ancestor_keys, children_keys) mappings
        """
        # Build ancestors (recursive parent traversal)
        self._ancestors = self._find_ancestors(changespec, all_changespecs)

        # Build children (direct only)
        self._children = self._find_children(changespec.name, all_changespecs)

        # Assign keybindings
        self._ancestor_keys = self._assign_keys(self._ancestors, is_ancestor=True)
        self._children_keys = self._assign_keys(self._children, is_ancestor=False)

        self._refresh_content()
        return self._ancestor_keys, self._children_keys

    def _find_ancestors(
        self,
        changespec: ChangeSpec,
        all_changespecs: list[ChangeSpec],
    ) -> list[str]:
        """Find all ancestors recursively (parent, grandparent, etc.)."""
        name_map = {cs.name.lower(): cs for cs in all_changespecs}
        ancestors: list[str] = []
        visited: set[str] = set()

        current = changespec
        while current.parent:
            parent_name = current.parent  # Store to preserve type narrowing
            parent_lower = parent_name.lower()
            if parent_lower in visited:
                break  # Cycle detection
            visited.add(parent_lower)

            if parent_lower in name_map:
                parent_cs = name_map[parent_lower]
                ancestors.append(parent_cs.name)  # Use actual case
                current = parent_cs
            else:
                # Parent not found in list (might be filtered out)
                ancestors.append(parent_name)
                break

        return ancestors

    def _find_children(
        self,
        name: str,
        all_changespecs: list[ChangeSpec],
    ) -> list[str]:
        """Find direct children (changespecs whose parent == name)."""
        name_lower = name.lower()
        return [
            cs.name
            for cs in all_changespecs
            if cs.parent and cs.parent.lower() == name_lower
        ]

    def _assign_keys(
        self,
        names: list[str],
        is_ancestor: bool,
    ) -> dict[str, str]:
        """Assign keybindings to a list of names.

        For ancestors: "<" (single), "<<" (first), "<a", "<b", etc.
        For children: ">" (single), ">>" (first), ">a", ">b", etc.
        """
        if not names:
            return {}

        prefix = "<" if is_ancestor else ">"
        result: dict[str, str] = {}

        if len(names) == 1:
            result[names[0]] = prefix
        else:
            # First item gets double prefix
            result[names[0]] = prefix * 2
            # Remaining get letter suffixes
            for i, name in enumerate(names[1:], start=0):
                if i < 26:  # a-z
                    letter = chr(ord("a") + i)
                    result[name] = f"{prefix}{letter}"

        return result

    def _refresh_content(self) -> None:
        """Refresh the panel content."""
        if not self._ancestors and not self._children:
            self.display = False
            return

        self.display = True
        text = Text()

        # ANCESTORS section
        if self._ancestors:
            text.append("ANCESTORS", style="bold #87D7FF")
            for name in self._ancestors:
                key = self._ancestor_keys.get(name, "")
                text.append("\n")
                text.append(f"  [{key}] ", style="bold #FFAF00")
                text.append(name, style="#00D7AF")

        # CHILDREN section (no blank line between sections)
        if self._children:
            if self._ancestors:
                text.append("\n")
            text.append("CHILDREN", style="bold #87D7FF")
            for name in self._children:
                key = self._children_keys.get(name, "")
                text.append("\n")
                text.append(f"  [{key}] ", style="bold #FFAF00")
                text.append(name, style="#00D7AF")

        self.update(text)

    def clear(self) -> None:
        """Clear the panel."""
        self._ancestors = []
        self._children = []
        self._ancestor_keys = {}
        self._children_keys = {}
        self.display = False
