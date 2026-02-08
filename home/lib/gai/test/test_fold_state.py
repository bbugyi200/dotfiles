"""Tests for FoldStateManager."""

from ace.tui.models.fold_state import FoldLevel, FoldStateManager


def test_default_fold_level_is_collapsed() -> None:
    """Test that unknown keys default to COLLAPSED."""
    mgr = FoldStateManager()
    assert mgr.get("unknown") == FoldLevel.COLLAPSED


def test_expand_from_collapsed_to_expanded() -> None:
    """Test expand advances COLLAPSED -> EXPANDED."""
    mgr = FoldStateManager()
    assert mgr.expand("key1") is True
    assert mgr.get("key1") == FoldLevel.EXPANDED


def test_expand_from_expanded_to_fully_expanded() -> None:
    """Test expand advances EXPANDED -> FULLY_EXPANDED."""
    mgr = FoldStateManager()
    mgr.expand("key1")
    assert mgr.expand("key1") is True
    assert mgr.get("key1") == FoldLevel.FULLY_EXPANDED


def test_expand_from_fully_expanded_returns_false() -> None:
    """Test expand returns False when already fully expanded."""
    mgr = FoldStateManager()
    mgr.expand("key1")
    mgr.expand("key1")
    assert mgr.expand("key1") is False
    assert mgr.get("key1") == FoldLevel.FULLY_EXPANDED


def test_collapse_from_fully_expanded_to_expanded() -> None:
    """Test collapse retreats FULLY_EXPANDED -> EXPANDED."""
    mgr = FoldStateManager()
    mgr.expand("key1")
    mgr.expand("key1")
    assert mgr.collapse("key1") is True
    assert mgr.get("key1") == FoldLevel.EXPANDED


def test_collapse_from_expanded_to_collapsed() -> None:
    """Test collapse retreats EXPANDED -> COLLAPSED."""
    mgr = FoldStateManager()
    mgr.expand("key1")
    assert mgr.collapse("key1") is True
    assert mgr.get("key1") == FoldLevel.COLLAPSED


def test_collapse_from_collapsed_returns_false() -> None:
    """Test collapse returns False when already collapsed."""
    mgr = FoldStateManager()
    assert mgr.collapse("key1") is False


def test_expand_all_expands_multiple_keys() -> None:
    """Test expand_all advances all keys one level."""
    mgr = FoldStateManager()
    changed = mgr.expand_all(["k1", "k2", "k3"])
    assert changed is True
    assert mgr.get("k1") == FoldLevel.EXPANDED
    assert mgr.get("k2") == FoldLevel.EXPANDED
    assert mgr.get("k3") == FoldLevel.EXPANDED


def test_expand_all_returns_false_when_all_fully_expanded() -> None:
    """Test expand_all returns False when no changes possible."""
    mgr = FoldStateManager()
    mgr.expand_all(["k1", "k2"])
    mgr.expand_all(["k1", "k2"])
    assert mgr.expand_all(["k1", "k2"]) is False


def test_collapse_all_collapses_fully_expanded_first() -> None:
    """Test collapse_all only collapses FULLY_EXPANDED keys when present."""
    mgr = FoldStateManager()
    # k1: FULLY_EXPANDED, k2: EXPANDED
    mgr.expand("k1")
    mgr.expand("k1")
    mgr.expand("k2")

    changed = mgr.collapse_all(["k1", "k2"])
    assert changed is True
    # k1 should go from FULLY_EXPANDED -> EXPANDED
    assert mgr.get("k1") == FoldLevel.EXPANDED
    # k2 should remain EXPANDED (only fully_expanded was collapsed)
    assert mgr.get("k2") == FoldLevel.EXPANDED


def test_collapse_all_collapses_expanded_when_no_fully_expanded() -> None:
    """Test collapse_all collapses EXPANDED keys when no FULLY_EXPANDED."""
    mgr = FoldStateManager()
    mgr.expand("k1")
    mgr.expand("k2")

    changed = mgr.collapse_all(["k1", "k2"])
    assert changed is True
    assert mgr.get("k1") == FoldLevel.COLLAPSED
    assert mgr.get("k2") == FoldLevel.COLLAPSED


def test_collapse_all_returns_false_when_all_collapsed() -> None:
    """Test collapse_all returns False when nothing to collapse."""
    mgr = FoldStateManager()
    assert mgr.collapse_all(["k1", "k2"]) is False


def test_has_any_fully_expanded() -> None:
    """Test has_any_fully_expanded detection."""
    mgr = FoldStateManager()
    assert mgr.has_any_fully_expanded(["k1"]) is False

    mgr.expand("k1")
    assert mgr.has_any_fully_expanded(["k1"]) is False

    mgr.expand("k1")
    assert mgr.has_any_fully_expanded(["k1"]) is True


def test_has_any_fully_expanded_mixed_keys() -> None:
    """Test has_any_fully_expanded with mix of levels."""
    mgr = FoldStateManager()
    mgr.expand("k1")
    mgr.expand("k1")
    mgr.expand("k2")

    assert mgr.has_any_fully_expanded(["k1", "k2"]) is True
    assert mgr.has_any_fully_expanded(["k2"]) is False
