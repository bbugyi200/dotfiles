"""Tests for xprompt.loader shortform syntax parsing."""

from xprompt.loader import (
    _normalize_schema_properties,
    _parse_inputs_from_front_matter,
    _parse_shortform_input_value,
    _parse_shortform_output,
    parse_output_from_front_matter,
    parse_shortform_inputs,
)
from xprompt.models import UNSET, InputType

# Tests for _parse_shortform_input_value


def test_parse_shortform_input_value_simple_type() -> None:
    """Test parsing a simple type without default."""
    type_str, default = _parse_shortform_input_value("word")
    assert type_str == "word"
    assert default is UNSET


def test_parse_shortform_input_value_dict_with_empty_string_default() -> None:
    """Test parsing dict with empty string default."""
    type_str, default = _parse_shortform_input_value({"type": "line", "default": ""})
    assert type_str == "line"
    assert default == ""


def test_parse_shortform_input_value_dict_with_string_default() -> None:
    """Test parsing dict with string default."""
    type_str, default = _parse_shortform_input_value(
        {"type": "text", "default": "hello world"}
    )
    assert type_str == "text"
    assert default == "hello world"


def test_parse_shortform_input_value_dict_with_int_default() -> None:
    """Test parsing dict with integer default."""
    type_str, default = _parse_shortform_input_value({"type": "int", "default": 42})
    assert type_str == "int"
    assert default == 42
    assert isinstance(default, int)


def test_parse_shortform_input_value_dict_with_negative_int() -> None:
    """Test parsing dict with negative integer default."""
    type_str, default = _parse_shortform_input_value({"type": "int", "default": -5})
    assert type_str == "int"
    assert default == -5


def test_parse_shortform_input_value_dict_with_float_default() -> None:
    """Test parsing dict with float default."""
    type_str, default = _parse_shortform_input_value({"type": "float", "default": 3.14})
    assert type_str == "float"
    assert default == 3.14
    assert isinstance(default, float)


def test_parse_shortform_input_value_dict_with_bool_true() -> None:
    """Test parsing dict with boolean true default."""
    type_str, default = _parse_shortform_input_value({"type": "bool", "default": True})
    assert type_str == "bool"
    assert default is True


def test_parse_shortform_input_value_dict_with_bool_false() -> None:
    """Test parsing dict with boolean false default."""
    type_str, default = _parse_shortform_input_value({"type": "bool", "default": False})
    assert type_str == "bool"
    assert default is False


def test_parse_shortform_input_value_dict_without_default() -> None:
    """Test parsing dict without default key."""
    type_str, default = _parse_shortform_input_value({"type": "word"})
    assert type_str == "word"
    assert default is UNSET


def test_parse_shortform_input_value_null_default() -> None:
    """Test parsing dict with explicit null default."""
    type_str, default = _parse_shortform_input_value({"type": "line", "default": None})
    assert type_str == "line"
    assert default is None


# Tests for parse_shortform_inputs


def test_parse_shortform_inputs_basic() -> None:
    """Test parsing a basic shortform input dict."""
    inputs = parse_shortform_inputs(
        {
            "name": "word",
            "description": "text",
        }
    )
    assert len(inputs) == 2

    names = [i.name for i in inputs]
    assert "name" in names
    assert "description" in names

    name_input = next(i for i in inputs if i.name == "name")
    assert name_input.type == InputType.WORD
    assert name_input.default is UNSET


def test_parse_shortform_inputs_with_defaults() -> None:
    """Test parsing shortform with default values."""
    inputs = parse_shortform_inputs(
        {
            "path": "path",
            "flag": {"type": "line", "default": ""},
            "count": {"type": "int", "default": 0},
        }
    )
    assert len(inputs) == 3

    flag_input = next(i for i in inputs if i.name == "flag")
    assert flag_input.type == InputType.LINE
    assert flag_input.default == ""

    count_input = next(i for i in inputs if i.name == "count")
    assert count_input.type == InputType.INT
    assert count_input.default == 0


# Tests for _parse_shortform_output


def test_parse_shortform_output_object() -> None:
    """Test parsing object shortform output."""
    output = _parse_shortform_output(
        {
            "name": "word",
            "description": "text",
        }
    )
    assert output.type == "json_schema"
    assert "properties" in output.schema
    assert output.schema["properties"]["name"]["type"] == "word"
    assert output.schema["properties"]["description"]["type"] == "text"


def test_parse_shortform_output_array_with_required() -> None:
    """Test parsing array shortform output with required fields."""
    output = _parse_shortform_output(
        [
            {
                "name": "word",
                "description": "text",
                "parent": {"type": "word", "default": ""},
            }
        ]
    )
    assert output.type == "json_schema"
    assert output.schema["type"] == "array"
    items = output.schema["items"]
    assert items["type"] == "object"
    assert "name" in items["required"]
    assert "description" in items["required"]
    # parent has a default, so not required
    assert "parent" not in items["required"]


