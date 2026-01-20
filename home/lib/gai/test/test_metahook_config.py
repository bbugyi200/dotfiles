"""Tests for the metahook_config module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from metahook_config import (
    MetahookConfig,
    _get_all_metahooks,
    _load_metahooks,
    find_matching_metahook,
)


def test_metahook_config_dataclass() -> None:
    """Test MetahookConfig dataclass."""
    config = MetahookConfig(
        name="scuba",
        hook_command="bb_rabbit_test",
        output_regex="Expected: Scuba Result PASSED",
    )

    assert config.name == "scuba"
    assert config.hook_command == "bb_rabbit_test"
    assert config.output_regex == "Expected: Scuba Result PASSED"


def test_load_metahooks_valid_config() -> None:
    """Test loading valid metahooks from config."""
    yaml_content = """
metahooks:
  - name: scuba
    hook_command: bb_rabbit_test
    output_regex: "Expected: Scuba Result PASSED"
  - name: lint
    hook_command: bb_lint
    output_regex: "lint error"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("metahook_config._get_config_path", return_value=config_path):
        metahooks = _load_metahooks()

    assert len(metahooks) == 2
    assert metahooks[0].name == "scuba"
    assert metahooks[0].hook_command == "bb_rabbit_test"
    assert metahooks[0].output_regex == "Expected: Scuba Result PASSED"
    assert metahooks[1].name == "lint"
    assert metahooks[1].hook_command == "bb_lint"
    assert metahooks[1].output_regex == "lint error"

    Path(config_path).unlink()


def test_load_metahooks_missing_key_returns_empty() -> None:
    """Test loading when metahooks key is missing returns empty list."""
    yaml_content = """
snippets:
  foo: "bar"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("metahook_config._get_config_path", return_value=config_path):
        metahooks = _load_metahooks()

    assert metahooks == []

    Path(config_path).unlink()


def test_load_metahooks_invalid_not_list_raises_error() -> None:
    """Test loading raises ValueError when metahooks is not a list."""
    yaml_content = """
metahooks:
  scuba: "value"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("metahook_config._get_config_path", return_value=config_path):
        with pytest.raises(ValueError, match="must be a list"):
            _load_metahooks()

    Path(config_path).unlink()


def test_load_metahooks_item_not_dict_raises_error() -> None:
    """Test loading raises ValueError when metahook item is not a dictionary."""
    yaml_content = """
metahooks:
  - "just_a_string"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("metahook_config._get_config_path", return_value=config_path):
        with pytest.raises(ValueError, match="must be a dictionary"):
            _load_metahooks()

    Path(config_path).unlink()


def test_load_metahooks_missing_name_raises_error() -> None:
    """Test loading raises ValueError when metahook is missing name field."""
    yaml_content = """
metahooks:
  - hook_command: bb_rabbit_test
    output_regex: "test"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("metahook_config._get_config_path", return_value=config_path):
        with pytest.raises(ValueError, match="missing required field: name"):
            _load_metahooks()

    Path(config_path).unlink()


def test_load_metahooks_missing_hook_command_raises_error() -> None:
    """Test loading raises ValueError when metahook is missing hook_command field."""
    yaml_content = """
metahooks:
  - name: scuba
    output_regex: "test"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("metahook_config._get_config_path", return_value=config_path):
        with pytest.raises(ValueError, match="missing required field: hook_command"):
            _load_metahooks()

    Path(config_path).unlink()


def test_load_metahooks_missing_output_regex_raises_error() -> None:
    """Test loading raises ValueError when metahook is missing output_regex field."""
    yaml_content = """
metahooks:
  - name: scuba
    hook_command: bb_rabbit_test
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("metahook_config._get_config_path", return_value=config_path):
        with pytest.raises(ValueError, match="missing required field: output_regex"):
            _load_metahooks()

    Path(config_path).unlink()


def test_load_metahooks_config_not_dict_raises_error() -> None:
    """Test loading raises ValueError when config is not a dictionary."""
    yaml_content = """
- just_a_list
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("metahook_config._get_config_path", return_value=config_path):
        with pytest.raises(ValueError, match="Config must be a dictionary"):
            _load_metahooks()

    Path(config_path).unlink()


def test__get_all_metahooks() -> None:
    """Test getting all metahooks."""
    yaml_content = """
metahooks:
  - name: scuba
    hook_command: bb_rabbit_test
    output_regex: "Expected: Scuba Result PASSED"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("metahook_config._get_config_path", return_value=config_path):
        metahooks = _get_all_metahooks()

    assert len(metahooks) == 1
    assert metahooks[0].name == "scuba"

    Path(config_path).unlink()


