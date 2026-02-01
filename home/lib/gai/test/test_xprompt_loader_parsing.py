"""Tests for xprompt.loader parsing functions."""

from xprompt.loader import (
    _parse_inputs_from_front_matter,
    _parse_yaml_front_matter,
)
from xprompt.models import InputType

# Tests for _parse_yaml_front_matter


def test_parse_yaml_front_matter_basic() -> None:
    """Test parsing basic YAML front matter."""
    content = """---
name: test
input:
  - name: foo
---
Body content here"""
    front_matter, body = _parse_yaml_front_matter(content)

    assert front_matter is not None
    assert front_matter["name"] == "test"
    assert "input" in front_matter
    assert body == "Body content here"


def test_parse_yaml_front_matter_no_front_matter() -> None:
    """Test content without front matter."""
    content = "Just some content without front matter"
    front_matter, body = _parse_yaml_front_matter(content)

    assert front_matter is None
    assert body == content


def test_parse_yaml_front_matter_opening_without_closing() -> None:
    """Test content with opening --- but no closing ---."""
    content = """---
name: test
No closing marker"""
    front_matter, body = _parse_yaml_front_matter(content)

    assert front_matter is None
    assert body == content


def test_parse_yaml_front_matter_empty_front_matter() -> None:
    """Test empty front matter section."""
    content = """---
---
Body here"""
    front_matter, body = _parse_yaml_front_matter(content)

    assert front_matter == {}
    assert body == "Body here"


def test_parse_yaml_front_matter_multiline_body() -> None:
    """Test with multiline body content."""
    content = """---
name: test
---
Line 1
Line 2
Line 3"""
    front_matter, body = _parse_yaml_front_matter(content)

    assert front_matter is not None
    assert front_matter["name"] == "test"
    assert "Line 1" in body
    assert "Line 3" in body


def test_parse_yaml_front_matter_strips_leading_newline() -> None:
    """Test that leading newline in body is stripped."""
    content = """---
name: test
---

Body with newline before"""
    front_matter, body = _parse_yaml_front_matter(content)

    # The blank line after --- becomes a single \n when joined, then stripped
    assert body == "Body with newline before"


# Tests for _parse_inputs_from_front_matter


def test_parse_inputs_none_input() -> None:
    """Test with None input."""
    inputs = _parse_inputs_from_front_matter(None)
    assert inputs == []


def test_parse_inputs_empty_list() -> None:
    """Test with empty list."""
    inputs = _parse_inputs_from_front_matter([])
    assert inputs == []


def test_parse_inputs_basic() -> None:
    """Test parsing basic input definitions."""
    input_list = [
        {"name": "foo"},
        {"name": "bar", "type": "int"},
    ]
    inputs = _parse_inputs_from_front_matter(input_list)

    assert len(inputs) == 2
    assert inputs[0].name == "foo"
    assert inputs[0].type == InputType.LINE  # Default type
    assert inputs[1].name == "bar"
    assert inputs[1].type == InputType.INT


def test_parse_inputs_with_defaults() -> None:
    """Test parsing inputs with default values."""
    input_list = [
        {"name": "count", "type": "int", "default": 10},
        {"name": "enabled", "type": "bool", "default": True},
    ]
    inputs = _parse_inputs_from_front_matter(input_list)

    assert inputs[0].default == 10
    assert inputs[1].default is True


def test_parse_inputs_all_types() -> None:
    """Test parsing all supported types."""
    input_list = [
        {"name": "w", "type": "word"},
        {"name": "l", "type": "line"},
        {"name": "t", "type": "text"},
        {"name": "p", "type": "path"},
        {"name": "i", "type": "int"},
        {"name": "b", "type": "bool"},
        {"name": "f", "type": "float"},
    ]
    inputs = _parse_inputs_from_front_matter(input_list)

    assert inputs[0].type == InputType.WORD
    assert inputs[1].type == InputType.LINE
    assert inputs[2].type == InputType.TEXT
    assert inputs[3].type == InputType.PATH
    assert inputs[4].type == InputType.INT
    assert inputs[5].type == InputType.BOOL
    assert inputs[6].type == InputType.FLOAT


def test_parse_inputs_type_aliases() -> None:
    """Test that type aliases are recognized."""
    input_list = [
        {"name": "i", "type": "integer"},
        {"name": "b", "type": "boolean"},
    ]
    inputs = _parse_inputs_from_front_matter(input_list)

    assert inputs[0].type == InputType.INT
    assert inputs[1].type == InputType.BOOL


def test_parse_inputs_skips_invalid_items() -> None:
    """Test that items without name are skipped."""
    input_list = [
        {"name": "valid"},
        {"type": "int"},  # Missing name
        "not a dict",  # Wrong type (intentionally testing edge case)
        {"name": "also_valid"},
    ]
    inputs = _parse_inputs_from_front_matter(input_list)  # type: ignore[arg-type]

    assert len(inputs) == 2
    assert inputs[0].name == "valid"
    assert inputs[1].name == "also_valid"
