"""Tests for the xprompt.loader module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from xprompt.loader import (
    _load_xprompt_from_file,
    _load_xprompts_from_config,
    _parse_inputs_from_front_matter,
    _parse_yaml_front_matter,
    get_all_xprompts,
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
