"""Tests for ace.hooks.defaults module."""

from unittest.mock import patch

from ace.hooks.defaults import get_required_changespec_hooks


def test_get_required_changespec_hooks_returns_defaults_when_no_config() -> None:
    """Test that defaults are returned when config file doesn't exist."""
    with patch("ace.hooks.defaults.get_vcs_provider_config", return_value={}):
        result = get_required_changespec_hooks()

    assert result == ("!$bb_hg_presubmit", "$bb_hg_lint")


def test_get_required_changespec_hooks_returns_defaults_when_no_key() -> None:
    """Test that defaults are returned when config has no default_hooks key."""
    with patch(
        "ace.hooks.defaults.get_vcs_provider_config",
        return_value={"provider": "auto"},
    ):
        result = get_required_changespec_hooks()

    assert result == ("!$bb_hg_presubmit", "$bb_hg_lint")


def test_get_required_changespec_hooks_uses_config_override() -> None:
    """Test that config override is used when present."""
    with patch(
        "ace.hooks.defaults.get_vcs_provider_config",
        return_value={"default_hooks": ["!$my_presubmit", "$my_lint"]},
    ):
        result = get_required_changespec_hooks()

    assert result == ("!$my_presubmit", "$my_lint")


def test_get_required_changespec_hooks_ignores_empty_list() -> None:
    """Test that empty list falls back to defaults."""
    with patch(
        "ace.hooks.defaults.get_vcs_provider_config",
        return_value={"default_hooks": []},
    ):
        result = get_required_changespec_hooks()

    assert result == ("!$bb_hg_presubmit", "$bb_hg_lint")


def test_get_required_changespec_hooks_ignores_none() -> None:
    """Test that None value falls back to defaults."""
    with patch(
        "ace.hooks.defaults.get_vcs_provider_config",
        return_value={"default_hooks": None},
    ):
        result = get_required_changespec_hooks()

    assert result == ("!$bb_hg_presubmit", "$bb_hg_lint")
