"""Tests for the snippet_config module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from snippet_config import (
    _load_snippets,
    get_all_snippets,
)


def test_load_snippets_valid_config() -> None:
    """Test loading valid snippets from config."""
    yaml_content = """
snippets:
  foo: "The foo content"
  bar: "The bar content with {1}"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("snippet_config._get_config_path", return_value=config_path):
        snippets = _load_snippets()

    assert len(snippets) == 2
    assert snippets["foo"] == "The foo content"
    assert snippets["bar"] == "The bar content with {1}"

    Path(config_path).unlink()


def test_load_snippets_missing_key_returns_empty() -> None:
    """Test loading when snippets key is missing returns empty dict."""
    yaml_content = """
mentor_profiles:
  - name: test
    mentors:
      - name: m
        prompt: p
    file_globs:
      - "*.py"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("snippet_config._get_config_path", return_value=config_path):
        snippets = _load_snippets()

    assert snippets == {}

    Path(config_path).unlink()


def test_load_snippets_with_multiline_content() -> None:
    """Test loading snippets with multiline content."""
    yaml_content = """
snippets:
  multiline: |
    First line
    Second line
    Third line
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("snippet_config._get_config_path", return_value=config_path):
        snippets = _load_snippets()

    assert "multiline" in snippets
    assert "First line" in snippets["multiline"]
    assert "Second line" in snippets["multiline"]

    Path(config_path).unlink()


def test_load_snippets_invalid_not_dict_raises_error() -> None:
    """Test loading raises ValueError when snippets is not a dictionary."""
    yaml_content = """
snippets:
  - "foo"
  - "bar"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("snippet_config._get_config_path", return_value=config_path):
        with pytest.raises(ValueError, match="must be a dictionary"):
            _load_snippets()

    Path(config_path).unlink()


def test_load_snippets_content_not_string_raises_error() -> None:
    """Test loading raises ValueError when snippet content is not a string."""
    yaml_content = """
snippets:
  foo:
    nested: value
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("snippet_config._get_config_path", return_value=config_path):
        with pytest.raises(ValueError, match="content must be a string"):
            _load_snippets()

    Path(config_path).unlink()


def test_get_all_snippets() -> None:
    """Test getting all snippets."""
    yaml_content = """
snippets:
  foo: "Foo content"
  bar: "Bar content"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("snippet_config._get_config_path", return_value=config_path):
        snippets = get_all_snippets()

    assert len(snippets) == 2
    assert snippets["foo"] == "Foo content"
    assert snippets["bar"] == "Bar content"

    Path(config_path).unlink()


def test_get_all_snippets_config_error() -> None:
    """Test that get_all_snippets returns empty dict on config errors."""
    with patch("snippet_config._get_config_path", return_value="/nonexistent/path.yml"):
        snippets = get_all_snippets()

    assert snippets == {}
