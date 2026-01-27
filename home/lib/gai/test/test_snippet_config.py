"""Tests for the snippet_config module (backward compatibility wrapper for xprompt.loader).

Note: Most functionality is now tested in test_xprompt_loader.py.
This file only tests the backward compatibility of the snippet_config wrapper.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

from snippet_config import get_all_snippets


def test_get_all_snippets_backward_compatibility() -> None:
    """Test that get_all_snippets from snippet_config still works."""
    yaml_content = """
xprompts:
  foo: "Foo content"
  bar: "Bar content"
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        config_path = f.name

    with (
        patch("xprompt.loader._get_config_path", return_value=config_path),
        patch("xprompt.loader._load_xprompts_from_files", return_value={}),
        patch("xprompt.loader._load_xprompts_from_internal", return_value={}),
    ):
        snippets = get_all_snippets()

    # Returns dict[str, str] (not XPrompt objects)
    assert isinstance(snippets, dict)
    assert len(snippets) == 2
    assert snippets["foo"] == "Foo content"
    assert snippets["bar"] == "Bar content"

    Path(config_path).unlink()


def test_get_all_snippets_supports_legacy_snippets_key() -> None:
    """Test that legacy 'snippets' key in config still works."""
    yaml_content = """
snippets:
  legacy: "Legacy content"
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        config_path = f.name

    with (
        patch("xprompt.loader._get_config_path", return_value=config_path),
        patch("xprompt.loader._load_xprompts_from_files", return_value={}),
        patch("xprompt.loader._load_xprompts_from_internal", return_value={}),
    ):
        snippets = get_all_snippets()

    assert "legacy" in snippets
    assert snippets["legacy"] == "Legacy content"

    Path(config_path).unlink()


def test_get_all_snippets_returns_empty_on_missing_config() -> None:
    """Test that get_all_snippets returns empty dict when config is missing."""
    with (
        patch("xprompt.loader._get_config_path", return_value="/nonexistent/path.yml"),
        patch("xprompt.loader._load_xprompts_from_files", return_value={}),
        patch("xprompt.loader._load_xprompts_from_internal", return_value={}),
    ):
        snippets = get_all_snippets()

    assert snippets == {}
