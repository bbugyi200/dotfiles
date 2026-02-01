"""Tests for the xprompt.loader module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from xprompt.loader import (
    _load_xprompt_from_file,
    _load_xprompts_from_config,
    _parse_inputs_from_front_matter,
    _parse_shortform_input_value,
    _parse_shortform_output,
    _parse_yaml_front_matter,
    get_all_xprompts,
    parse_output_from_front_matter,
    parse_shortform_inputs,
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


# Tests for _load_xprompt_from_file


def test_load_xprompt_from_file_with_front_matter() -> None:
    """Test loading xprompt file with front matter."""
    content = """---
name: my_prompt
input:
  - name: arg1
    type: string
---
Hello {{ arg1 }}!"""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        temp_path = Path(f.name)

    try:
        xprompt = _load_xprompt_from_file(temp_path)

        assert xprompt is not None
        assert xprompt.name == "my_prompt"
        assert len(xprompt.inputs) == 1
        assert xprompt.inputs[0].name == "arg1"
        assert "Hello {{ arg1 }}" in xprompt.content
        assert xprompt.source_path == str(temp_path)
    finally:
        temp_path.unlink()


def test_load_xprompt_from_file_without_front_matter() -> None:
    """Test loading xprompt file without front matter."""
    content = "Just some content without front matter"

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        temp_path = Path(f.name)

    try:
        xprompt = _load_xprompt_from_file(temp_path)

        assert xprompt is not None
        # Name should be filename stem
        assert xprompt.name == temp_path.stem
        assert xprompt.inputs == []
        assert xprompt.content == content
    finally:
        temp_path.unlink()


def test_load_xprompt_from_file_name_from_front_matter() -> None:
    """Test that name from front matter overrides filename."""
    content = """---
name: custom_name
---
Content"""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        temp_path = Path(f.name)

    try:
        xprompt = _load_xprompt_from_file(temp_path)

        assert xprompt is not None
        assert xprompt.name == "custom_name"
    finally:
        temp_path.unlink()


def test_load_xprompt_from_file_nonexistent() -> None:
    """Test loading nonexistent file returns None."""
    xprompt = _load_xprompt_from_file(Path("/nonexistent/path.md"))
    assert xprompt is None


# Tests for _load_xprompts_from_config


def test_load_xprompts_from_config_basic() -> None:
    """Test loading xprompts from config file."""
    yaml_content = """
xprompts:
  foo: "Foo content"
  bar: "Bar content with {1}"
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("xprompt.loader._get_config_path", return_value=config_path):
        xprompts = _load_xprompts_from_config()

    assert len(xprompts) == 2
    assert xprompts["foo"].content == "Foo content"
    assert xprompts["bar"].content == "Bar content with {1}"
    assert xprompts["foo"].source_path == "config"

    Path(config_path).unlink()


def test_load_xprompts_from_config_missing_file() -> None:
    """Test that missing config file returns empty dict."""
    with patch("xprompt.loader._get_config_path", return_value="/nonexistent/path.yml"):
        xprompts = _load_xprompts_from_config()

    assert xprompts == {}


def test_load_xprompts_from_config_missing_key() -> None:
    """Test that config without xprompts/snippets returns empty dict."""
    yaml_content = """
mentor_profiles:
  - name: test
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        config_path = f.name

    with patch("xprompt.loader._get_config_path", return_value=config_path):
        xprompts = _load_xprompts_from_config()

    assert xprompts == {}

    Path(config_path).unlink()


# Tests for get_all_xprompts


def test_get_all_xprompts_merges_sources() -> None:
    """Test that xprompts are merged from all sources."""
    yaml_content = """
xprompts:
  from_config: "Config content"
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        config_path = f.name

    # Mock file discovery to return a test xprompt
    from xprompt.models import XPrompt

    file_xprompt = XPrompt(name="from_file", content="File content")

    with (
        patch("xprompt.loader._get_config_path", return_value=config_path),
        patch(
            "xprompt.loader._load_xprompts_from_files",
            return_value={"from_file": file_xprompt},
        ),
        patch("xprompt.loader._load_xprompts_from_internal", return_value={}),
    ):
        xprompts = get_all_xprompts()

    assert "from_config" in xprompts
    assert "from_file" in xprompts

    Path(config_path).unlink()


def test_get_all_xprompts_file_overrides_config() -> None:
    """Test that file-based xprompts override config-based ones."""
    yaml_content = """
xprompts:
  test: "From config"
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        config_path = f.name

    from xprompt.models import XPrompt

    file_xprompt = XPrompt(name="test", content="From file")

    with (
        patch("xprompt.loader._get_config_path", return_value=config_path),
        patch(
            "xprompt.loader._load_xprompts_from_files",
            return_value={"test": file_xprompt},
        ),
        patch("xprompt.loader._load_xprompts_from_internal", return_value={}),
    ):
        xprompts = get_all_xprompts()

    # File-based should win
    assert xprompts["test"].content == "From file"

    Path(config_path).unlink()


# Tests for shortform syntax parsing


def test_parse_shortform_input_value_simple_type() -> None:
    """Test parsing a simple type without default."""
    type_str, default = _parse_shortform_input_value("word")
    assert type_str == "word"
    assert default is None


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
    assert default is None


def testparse_shortform_inputs_basic() -> None:
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
    assert name_input.default is None


def testparse_shortform_inputs_with_defaults() -> None:
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


def test_parse_shortform_output_array_empty() -> None:
    """Test parsing empty array shortform."""
    output = _parse_shortform_output([])
    assert output.type == "json_schema"
    assert output.schema["type"] == "array"


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
