"""Tests for snippet_processor internal parsing and substitution functions."""

import pytest
from gemini_wrapper.snippet_processor import (
    _expand_single_snippet,
    _parse_args,
    _parse_named_arg,
    _SnippetArgumentError,
    _SnippetNotFoundError,
    _substitute_placeholders,
    is_jinja2_template,
)

# Tests for _parse_named_arg


def test_parse_named_arg_positional() -> None:
    """Test parsing a positional argument (no = sign)."""
    name, value = _parse_named_arg("hello")
    assert name is None
    assert value == "hello"


def test_parse_named_arg_named() -> None:
    """Test parsing a named argument."""
    name, value = _parse_named_arg("foo=bar")
    assert name == "foo"
    assert value == "bar"


def test_parse_named_arg_named_with_quotes() -> None:
    """Test parsing a named argument with quoted value."""
    name, value = _parse_named_arg('msg="hello world"')
    assert name == "msg"
    assert value == "hello world"


def test_parse_named_arg_equals_in_quotes() -> None:
    """Test that equals inside quotes doesn't split."""
    name, value = _parse_named_arg('expr="a=b"')
    assert name == "expr"
    assert value == "a=b"


# Tests for _parse_args


def test_parse_args_empty_string() -> None:
    """Test parsing empty argument string."""
    assert _parse_args("") == ([], {})
    assert _parse_args("   ") == ([], {})


def test_parse_args_single_arg() -> None:
    """Test parsing single argument."""
    positional, named = _parse_args("hello")
    assert positional == ["hello"]
    assert named == {}


def test_parse_args_multiple_args() -> None:
    """Test parsing multiple arguments."""
    positional, named = _parse_args("hello, world")
    assert positional == ["hello", "world"]
    assert named == {}

    positional, named = _parse_args("a, b, c")
    assert positional == ["a", "b", "c"]
    assert named == {}


def test_parse_args_strips_whitespace() -> None:
    """Test that whitespace is stripped from arguments."""
    positional, named = _parse_args("  hello  ,  world  ")
    assert positional == ["hello", "world"]
    assert named == {}


def test_parse_args_with_double_quotes() -> None:
    """Test parsing arguments with double quotes containing commas."""
    positional, named = _parse_args('hello, "world, there"')
    # Quotes are stripped - they are delimiters, not part of the value
    assert positional == ["hello", "world, there"]
    assert named == {}


def test_parse_args_with_single_quotes() -> None:
    """Test parsing arguments with single quotes containing commas."""
    positional, named = _parse_args("hello, 'world, there'")
    # Quotes are stripped - they are delimiters, not part of the value
    assert positional == ["hello", "world, there"]
    assert named == {}


def test_parse_args_named_simple() -> None:
    """Test parsing simple named argument."""
    positional, named = _parse_args("name=value")
    assert positional == []
    assert named == {"name": "value"}


def test_parse_args_named_with_quotes() -> None:
    """Test parsing named argument with quoted value."""
    positional, named = _parse_args('greeting="hello world"')
    assert positional == []
    assert named == {"greeting": "hello world"}


def test_parse_args_mixed_positional_and_named() -> None:
    """Test parsing mixed positional and named arguments."""
    positional, named = _parse_args("pos1, pos2, name=value")
    assert positional == ["pos1", "pos2"]
    assert named == {"name": "value"}


def test_parse_args_multiple_named() -> None:
    """Test parsing multiple named arguments."""
    positional, named = _parse_args("a=1, b=2, c=3")
    assert positional == []
    assert named == {"a": "1", "b": "2", "c": "3"}


def test_parse_args_named_with_equals_in_quotes() -> None:
    """Test that equals inside quotes doesn't split."""
    positional, named = _parse_args('expr="a=b"')
    assert positional == []
    assert named == {"expr": "a=b"}


# Tests for is_jinja2_template


def testis_jinja2_template_variable() -> None:
    """Test detection of Jinja2 variable syntax."""
    assert is_jinja2_template("Hello {{ name }}!") is True


def testis_jinja2_template_control() -> None:
    """Test detection of Jinja2 control syntax."""
    assert is_jinja2_template("{% if x %}yes{% endif %}") is True


def testis_jinja2_template_comment() -> None:
    """Test detection of Jinja2 comment syntax."""
    assert is_jinja2_template("{# comment #}") is True


def testis_jinja2_template_legacy() -> None:
    """Test that legacy syntax is not detected as Jinja2."""
    assert is_jinja2_template("Hello {1}!") is False
    assert is_jinja2_template("{1:default}") is False


def testis_jinja2_template_multiline() -> None:
    """Test detection in multiline content."""
    content = """Line 1
    {{ var }}
    Line 3"""
    assert is_jinja2_template(content) is True


# Tests for _substitute_placeholders (legacy mode)


def test_substitute_placeholders_no_placeholders() -> None:
    """Test substitution when there are no placeholders."""
    result = _substitute_placeholders("No placeholders here", [], {}, "test")
    assert result == "No placeholders here"