def test_parse_shortform_output_array_nullable_field() -> None:
    """Test that default: null produces a nullable type in array format."""
    output = _parse_shortform_output(
        [
            {
                "name": "word",
                "parent": {"type": "word", "default": None},
            }
        ]
    )
    assert output.type == "json_schema"
    items = output.schema["items"]
    assert items["properties"]["parent"]["type"] == ["word", "null"]
    # name has no default, so it's required; parent has default null, not required
    assert "name" in items["required"]
    assert "parent" not in items["required"]


def test_parse_shortform_output_object_nullable_field() -> None:
    """Test that default: null produces a nullable type in object format."""
    output = _parse_shortform_output(
        {
            "name": "word",
            "parent": {"type": "word", "default": None},
        }
    )
    assert output.type == "json_schema"
    assert output.schema["properties"]["parent"]["type"] == ["word", "null"]
    assert output.schema["properties"]["name"]["type"] == "word"


def test_parse_shortform_output_array_empty() -> None:
    """Test parsing empty array shortform."""
    output = _parse_shortform_output([])
    assert output.type == "json_schema"
    assert output.schema["type"] == "array"


def test_parse_shortform_output_array_non_dict_item() -> None:
    """Test parsing array shortform with non-dict item."""
    output = _parse_shortform_output(["not a dict"])  # type: ignore[list-item]
    assert output.type == "json_schema"
    assert output.schema["type"] == "array"
    assert output.schema["items"] == {}


# Tests for _parse_inputs_from_front_matter with shortform


def test_parse_inputs_from_front_matter_shortform() -> None:
    """Test that _parse_inputs_from_front_matter handles shortform dict."""
    inputs = _parse_inputs_from_front_matter(
        {
            "foo": "word",
            "bar": {"type": "line", "default": ""},
        }
    )
    assert len(inputs) == 2

    foo_input = next(i for i in inputs if i.name == "foo")
    assert foo_input.type == InputType.WORD

    bar_input = next(i for i in inputs if i.name == "bar")
    assert bar_input.type == InputType.LINE
    assert bar_input.default == ""


# Tests for parse_output_from_front_matter


def test_parse_output_from_front_matter_longform() -> None:
    """Test parsing longform output specification."""
    output = parse_output_from_front_matter(
        {
            "type": "json_schema",
            "schema": {
                "properties": {
                    "name": {"type": "word"},
                },
            },
        }
    )
    assert output is not None
    assert output.type == "json_schema"
    assert output.schema["properties"]["name"]["type"] == "word"


def test_parse_output_from_front_matter_shortform_object() -> None:
    """Test parsing shortform object output."""
    output = parse_output_from_front_matter(
        {
            "name": "word",
            "description": "text",
        }
    )
    assert output is not None
    assert output.type == "json_schema"
    assert output.schema["properties"]["name"]["type"] == "word"


def test_parse_output_from_front_matter_shortform_array() -> None:
    """Test parsing shortform array output."""
    output = parse_output_from_front_matter(
        [
            {
                "name": "word",
                "description": "text",
            }
        ]
    )
    assert output is not None
    assert output.type == "json_schema"
    assert output.schema["type"] == "array"
    assert output.schema["items"]["properties"]["name"]["type"] == "word"


def test_parse_output_from_front_matter_empty() -> None:
    """Test parsing empty output returns None."""
    assert parse_output_from_front_matter(None) is None
    assert parse_output_from_front_matter({}) is None


def test_parse_output_distinguishes_longform_from_shortform() -> None:
    """Test that parser correctly distinguishes longform from shortform.

    Longform has 'type' as output format type (e.g., 'json_schema'),
    while shortform has 'type' as field types (e.g., 'word', 'text').
    """
    # This is longform because it has 'type' + 'schema' keys
    longform = parse_output_from_front_matter(
        {
            "type": "json_schema",
            "schema": {"properties": {}},
        }
    )
    assert longform is not None
    assert longform.type == "json_schema"

    # This is shortform because 'type' is a field with no 'schema' key
    shortform = parse_output_from_front_matter(
        {
            "type": "word",  # This is a field named 'type'
            "name": "line",
        }
    )
    assert shortform is not None
    assert "properties" in shortform.schema


# Tests for _normalize_schema_properties


def test_normalize_schema_properties_non_dict() -> None:
    """Test that non-dict input is returned as-is."""
    result = _normalize_schema_properties("not a dict")  # type: ignore[arg-type]
    assert result == "not a dict"


def test_normalize_schema_properties_nested_properties() -> None:
    """Test normalizing nested properties."""
    schema = {
        "type": "object",
        "properties": {
            "outer": {
                "type": "object",
                "properties": {
                    "inner": {"type": "string"},
                },
            },
        },
    }
    result = _normalize_schema_properties(schema)
    assert result["properties"]["outer"]["properties"]["inner"]["type"] == "string"


def test_normalize_schema_properties_with_items() -> None:
    """Test normalizing array items."""
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
        },
    }
    result = _normalize_schema_properties(schema)
    assert result["items"]["properties"]["name"]["type"] == "string"
