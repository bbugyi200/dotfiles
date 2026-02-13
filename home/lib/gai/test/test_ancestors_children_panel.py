"""Tests for AncestorsChildrenPanel sibling logic."""

from ace.changespec import ChangeSpec
from ace.tui.widgets.ancestors_children_panel import AncestorsChildrenPanel
from conftest import _ChangeSpecFactory


def _find_siblings_and_keys(
    current_name: str,
    current_status: str,
    sibling_specs: list[tuple[str, str]],
    hide_reverted: bool = False,
) -> tuple[AncestorsChildrenPanel, list[str], dict[str, str]]:
    """Helper to call _find_siblings and _assign_sibling_keys directly.

    Args:
        current_name: Name of the currently selected ChangeSpec.
        current_status: Status of the currently selected ChangeSpec.
        sibling_specs: List of (name, status) tuples for other ChangeSpecs.
        hide_reverted: Whether to hide reverted/archived siblings.

    Returns:
        Tuple of (panel, sibling_names, sibling_keys).
    """
    current = _ChangeSpecFactory.create(name=current_name, status=current_status)
    all_cs: list[ChangeSpec] = [current] + [
        _ChangeSpecFactory.create(name=n, status=s) for n, s in sibling_specs
    ]
    panel = AncestorsChildrenPanel.__new__(AncestorsChildrenPanel)
    panel._hidden_reverted_sibling_count = 0
    siblings = panel._find_siblings(current, all_cs, hide_reverted)
    keys = panel._assign_sibling_keys(siblings)
    return panel, siblings, keys


def test_suffixed_finds_non_suffixed_sibling() -> None:
    """A suffixed (Reverted) ChangeSpec should find its non-suffixed (Drafted) sibling."""
    _, siblings, _ = _find_siblings_and_keys(
        current_name="pat_no_last_7_days__1",
        current_status="Reverted",
        sibling_specs=[("pat_no_last_7_days", "Drafted")],
    )
    assert siblings == ["pat_no_last_7_days"]


def test_non_suffixed_finds_suffixed_siblings() -> None:
    """A non-suffixed (Drafted) ChangeSpec should find its suffixed (Reverted) siblings."""
    _, siblings, _ = _find_siblings_and_keys(
        current_name="pat_no_last_7_days",
        current_status="Drafted",
        sibling_specs=[
            ("pat_no_last_7_days__1", "Reverted"),
            ("pat_no_last_7_days__2", "Reverted"),
        ],
    )
    assert siblings == ["pat_no_last_7_days__1", "pat_no_last_7_days__2"]


def test_non_suffixed_sibling_sorts_first() -> None:
    """Non-suffixed sibling (suffix_num=0) should sort before suffixed ones."""
    _, siblings, _ = _find_siblings_and_keys(
        current_name="pat_no_last_7_days__2",
        current_status="Reverted",
        sibling_specs=[
            ("pat_no_last_7_days__1", "Reverted"),
            ("pat_no_last_7_days", "Drafted"),
        ],
    )
    assert siblings == ["pat_no_last_7_days", "pat_no_last_7_days__1"]


def test_hide_reverted_hides_reverted_siblings_from_non_suffixed() -> None:
    """With hide_reverted=True, Reverted siblings should be hidden from a Drafted ChangeSpec."""
    panel, siblings, _ = _find_siblings_and_keys(
        current_name="foo",
        current_status="Drafted",
        sibling_specs=[
            ("foo__1", "Reverted"),
            ("foo__2", "Archived"),
        ],
        hide_reverted=True,
    )
    assert siblings == []
    assert panel._hidden_reverted_sibling_count == 2


def test_hide_reverted_keeps_drafted_sibling_from_suffixed() -> None:
    """With hide_reverted=True, a Drafted (non-suffixed) sibling should still be shown."""
    _, siblings, _ = _find_siblings_and_keys(
        current_name="foo__1",
        current_status="Reverted",
        sibling_specs=[
            ("foo", "Drafted"),
            ("foo__2", "Reverted"),
        ],
        hide_reverted=True,
    )
    assert siblings == ["foo"]


def test_suffixed_finds_other_suffixed_siblings() -> None:
    """Suffixed ChangeSpec finds other suffixed siblings (existing behavior)."""
    _, siblings, _ = _find_siblings_and_keys(
        current_name="bar__1",
        current_status="Reverted",
        sibling_specs=[
            ("bar__2", "Reverted"),
            ("bar__3", "Reverted"),
        ],
    )
    assert siblings == ["bar__2", "bar__3"]


def test_no_siblings_returns_empty() -> None:
    """ChangeSpec with no siblings returns empty list."""
    _, siblings, _ = _find_siblings_and_keys(
        current_name="unique_name",
        current_status="Drafted",
        sibling_specs=[
            ("different_base__1", "Reverted"),
            ("other_thing", "Drafted"),
        ],
    )
    assert siblings == []


def test_sibling_keys_assigned_correctly() -> None:
    """Sibling keys should be assigned for navigation."""
    _, siblings, sibling_keys = _find_siblings_and_keys(
        current_name="baz__1",
        current_status="Reverted",
        sibling_specs=[
            ("baz", "Drafted"),
            ("baz__2", "Reverted"),
        ],
    )
    assert len(siblings) == 2
    assert "~~" in sibling_keys
    assert "~a" in sibling_keys
    assert sibling_keys["~~"] == "baz"
    assert sibling_keys["~a"] == "baz__2"


def test_single_sibling_gets_tilde_key() -> None:
    """A single sibling should get the '~' key (not '~~')."""
    _, siblings, sibling_keys = _find_siblings_and_keys(
        current_name="qux__1",
        current_status="Reverted",
        sibling_specs=[("qux", "Drafted")],
    )
    assert len(siblings) == 1
    assert "~" in sibling_keys
    assert sibling_keys["~"] == "qux"