def test_substitute_placeholders_single_arg() -> None:
    """Test substitution with single placeholder."""
    result = _substitute_placeholders("Hello {1}!", ["world"], {}, "test")
    assert result == "Hello world!"


def test_substitute_placeholders_multiple_args() -> None:
    """Test substitution with multiple placeholders."""
    result = _substitute_placeholders("{1} says {2}", ["Alice", "hello"], {}, "test")
    assert result == "Alice says hello"


def test_substitute_placeholders_repeated_placeholder() -> None:
    """Test substitution when same placeholder appears multiple times."""
    result = _substitute_placeholders("{1} and {1} again", ["value"], {}, "test")
    assert result == "value and value again"


def test_substitute_placeholders_with_default() -> None:
    """Test substitution with default value when no arg provided."""
    result = _substitute_placeholders("Hello {1:default}!", [], {}, "test")
    assert result == "Hello default!"


def test_substitute_placeholders_arg_overrides_default() -> None:
    """Test that provided arg overrides default value."""
    result = _substitute_placeholders("Hello {1:default}!", ["world"], {}, "test")
    assert result == "Hello world!"


def test_substitute_placeholders_missing_required_arg() -> None:
    """Test that missing required arg raises error."""
    with pytest.raises(_SnippetArgumentError, match="requires argument"):
        _substitute_placeholders("Hello {1}!", [], {}, "test")


def test_substitute_placeholders_mixed_required_and_optional() -> None:
    """Test substitution with mix of required and optional args."""
    result = _substitute_placeholders("{1} and {2:optional}", ["required"], {}, "test")
    assert result == "required and optional"


# Tests for _substitute_placeholders (Jinja2 mode)


def test_substitute_placeholders_jinja2_simple_variable() -> None:
    """Test Jinja2 variable substitution with named arg."""
    result = _substitute_placeholders(
        "Hello {{ name }}!", [], {"name": "World"}, "test"
    )
    assert result == "Hello World!"


def test_substitute_placeholders_jinja2_positional_as_underscore() -> None:
    """Test that positional args are available as _1, _2, etc."""
    result = _substitute_placeholders(
        "{{ _1 }} says {{ _2 }}", ["Alice", "hello"], {}, "test"
    )
    assert result == "Alice says hello"


def test_substitute_placeholders_jinja2_filter() -> None:
    """Test Jinja2 filter usage."""
    result = _substitute_placeholders(
        "{{ name | upper }}", [], {"name": "hello"}, "test"
    )
    assert result == "HELLO"


def test_substitute_placeholders_jinja2_default_filter() -> None:
    """Test Jinja2 default filter for optional args."""
    result = _substitute_placeholders(
        "Hello {{ name | default('World') }}!", [], {}, "test"
    )
    assert result == "Hello World!"


def test_substitute_placeholders_jinja2_conditional() -> None:
    """Test Jinja2 conditional logic."""
    content = "Hello {{ name }}{% if formal %}, sir{% endif %}!"
    result = _substitute_placeholders(
        content, [], {"name": "Bob", "formal": "true"}, "test"
    )
    # "true" as string is truthy in Jinja2
    assert result == "Hello Bob, sir!"


def test_substitute_placeholders_jinja2_missing_var_error() -> None:
    """Test that missing required variable raises error."""
    with pytest.raises(_SnippetArgumentError, match="template error"):
        _substitute_placeholders("Hello {{ name }}!", [], {}, "test")


# Tests for _expand_single_snippet


def test_expand_single_snippet_not_found() -> None:
    """Test that missing snippet raises error."""
    with pytest.raises(_SnippetNotFoundError, match="not found"):
        _expand_single_snippet("nonexistent", [], {}, {"foo": "content"})


def test_expand_single_snippet_no_args() -> None:
    """Test expanding snippet without arguments."""
    snippets = {"foo": "The foo content"}
    result = _expand_single_snippet("foo", [], {}, snippets)
    assert result == "The foo content"


def test_expand_single_snippet_with_positional_args() -> None:
    """Test expanding snippet with positional arguments."""
    snippets = {"greet": "Hello {1}!"}
    result = _expand_single_snippet("greet", ["world"], {}, snippets)
    assert result == "Hello world!"


def test_expand_single_snippet_with_named_args_jinja2() -> None:
    """Test expanding Jinja2 snippet with named arguments."""
    snippets = {"greet": "Hello {{ name }}!"}
    result = _expand_single_snippet("greet", [], {"name": "World"}, snippets)
    assert result == "Hello World!"


def test_expand_single_snippet_mixed_args_jinja2() -> None:
    """Test expanding Jinja2 snippet with mixed positional and named args."""
    snippets = {"msg": "{{ _1 }} says {{ message }}"}
    result = _expand_single_snippet("msg", ["Alice"], {"message": "hello"}, snippets)
    assert result == "Alice says hello"
