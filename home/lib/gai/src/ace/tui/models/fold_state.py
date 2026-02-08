"""Fold state management for nested workflow steps in the Agents tab."""

from enum import Enum


class FoldLevel(Enum):
    """Fold level for a workflow entry's children."""

    COLLAPSED = "collapsed"
    EXPANDED = "expanded"
    FULLY_EXPANDED = "fully_expanded"


class FoldStateManager:
    """Manages fold state for workflow entries in the Agents tab.

    Each workflow is identified by its raw_suffix (timestamp string).
    Default fold state is COLLAPSED.
    """

    def __init__(self) -> None:
        self._states: dict[str, FoldLevel] = {}

    def get(self, key: str) -> FoldLevel:
        """Get the fold level for a workflow key.

        Args:
            key: Workflow raw_suffix (timestamp).

        Returns:
            Current fold level (defaults to COLLAPSED).
        """
        return self._states.get(key, FoldLevel.COLLAPSED)

    def expand(self, key: str) -> bool:
        """Advance fold level one step: COLLAPSED -> EXPANDED -> FULLY_EXPANDED.

        Args:
            key: Workflow raw_suffix (timestamp).

        Returns:
            True if the level changed, False if already fully expanded.
        """
        current = self.get(key)
        if current == FoldLevel.COLLAPSED:
            self._states[key] = FoldLevel.EXPANDED
            return True
        if current == FoldLevel.EXPANDED:
            self._states[key] = FoldLevel.FULLY_EXPANDED
            return True
        return False

    def collapse(self, key: str) -> bool:
        """Retreat fold level one step: FULLY_EXPANDED -> EXPANDED -> COLLAPSED.

        Args:
            key: Workflow raw_suffix (timestamp).

        Returns:
            True if the level changed, False if already collapsed.
        """
        current = self.get(key)
        if current == FoldLevel.FULLY_EXPANDED:
            self._states[key] = FoldLevel.EXPANDED
            return True
        if current == FoldLevel.EXPANDED:
            self._states[key] = FoldLevel.COLLAPSED
            return True
        return False

    def expand_all(self, keys: list[str]) -> bool:
        """Expand all given workflow keys one level.

        Args:
            keys: List of workflow raw_suffix strings.

        Returns:
            True if any level changed.
        """
        changed = False
        for key in keys:
            if self.expand(key):
                changed = True
        return changed

    def collapse_all(self, keys: list[str]) -> bool:
        """Collapse all given workflow keys one level.

        If any are FULLY_EXPANDED, only collapse those (to EXPANDED).
        Otherwise, collapse all EXPANDED to COLLAPSED.

        Args:
            keys: List of workflow raw_suffix strings.

        Returns:
            True if any level changed.
        """
        # First pass: if any are fully expanded, only collapse those
        if self.has_any_fully_expanded(keys):
            changed = False
            for key in keys:
                if self.get(key) == FoldLevel.FULLY_EXPANDED:
                    self._states[key] = FoldLevel.EXPANDED
                    changed = True
            return changed

        # Second pass: collapse all expanded to collapsed
        changed = False
        for key in keys:
            if self.collapse(key):
                changed = True
        return changed

    def has_any_fully_expanded(self, keys: list[str]) -> bool:
        """Check if any of the given keys are fully expanded.

        Args:
            keys: List of workflow raw_suffix strings.

        Returns:
            True if any key is at FULLY_EXPANDED level.
        """
        return any(self.get(key) == FoldLevel.FULLY_EXPANDED for key in keys)