def test__get_all_metahooks_config_error() -> None:
    """Test that get_all_metahooks returns empty list on config errors."""
    with patch(
        "metahook_config._get_config_path", return_value="/nonexistent/path.yml"
    ):
        metahooks = _get_all_metahooks()

    assert metahooks == []


def test_find_matching_metahook_command_match() -> None:
    """Test find_matching_metahook with command substring match."""
    yaml_content = """
metahooks:
  - name: scuba
    hook_command: bb_rabbit_test
    output_regex: "Expected: Scuba"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("metahook_config._get_config_path", return_value=config_path):
        result = find_matching_metahook(
            "bb_rabbit_test --some-flag",
            "Output: Expected: Scuba Result PASSED",
        )

    assert result is not None
    assert result.name == "scuba"

    Path(config_path).unlink()


def test_find_matching_metahook_command_no_match() -> None:
    """Test find_matching_metahook when command doesn't match."""
    yaml_content = """
metahooks:
  - name: scuba
    hook_command: bb_rabbit_test
    output_regex: "Expected: Scuba"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("metahook_config._get_config_path", return_value=config_path):
        result = find_matching_metahook(
            "different_command",
            "Output: Expected: Scuba Result PASSED",
        )

    assert result is None

    Path(config_path).unlink()


def test_find_matching_metahook_regex_no_match() -> None:
    """Test find_matching_metahook when regex doesn't match."""
    yaml_content = """
metahooks:
  - name: scuba
    hook_command: bb_rabbit_test
    output_regex: "Expected: Scuba"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("metahook_config._get_config_path", return_value=config_path):
        result = find_matching_metahook(
            "bb_rabbit_test",
            "Some different output without the expected pattern",
        )

    assert result is None

    Path(config_path).unlink()


def test_find_matching_metahook_both_must_match() -> None:
    """Test find_matching_metahook requires both command and regex to match."""
    yaml_content = """
metahooks:
  - name: scuba
    hook_command: bb_rabbit_test
    output_regex: "Expected: Scuba"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("metahook_config._get_config_path", return_value=config_path):
        # Command matches but regex doesn't
        result1 = find_matching_metahook(
            "bb_rabbit_test",
            "No match here",
        )
        # Regex matches but command doesn't
        result2 = find_matching_metahook(
            "other_command",
            "Expected: Scuba",
        )

    assert result1 is None
    assert result2 is None

    Path(config_path).unlink()


def test_find_matching_metahook_first_match_wins() -> None:
    """Test find_matching_metahook returns first matching metahook."""
    yaml_content = """
metahooks:
  - name: first
    hook_command: bb_rabbit
    output_regex: "test"
  - name: second
    hook_command: bb_rabbit
    output_regex: "test"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("metahook_config._get_config_path", return_value=config_path):
        result = find_matching_metahook(
            "bb_rabbit_test",
            "some test output",
        )

    assert result is not None
    assert result.name == "first"

    Path(config_path).unlink()


def test_find_matching_metahook_invalid_regex_skipped() -> None:
    """Test find_matching_metahook skips metahooks with invalid regex."""
    yaml_content = """
metahooks:
  - name: invalid
    hook_command: bb_rabbit
    output_regex: "[invalid regex("
  - name: valid
    hook_command: bb_rabbit
    output_regex: "test"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("metahook_config._get_config_path", return_value=config_path):
        result = find_matching_metahook(
            "bb_rabbit_test",
            "some test output",
        )

    # Should skip the invalid regex and match the valid one
    assert result is not None
    assert result.name == "valid"

    Path(config_path).unlink()


def test_find_matching_metahook_multiline_output() -> None:
    """Test find_matching_metahook works with multiline output."""
    yaml_content = """
metahooks:
  - name: scuba
    hook_command: bb_rabbit
    output_regex: "Expected: Scuba"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    multiline_output = """
Line 1: Some output
Line 2: More output
Line 3: Expected: Scuba Result PASSED
Line 4: Final output
"""

    with patch("metahook_config._get_config_path", return_value=config_path):
        result = find_matching_metahook(
            "bb_rabbit_test",
            multiline_output,
        )

    assert result is not None
    assert result.name == "scuba"

    Path(config_path).unlink()


def test_find_matching_metahook_no_metahooks() -> None:
    """Test find_matching_metahook returns None when no metahooks configured."""
    yaml_content = """
snippets:
  foo: "bar"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("metahook_config._get_config_path", return_value=config_path):
        result = find_matching_metahook(
            "any_command",
            "any output",
        )

    assert result is None

    Path(config_path).unlink()
