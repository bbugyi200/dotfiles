"""Ancestors and Children panel widget for the ace TUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rich.text import Text
from textual.widgets import Static

from ...changespec import ChangeSpec


@dataclass
class _ChildNode:
    """A node in the descendant tree."""

    name: str
    key: str  # e.g., ">2a" or ">2a." for non-leaf
    is_leaf: bool
    depth: int
    children: list[_ChildNode] = field(default_factory=list)


class AncestorsChildrenPanel(Static):
    """Panel showing ancestors and all descendants of the current ChangeSpec."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._ancestors: list[str] = []  # Ordered: parent, grandparent, etc.
        self._descendant_tree: list[_ChildNode] = []  # Tree of all descendants
        self._ancestor_keys: dict[str, str] = {}  # name -> key hint
        self._children_keys: dict[str, str] = {}  # key -> name (for navigation)

    def update_relationships(
        self,
        changespec: ChangeSpec,
        all_changespecs: list[ChangeSpec],
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Update with ancestors and descendants of current ChangeSpec.

        Args:
            changespec: Currently selected ChangeSpec
            all_changespecs: All changespecs (for finding children)

        Returns:
            Tuple of (ancestor_keys, children_keys) mappings
            - ancestor_keys: name -> key (e.g., {"parent": "<<"})
            - children_keys: key -> name (e.g., {">>": "child1", ">2a": "grandchild"})
        """
        # Build ancestors (recursive parent traversal)
        self._ancestors = self._find_ancestors(changespec, all_changespecs)

        # Build descendant tree (recursive child traversal)
        self._descendant_tree = self._build_descendant_tree(
            changespec.name, all_changespecs
        )

        # Assign keybindings
        self._ancestor_keys = self._assign_ancestor_keys(self._ancestors)
        self._children_keys = self._build_children_keys_map(self._descendant_tree)

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

    def _build_descendant_tree(
        self,
        parent_name: str,
        all_changespecs: list[ChangeSpec],
    ) -> list[_ChildNode]:
        """Build tree of all descendants with assigned keymaps."""
        # Build lookup for finding children
        children_map: dict[str, list[str]] = {}
        for cs in all_changespecs:
            if cs.parent:
                parent_lower = cs.parent.lower()
                if parent_lower not in children_map:
                    children_map[parent_lower] = []
                children_map[parent_lower].append(cs.name)

        # Build tree recursively
        direct_children = children_map.get(parent_name.lower(), [])
        return self._build_subtree(direct_children, children_map, depth=0, prefix=">")

    def _build_subtree(
        self,
        child_names: list[str],
        children_map: dict[str, list[str]],
        depth: int,
        prefix: str,
    ) -> list[_ChildNode]:
        """Recursively build subtree with keymaps.

        Key assignment pattern (alternating numbers 2-9 and letters a-z):
        - Depth 0 (direct children):
          - Single leaf child: >
          - First child (leaf or not): >> (no dot suffix)
          - Other children: >2, >3, ... >9 (with . for non-leaf)
        - Depth 1 (grandchildren): >a, >b, ... or >2a, >2b, ...
        - Depth 2: >a2, >a3, ... or >2a2, >2a3, ...
        - etc.
        """
        if not child_names:
            return []

        nodes: list[_ChildNode] = []
        use_letters = (depth % 2) == 1  # Odd depths use letters

        # Special case: single leaf child at depth 0 gets ">"
        if depth == 0 and len(child_names) == 1:
            name = child_names[0]
            grandchildren_names = children_map.get(name.lower(), [])
            is_leaf = len(grandchildren_names) == 0
            if is_leaf:
                # Single leaf child: use ">"
                return [
                    _ChildNode(
                        name=name,
                        key=">",
                        is_leaf=True,
                        depth=0,
                        children=[],
                    )
                ]

        for i, name in enumerate(child_names):
            # Determine the key suffix for this child
            if depth == 0:
                # Direct children: >>, >2, >3, ...
                if i == 0:
                    key_suffix = ">"  # Will become ">>"
                elif i < 9:  # 2-9 (indices 1-8)
                    key_suffix = str(i + 1)
                else:
                    continue  # Skip if too many direct children
            elif use_letters:
                # Use letters a-z
                if i < 26:
                    key_suffix = chr(ord("a") + i)
                else:
                    continue  # Skip if too many
            else:
                # Use numbers 2-9
                if i < 8:  # 2-9 (indices 0-7)
                    key_suffix = str(i + 2)
                else:
                    continue  # Skip if too many

            # Get grandchildren
            grandchildren_names = children_map.get(name.lower(), [])
            is_leaf = len(grandchildren_names) == 0

            # Build key: prefix + suffix
            base_key = prefix + key_suffix

            # Determine display key and recursion prefix
            if depth == 0 and i == 0:
                # First direct child: always ">>" (no dot), children use ">" prefix
                display_key = ">>"
                recurse_prefix = ">"
            else:
                # Other nodes: add "." for non-leaf
                display_key = base_key if is_leaf else base_key + "."
                recurse_prefix = base_key

            # Recursively build children
            children_nodes = self._build_subtree(
                grandchildren_names,
                children_map,
                depth + 1,
                recurse_prefix,
            )

            nodes.append(
                _ChildNode(
                    name=name,
                    key=display_key,
                    is_leaf=is_leaf,
                    depth=depth,
                    children=children_nodes,
                )
            )

        return nodes

    def _build_children_keys_map(
        self,
        tree: list[_ChildNode],
    ) -> dict[str, str]:
        """Flatten tree into key -> name mapping for navigation."""
        result: dict[str, str] = {}

        def traverse(nodes: list[_ChildNode]) -> None:
            for node in nodes:
                result[node.key] = node.name
                traverse(node.children)

        traverse(tree)
        return result

    def _assign_ancestor_keys(self, names: list[str]) -> dict[str, str]:
        """Assign keybindings to ancestors.

        Pattern: "<" (single), "<<" (first), "<2", "<3", etc.
        """
        if not names:
            return {}

        result: dict[str, str] = {}

        if len(names) == 1:
            result[names[0]] = "<"
        else:
            # First item gets double prefix
            result[names[0]] = "<<"
            # Remaining get number suffixes (2-9)
            for i, name in enumerate(names[1:], start=0):
                if i < 8:  # 2-9
                    digit = str(i + 2)
                    result[name] = f"<{digit}"

        return result

    def _refresh_content(self) -> None:
        """Refresh the panel content."""
        if not self._ancestors and not self._descendant_tree:
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

        # CHILDREN section (tree view)
        if self._descendant_tree:
            if self._ancestors:
                text.append("\n\n")  # Blank line between sections
            text.append("CHILDREN", style="bold #87D7FF")
            self._render_tree(self._descendant_tree, text)

        self.update(text)

    def _render_tree(self, nodes: list[_ChildNode], text: Text) -> None:
        """Render descendant tree as flat list (no indentation)."""
        for node in nodes:
            text.append("\n")
            text.append(f"  [{node.key}] ", style="bold #FFAF00")
            text.append(node.name, style="#00D7AF")
            # Recursively render children
            self._render_tree(node.children, text)

    def clear(self) -> None:
        """Clear the panel."""
        self._ancestors = []
        self._descendant_tree = []
        self._ancestor_keys = {}
        self._children_keys = {}
        self.display = False
