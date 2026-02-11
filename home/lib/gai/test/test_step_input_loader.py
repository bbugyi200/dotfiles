"""Tests for step input loading and validation."""

import os
import tempfile

import pytest
import yaml  # type: ignore[import-untyped]
from xprompt._step_input_loader import (
    _looks_like_file_path,
    load_step_input_value,
)
from xprompt.models import OutputSpec
from xprompt.workflow_models import WorkflowValidationError


def test_load_step_input_inline_yaml() -> None:
    """Test loading step input from inline YAML string."""
    value = "{field1: value1, field2: 42}"
    result = load_step_input_value(value, None)
    assert result == {"field1": "value1", "field2": 42}


def test_load_step_input_inline_json() -> None:
    """Test loading step input from inline JSON string."""
    value = '{"field1": "value1", "field2": 42}'
    result = load_step_input_value(value, None)
    assert result == {"field1": "value1", "field2": 42}


def test_load_step_input_simple_string() -> None:
    """Test loading step input that's a simple string (no parsing needed)."""
    value = "simple_value"
    result = load_step_input_value(value, None)
    assert result == "simple_value"


def test_load_step_input_from_file() -> None:
    """Test loading step input from @file reference."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump({"key": "from_file", "num": 123}, f)
        file_path = f.name

    try:
        result = load_step_input_value(f"@{file_path}", None)
        assert result == {"key": "from_file", "num": 123}
    finally:
        os.unlink(file_path)


def test_load_step_input_from_file_with_tilde() -> None:
    """Test that ~ is expanded in @file references."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, dir=os.path.expanduser("~")
    ) as f:
        yaml.dump({"home_file": True}, f)
        file_path = f.name
        home_relative = "~/" + os.path.basename(file_path)

    try:
        result = load_step_input_value(f"@{home_relative}", None)
        assert result == {"home_file": True}
    finally:
        os.unlink(file_path)


def test_load_step_input_file_not_found() -> None:
    """Test that missing @file raises WorkflowValidationError."""
    with pytest.raises(WorkflowValidationError, match="does not exist"):
        load_step_input_value("@/nonexistent/file.yml", None)


def test_load_step_input_invalid_yaml() -> None:
    """Test that invalid YAML raises WorkflowValidationError."""
    with pytest.raises(WorkflowValidationError, match="Failed to parse"):
        load_step_input_value("{ invalid: yaml: syntax }", None)


def test_load_step_input_with_validation_success() -> None:
    """Test loading step input with schema validation succeeding."""
    output_spec = OutputSpec(
        type="json_schema",
        schema={
            "type": "object",
            "properties": {
                "name": {"type": "line"},
                "count": {"type": "int"},
            },
            "required": ["name", "count"],
        },
    )
    value = '{"name": "test", "count": 5}'
    result = load_step_input_value(value, output_spec)
    assert result == {"name": "test", "count": 5}


def test_load_step_input_with_validation_failure() -> None:
    """Test loading step input with schema validation failing."""
    output_spec = OutputSpec(
        type="json_schema",
        schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        },
    )
    value = '{"wrong_field": "value"}'
    with pytest.raises(WorkflowValidationError, match="validation failed"):
        load_step_input_value(value, output_spec)


def test_load_step_input_from_json_file() -> None:
    """Test loading step input from @file with JSON content."""
    import json

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"json_key": "json_value"}, f)
        file_path = f.name

    try:
        # yaml.safe_load can parse JSON too
        result = load_step_input_value(f"@{file_path}", None)
        assert result == {"json_key": "json_value"}
    finally:
        os.unlink(file_path)


# --- Auto-detected file path tests (no @ prefix) ---


def test_looks_like_file_path_positive() -> None:
    """Test _looks_like_file_path returns True for recognized extensions."""
    assert _looks_like_file_path("foo.yml") is True
    assert _looks_like_file_path("foo.yaml") is True
    assert _looks_like_file_path("foo.json") is True
    assert _looks_like_file_path("~/path/to/file.yml") is True
    assert _looks_like_file_path("/absolute/path.json") is True


def test_looks_like_file_path_negative() -> None:
    """Test _looks_like_file_path returns False for non-file values."""
    assert _looks_like_file_path("simple_value") is False
    assert _looks_like_file_path("{key: value}") is False
    assert _looks_like_file_path("foo.txt") is False
    assert _looks_like_file_path("foo.py") is False


def test_load_step_input_auto_detect_yml() -> None:
    """Test auto-detecting .yml file path without @ prefix."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump({"auto": "detected"}, f)
        file_path = f.name

    try:
        result = load_step_input_value(file_path, None)
        assert result == {"auto": "detected"}
    finally:
        os.unlink(file_path)


def test_load_step_input_auto_detect_yaml() -> None:
    """Test auto-detecting .yaml file path without @ prefix."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({"format": "yaml"}, f)
        file_path = f.name

    try:
        result = load_step_input_value(file_path, None)
        assert result == {"format": "yaml"}
    finally:
        os.unlink(file_path)


def test_load_step_input_auto_detect_json() -> None:
    """Test auto-detecting .json file path without @ prefix."""
    import json

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"format": "json"}, f)
        file_path = f.name

    try:
        result = load_step_input_value(file_path, None)
        assert result == {"format": "json"}
    finally:
        os.unlink(file_path)


def test_load_step_input_auto_detect_tilde_expansion() -> None:
    """Test that ~ is expanded in auto-detected file paths."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, dir=os.path.expanduser("~")
    ) as f:
        yaml.dump({"tilde": "expanded"}, f)
        file_path = f.name
        home_relative = "~/" + os.path.basename(file_path)

    try:
        result = load_step_input_value(home_relative, None)
        assert result == {"tilde": "expanded"}
    finally:
        os.unlink(file_path)


def test_load_step_input_auto_detect_nonexistent_file() -> None:
    """Test that a nonexistent auto-detected file raises a clear error."""
    with pytest.raises(WorkflowValidationError, match="does not exist"):
        load_step_input_value("/nonexistent/path/file.yml", None)


def test_load_step_input_auto_detect_with_validation() -> None:
    """Test auto-detected file with schema validation."""
    output_spec = OutputSpec(
        type="json_schema",
        schema={
            "type": "object",
            "properties": {
                "name": {"type": "line"},
                "count": {"type": "int"},
            },
            "required": ["name", "count"],
        },
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump({"name": "test", "count": 5}, f)
        file_path = f.name

    try:
        result = load_step_input_value(file_path, output_spec)
        assert result == {"name": "test", "count": 5}
    finally:
        os.unlink(file_path)
