"""Ancestors and Children panel widget for the ace TUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gai_utils import has_suffix, strip_reverted_suffix
from rich.text import Text
from textual.widgets import Static

from ...changespec import ChangeSpec


def _get_simple_status_indicator(status: str) -> tuple[str, str]:
    """Get a simple status indicator character and color."""
    if status.startswith("Drafted"):
        return "D", "#87D700"
    elif status.startswith("Mailed"):
        return "M", "#00D787"
    elif status.startswith("Submitted"):
        return "S", "#00AF00"
    elif status.startswith("Reverted"):
        return "X", "#808080"
    return "W", "#FFD700"  # WIP - gold


@dataclass
class _ChildNode:
    """A node in the descendant tree."""

    name: str
    key: str  # e.g., ">>" for first, ">a", ">b", ... for subsequent
    is_leaf: bool
    depth: int
    status: str
    children: list[_ChildNode] = field(default_factory=list)


class AncestorsChildrenPanel(Static):
    """Panel showing ancestors and all descendants of the current ChangeSpec."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._ancestors: list[str] = []  # Ordered: parent, grandparent, etc.
        self._ancestor_statuses: dict[str, str] = {}  # name -> status
        self._descendant_tree: list[_ChildNode] = []  # Tree of all descendants
        self._ancestor_keys: dict[str, str] = {}  # name -> key hint
        self._children_keys: dict[str, str] = {}  # key -> name (for navigation)
        self._hidden_reverted_count: int = 0  # Count of hidden reverted entries
        # Sibling-related fields
        self._siblings: list[str] = []  # Sibling names sorted by suffix number
        self._sibling_statuses: dict[str, str] = {}  # name -> status
        self._sibling_keys: dict[str, str] = {}  # key -> name (for navigation)
        self._hidden_reverted_sibling_count: int = (
            0  # Count of hidden reverted siblings
        )

    def update_relationships(
        self,
        changespec: ChangeSpec,
        all_changespecs: list[ChangeSpec],
        hide_reverted: bool = False,
    ) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
        """Update with ancestors and descendants of current ChangeSpec.

        Args:
            changespec: Currently selected ChangeSpec
            all_changespecs: All changespecs (for finding children)
            hide_reverted: Whether to hide reverted ChangeSpecs from display

        Returns:
            Tuple of (ancestor_keys, children_keys, sibling_keys) mappings
            - ancestor_keys: name -> key (e.g., {"parent": "<<"})
            - children_keys: key -> name (e.g., {">>": "child1", ">2a": "grandchild"})
            - sibling_keys: key -> name (e.g., {"~~": "foo__1", "~a": "foo__2"})
        """
        # Reset hidden counts
        self._hidden_reverted_count = 0
        self._hidden_reverted_sibling_count = 0

        # Build ancestors (recursive parent traversal)
        self._ancestors = self._find_ancestors(
            changespec, all_changespecs, hide_reverted
        )

        # Build descendant tree (recursive child traversal)
        self._descendant_tree = self._build_descendant_tree(
            changespec.name, all_changespecs, hide_reverted
        )

        # Build siblings (same base name with __<N> suffix)
        self._siblings = self._find_siblings(changespec, all_changespecs, hide_reverted)

        # Assign keybindings
        self._ancestor_keys = self._assign_ancestor_keys(self._ancestors)
        self._children_keys = self._build_children_keys_map(self._descendant_tree)
        self._sibling_keys = self._assign_sibling_keys(self._siblings)

        self._refresh_content()
        return self._ancestor_keys, self._children_keys, self._sibling_keys

    def get_hidden_reverted_count(self) -> int:
        """Get the count of hidden reverted entries in this panel.

        Returns:
            Number of reverted ancestors/descendants/siblings that were hidden.
        """
        return self._hidden_reverted_count + self._hidden_reverted_sibling_count

    def _find_ancestors(
        self,
        changespec: ChangeSpec,
        all_changespecs: list[ChangeSpec],
        hide_reverted: bool = False,
    ) -> list[str]:
        """Find all ancestors recursively (parent, grandparent, etc.).

        Args:
            changespec: The starting ChangeSpec
            all_changespecs: All changespecs for lookup
            hide_reverted: Whether to hide reverted ancestors from display
                          (but continue traversal through them)
        """
        name_map = {cs.name.lower(): cs for cs in all_changespecs}
        ancestors: list[str] = []
        self._ancestor_statuses = {}
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
                # Check if we should hide this reverted ancestor
                if hide_reverted and parent_cs.status.startswith("Reverted"):
                    self._hidden_reverted_count += 1
                    # Continue traversal but don't add to display list
                    current = parent_cs
                    continue
                ancestors.append(parent_cs.name)  # Use actual case
                self._ancestor_statuses[parent_cs.name] = parent_cs.status
                current = parent_cs
            else:
                # Parent not found in list (might be filtered out)
                ancestors.append(parent_name)
                self._ancestor_statuses[parent_name] = "WIP"
                break

        return ancestors

    def _find_siblings(
        self,
        changespec: ChangeSpec,
        all_changespecs: list[ChangeSpec],
        hide_reverted: bool = False,
    ) -> list[str]:
        """Find all sibling ChangeSpecs (same base name with __<N> suffix).

        Siblings are ChangeSpecs that share the same base name after stripping
        the __<N> suffix. Only ChangeSpecs WITH a suffix can have siblings.

        Args:
            changespec: The starting ChangeSpec
            all_changespecs: All changespecs for lookup
            hide_reverted: Whether to hide reverted siblings from display

        Returns:
            List of sibling names sorted by suffix number, excluding current.
        """
        self._sibling_statuses = {}

        # Only ChangeSpecs WITH a suffix can have siblings
        if not has_suffix(changespec.name):
            return []

        # Get base name for comparison (case-insensitive)
        base_name = strip_reverted_suffix(changespec.name).lower()

        # Find all siblings (same base name, different suffix, not self)
        siblings: list[tuple[int, str, str]] = []  # (suffix_num, name, status)
        for cs in all_changespecs:
            if cs.name.lower() == changespec.name.lower():
                continue  # Skip self
            if not has_suffix(cs.name):
                continue  # Skip non-suffixed names
            if strip_reverted_suffix(cs.name).lower() != base_name:
                continue  # Different base name

            # Check if we should hide this reverted sibling
            if hide_reverted and cs.status.startswith("Reverted"):
                self._hidden_reverted_sibling_count += 1
                continue

            # Extract suffix number for sorting
            import re

            match = re.match(r"^.+__(\d+)$", cs.name)
            suffix_num = int(match.group(1)) if match else 0
            siblings.append((suffix_num, cs.name, cs.status))

        # Sort by suffix number ascending
        siblings.sort(key=lambda x: x[0])

        # Build result list and status map
        result: list[str] = []
        for _, name, status in siblings:
            result.append(name)
            self._sibling_statuses[name] = status

        return result

    def _build_descendant_tree(
        self,
        parent_name: str,
        all_changespecs: list[ChangeSpec],
        hide_reverted: bool = False,
    ) -> list[_ChildNode]:
        """Build tree of all descendants with assigned keymaps.

        Args:
            parent_name: Name of the parent ChangeSpec
            all_changespecs: All changespecs for lookup
            hide_reverted: Whether to hide reverted descendants
        """
        # Build lookup for finding children
        children_map: dict[str, list[str]] = {}
        status_map: dict[str, str] = {}
        for cs in all_changespecs:
            status_map[cs.name.lower()] = cs.status
            if cs.parent:
                parent_lower = cs.parent.lower()
                if parent_lower not in children_map:
                    children_map[parent_lower] = []
                children_map[parent_lower].append(cs.name)

        # Build tree recursively with a counter for sequential key assignment
        # counter[0] tracks position across entire tree (pre-order traversal)
        counter: list[int] = [0]
        direct_children = children_map.get(parent_name.lower(), [])
        return self._build_subtree(
            direct_children,
            children_map,
            status_map,
            depth=0,
            counter=counter,
            hide_reverted=hide_reverted,
        )

    def _build_subtree(
        self,
        child_names: list[str],
        children_map: dict[str, list[str]],
        status_map: dict[str, str],
        depth: int,
        counter: list[int],
        hide_reverted: bool = False,
    ) -> list[_ChildNode]:
        """Recursively build subtree with simple sequential keymaps.

        Key assignment pattern (sequential across entire tree):
        - First descendant (any depth): >> (displayed as [>])
        - All subsequent descendants: >a, >b, >c, ... >z (sequential)

        Args:
            child_names: Names of children to process
            children_map: Map of parent name -> list of child names
            status_map: Map of name -> status
            depth: Current depth in tree
            counter: Mutable counter [position] for sequential key assignment
            hide_reverted: Whether to hide reverted descendants
        """
        if not child_names:
            return []

        # Filter out reverted children if hide_reverted is True
        if hide_reverted:
            filtered_names: list[str] = []
            for name in child_names:
                status = status_map.get(name.lower(), "WIP")
                if status.startswith("Reverted"):
                    self._hidden_reverted_count += 1
                else:
                    filtered_names.append(name)
            child_names = filtered_names

        if not child_names:
            return []

        nodes: list[_ChildNode] = []

        # Special case: single leaf child at depth 0 gets ">"
        if depth == 0 and len(child_names) == 1:
            name = child_names[0]
            grandchildren_names = children_map.get(name.lower(), [])
            # Also filter grandchildren for leaf check
            if hide_reverted:
                grandchildren_names = [
                    n
                    for n in grandchildren_names
                    if not status_map.get(n.lower(), "WIP").startswith("Reverted")
                ]
            is_leaf = len(grandchildren_names) == 0
            if is_leaf:
                # Single leaf child: use ">"
                counter[0] += 1  # Still increment counter
                return [
                    _ChildNode(
                        name=name,
                        key=">",
                        is_leaf=True,
                        depth=0,
                        status=status_map.get(name.lower(), "WIP"),
                        children=[],
                    )
                ]

        for name in child_names:
            # Get grandchildren
            grandchildren_names = children_map.get(name.lower(), [])
            # Filter for is_leaf check (but don't count as hidden - that happens in recursion)
            visible_grandchildren = grandchildren_names
            if hide_reverted:
                visible_grandchildren = [
                    n
                    for n in grandchildren_names
                    if not status_map.get(n.lower(), "WIP").startswith("Reverted")
                ]
            is_leaf = len(visible_grandchildren) == 0

            # Assign key based on counter position
            pos = counter[0]
            if pos == 0:
                # First descendant: >>
                key = ">>"
            elif pos <= 26:
                # Subsequent descendants: >a, >b, ... >z
                key = ">" + chr(ord("a") + pos - 1)
            else:
                # Skip if too many descendants (over 27: >> + a-z)
                counter[0] += 1
                continue

            counter[0] += 1

            # Recursively build children (pre-order: process children after this node)
            children_nodes = self._build_subtree(
                grandchildren_names,
                children_map,
                status_map,
                depth + 1,
                counter,
                hide_reverted=hide_reverted,
            )

            nodes.append(
                _ChildNode(
                    name=name,
                    key=key,
                    is_leaf=is_leaf,
                    depth=depth,
                    status=status_map.get(name.lower(), "WIP"),
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

        Pattern: "<" (single), "<<" (first), "<a", "<b", etc.
        """
        if not names:
            return {}

        result: dict[str, str] = {}

        if len(names) == 1:
            result[names[0]] = "<"
        else:
            # First item gets double prefix
            result[names[0]] = "<<"
            # Remaining get letter suffixes (a-z)
            for i, name in enumerate(names[1:], start=0):
                if i < 26:  # a-z
                    letter = chr(ord("a") + i)
                    result[name] = f"<{letter}"

        return result

    def _assign_sibling_keys(self, names: list[str]) -> dict[str, str]:
        """Assign keybindings to siblings.

        Pattern: "~" (single), "~~" (first of multiple), "~a", "~b", etc.

        Args:
            names: List of sibling names (sorted by suffix number).

        Returns:
            Dict mapping key -> name (e.g., {"~~": "foo__1", "~a": "foo__2"}).
        """
        if not names:
            return {}

        result: dict[str, str] = {}

        if len(names) == 1:
            result["~"] = names[0]
        else:
            # First item gets double prefix
            result["~~"] = names[0]
            # Remaining get letter suffixes (a-z)
            for i, name in enumerate(names[1:], start=0):
                if i < 26:  # a-z
                    letter = chr(ord("a") + i)
                    result[f"~{letter}"] = name

        return result

    def _refresh_content(self) -> None:
        """Refresh the panel content."""
        if not self._ancestors and not self._descendant_tree and not self._siblings:
            self.display = False
            return

        self.display = True
        text = Text()
        has_previous_section = False

        # ANCESTORS section (reversed: show furthest ancestor first)
        if self._ancestors:
            text.append("ANCESTORS", style="bold #87D7FF")
            for name in reversed(self._ancestors):
                key = self._ancestor_keys.get(name, "")
                text.append("\n")
                text.append(f"  [{key}] ", style="bold #FFAF00")
                text.append(name, style="#00D7AF")
                status = self._ancestor_statuses.get(name, "WIP")
                indicator, color = _get_simple_status_indicator(status)
                if indicator:
                    text.append(f" [{indicator}]", style=f"bold {color}")
            has_previous_section = True

        # CHILDREN section (tree view)
        if self._descendant_tree:
            if has_previous_section:
                text.append("\n\n")  # Blank line between sections
            text.append("CHILDREN", style="bold #87D7FF")
            self._render_tree(self._descendant_tree, text)
            has_previous_section = True

        # SIBLINGS section
        if self._siblings:
            if has_previous_section:
                text.append("\n\n")  # Blank line between sections
            text.append("SIBLINGS", style="bold #87D7FF")
            for name in self._siblings:
                # Find key for this sibling (reverse lookup)
                key = ""
                for k, n in self._sibling_keys.items():
                    if n == name:
                        key = k
                        break
                text.append("\n")
                text.append(f"  [{key}] ", style="bold #FFAF00")
                text.append(name, style="#00D7AF")
                status = self._sibling_statuses.get(name, "WIP")
                indicator, color = _get_simple_status_indicator(status)
                if indicator:
                    text.append(f" [{indicator}]", style=f"bold {color}")

        self.update(text)

    def _render_tree(
        self, nodes: list[_ChildNode], text: Text, prefix: str = ""
    ) -> None:
        """Render descendant tree with box-drawing visualization.

        Args:
            nodes: List of child nodes to render
            text: Rich Text object to append to
            prefix: Prefix string for indentation (used for nested levels)
        """
        for i, node in enumerate(nodes):
            is_last = i == len(nodes) - 1
            text.append("\n")

            if node.depth == 0:
                # Direct children: render with standard indentation
                text.append(f"  [{node.key}] ", style="bold #FFAF00")
                text.append(node.name, style="#00D7AF")
                indicator, color = _get_simple_status_indicator(node.status)
                if indicator:
                    text.append(f" [{indicator}]", style=f"bold {color}")

                # Render descendants with tree structure
                # Prefix starts with 6 spaces to align under the name
                if node.children:
                    self._render_tree(node.children, text, prefix="      ")
            else:
                # Descendants: render with tree branches
                branch = "└─" if is_last else "├─"
                text.append(f"{prefix}{branch} ", style="dim")
                text.append(f"[{node.key}] ", style="bold #FFAF00")
                text.append(node.name, style="#00D7AF")
                indicator, color = _get_simple_status_indicator(node.status)
                if indicator:
                    text.append(f" [{indicator}]", style=f"bold {color}")

                # Recursively render children with updated prefix
                if node.children:
                    # Add "│  " if not last, "   " if last
                    child_prefix = prefix + ("   " if is_last else "│  ")
                    self._render_tree(node.children, text, prefix=child_prefix)

    def clear(self) -> None:
        """Clear the panel."""
        self._ancestors = []
        self._ancestor_statuses = {}
        self._descendant_tree = []
        self._ancestor_keys = {}
        self._children_keys = {}
        self._hidden_reverted_count = 0
        # Clear sibling-related fields
        self._siblings = []
        self._sibling_statuses = {}
        self._sibling_keys = {}
        self._hidden_reverted_sibling_count = 0
        self.display = False
