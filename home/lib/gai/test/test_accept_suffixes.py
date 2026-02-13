"""Tests for _strip_accept_suffixes helper."""

from ace.tui.actions.hints._accept import _strip_accept_suffixes


def test_no_suffixes() -> None:
    """Plain args return both flags False."""
    args, should_mail, skip_amend = _strip_accept_suffixes(["a", "b", "c"])
    assert args == ["a", "b", "c"]
    assert should_mail is False
    assert skip_amend is False


def test_bang_suffix_only() -> None:
    """! suffix sets skip_amend."""
    args, should_mail, skip_amend = _strip_accept_suffixes(["a", "b", "c!"])
    assert args == ["a", "b", "c"]
    assert should_mail is False
    assert skip_amend is True


def test_at_suffix_only() -> None:
    """@ suffix sets should_mail (backward compat)."""
    args, should_mail, skip_amend = _strip_accept_suffixes(["a", "b", "c@"])
    assert args == ["a", "b", "c"]
    assert should_mail is True
    assert skip_amend is False


def test_bang_at_combined() -> None:
    """!@ sets both flags."""
    args, should_mail, skip_amend = _strip_accept_suffixes(["a", "b", "c!@"])
    assert args == ["a", "b", "c"]
    assert should_mail is True
    assert skip_amend is True


def test_at_bang_combined() -> None:
    """@! sets both flags (reversed order)."""
    args, should_mail, skip_amend = _strip_accept_suffixes(["a", "b", "c@!"])
    assert args == ["a", "b", "c"]
    assert should_mail is True
    assert skip_amend is True


def test_bang_alone_is_error() -> None:
    """! as the only arg results in None (error)."""
    args, should_mail, skip_amend = _strip_accept_suffixes(["!"])
    assert args is None
    assert skip_amend is True


def test_at_alone_is_error() -> None:
    """@ as the only arg results in None (error)."""
    args, should_mail, skip_amend = _strip_accept_suffixes(["@"])
    assert args is None
    assert should_mail is True


def test_empty_args() -> None:
    """Empty args list returns None."""
    args, should_mail, skip_amend = _strip_accept_suffixes([])
    assert args is None
    assert should_mail is False
    assert skip_amend is False


def test_single_arg_with_bang() -> None:
    """Single arg with ! suffix works."""
    args, should_mail, skip_amend = _strip_accept_suffixes(["c!"])
    assert args == ["c"]
    assert skip_amend is True
    assert should_mail is False


def test_multiple_bangs_idempotent() -> None:
    """Multiple ! suffixes are handled (idempotent)."""
    args, should_mail, skip_amend = _strip_accept_suffixes(["c!!"])
    assert args == ["c"]
    assert skip_amend is True
    assert should_mail is False


def test_multiple_ats_idempotent() -> None:
    """Multiple @ suffixes are handled (idempotent)."""
    args, should_mail, skip_amend = _strip_accept_suffixes(["c@@"])
    assert args == ["c"]
    assert skip_amend is False
    assert should_mail is True
