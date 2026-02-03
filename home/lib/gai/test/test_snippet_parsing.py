"""Tests for xprompt processor internal parsing and substitution functions."""

import pytest
from xprompt._exceptions import XPromptArgumentError
from xprompt._jinja import is_jinja2_template, substitute_placeholders
from xprompt._parsing import (
    _parse_named_arg,
    _process_text_block,
    find_matching_paren_for_args,
    parse_args,
    parse_workflow_reference,
)
from xprompt.models import XPrompt
from xprompt.processor import _expand_single_xprompt

# Tests for parse_named_arg


def testparse_named_arg_positional() -> None:
    """Test parsing a positional argument (no = sign)."""
    name, value = _parse_named_arg("hello")
    assert name is None
    assert value == "hello"


def testparse_named_arg_named() -> None:
    """Test parsing a named argument."""
    name, value = _parse_named_arg("foo=bar")
    assert name == "foo"
    assert value == "bar"


def testparse_named_arg_named_with_quotes() -> None:
    """Test parsing a named argument with quoted value."""
    name, value = _parse_named_arg('msg="hello world"')
    assert name == "msg"
    assert value == "hello world"


def testparse_named_arg_equals_in_quotes() -> None:
    """Test that equals inside quotes doesn't split."""
    name, value = _parse_named_arg('expr="a=b"')
    assert name == "expr"
    assert value == "a=b"


# Tests for parse_args


def testparse_args_empty_string() -> None:
    """Test parsing empty argument string."""
    assert parse_args("") == ([], {})
    assert parse_args("   ") == ([], {})


def testparse_args_single_arg() -> None:
    """Test parsing single argument."""
    positional, named = parse_args("hello")
    assert positional == ["hello"]
    assert named == {}


def testparse_args_multiple_args() -> None:
    """Test parsing multiple arguments."""
    positional, named = parse_args("hello, world")
    assert positional == ["hello", "world"]
    assert named == {}

    positional, named = parse_args("a, b, c")
    assert positional == ["a", "b", "c"]
    assert named == {}


def testparse_args_strips_whitespace() -> None:
    """Test that whitespace is stripped from arguments."""
    positional, named = parse_args("  hello  ,  world  ")
    assert positional == ["hello", "world"]
    assert named == {}


def testparse_args_with_double_quotes() -> None:
    """Test parsing arguments with double quotes containing commas."""
    positional, named = parse_args('hello, "world, there"')
    # Quotes are stripped - they are delimiters, not part of the value
    assert positional == ["hello", "world, there"]
    assert named == {}


def testparse_args_with_single_quotes() -> None:
    """Test parsing arguments with single quotes containing commas."""
    positional, named = parse_args("hello, 'world, there'")
    # Quotes are stripped - they are delimiters, not part of the value
    assert positional == ["hello", "world, there"]
    assert named == {}


def testparse_args_named_simple() -> None:
    """Test parsing simple named argument."""
    positional, named = parse_args("name=value")
    assert positional == []
    assert named == {"name": "value"}


def testparse_args_named_with_quotes() -> None:
    """Test parsing named argument with quoted value."""
    positional, named = parse_args('greeting="hello world"')
    assert positional == []
    assert named == {"greeting": "hello world"}


def testparse_args_mixed_positional_and_named() -> None:
    """Test parsing mixed positional and named arguments."""
    positional, named = parse_args("pos1, pos2, name=value")
    assert positional == ["pos1", "pos2"]
    assert named == {"name": "value"}


def testparse_args_multiple_named() -> None:
    """Test parsing multiple named arguments."""
    positional, named = parse_args("a=1, b=2, c=3")
    assert positional == []
    assert named == {"a": "1", "b": "2", "c": "3"}


def testparse_args_named_with_equals_in_quotes() -> None:
    """Test that equals inside quotes doesn't split."""
    positional, named = parse_args('expr="a=b"')
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


# Tests for substitute_placeholders (legacy mode)


def testsubstitute_placeholders_no_placeholders() -> None:
    """Test substitution when there are no placeholders."""
    result = substitute_placeholders("No placeholders here", [], {}, "test")
    assert result == "No placeholders here"


def testsubstitute_placeholders_single_arg() -> None:
    """Test substitution with single placeholder."""
    result = substitute_placeholders("Hello {1}!", ["world"], {}, "test")
    assert result == "Hello world!"


def testsubstitute_placeholders_multiple_args() -> None:
    """Test substitution with multiple placeholders."""
    result = substitute_placeholders("{1} says {2}", ["Alice", "hello"], {}, "test")
    assert result == "Alice says hello"


def testsubstitute_placeholders_repeated_placeholder() -> None:
    """Test substitution when same placeholder appears multiple times."""
    result = substitute_placeholders("{1} and {1} again", ["value"], {}, "test")
    assert result == "value and value again"


def testsubstitute_placeholders_with_default() -> None:
    """Test substitution with default value when no arg provided."""
    result = substitute_placeholders("Hello {1:default}!", [], {}, "test")
    assert result == "Hello default!"


def testsubstitute_placeholders_arg_overrides_default() -> None:
    """Test that provided arg overrides default value."""
    result = substitute_placeholders("Hello {1:default}!", ["world"], {}, "test")
    assert result == "Hello world!"


def testsubstitute_placeholders_missing_required_arg() -> None:
    """Test that missing required arg raises error."""
    with pytest.raises(XPromptArgumentError, match="requires argument"):
        substitute_placeholders("Hello {1}!", [], {}, "test")


def testsubstitute_placeholders_mixed_required_and_optional() -> None:
    """Test substitution with mix of required and optional args."""
    result = substitute_placeholders("{1} and {2:optional}", ["required"], {}, "test")
    assert result == "required and optional"


# Tests for substitute_placeholders (Jinja2 mode)


def testsubstitute_placeholders_jinja2_simple_variable() -> None:
    """Test Jinja2 variable substitution with named arg."""
    result = substitute_placeholders("Hello {{ name }}!", [], {"name": "World"}, "test")
    assert result == "Hello World!"


def testsubstitute_placeholders_jinja2_positional_as_underscore() -> None:
    """Test that positional args are available as _1, _2, etc."""
    result = substitute_placeholders(
        "{{ _1 }} says {{ _2 }}", ["Alice", "hello"], {}, "test"
    )
    assert result == "Alice says hello"


def testsubstitute_placeholders_jinja2_filter() -> None:
    """Test Jinja2 filter usage."""
    result = substitute_placeholders(
        "{{ name | upper }}", [], {"name": "hello"}, "test"
    )
    assert result == "HELLO"


def testsubstitute_placeholders_jinja2_default_filter() -> None:
    """Test Jinja2 default filter for optional args."""
    result = substitute_placeholders(
        "Hello {{ name | default('World') }}!", [], {}, "test"
    )
    assert result == "Hello World!"


def testsubstitute_placeholders_jinja2_conditional() -> None:
    """Test Jinja2 conditional logic."""
    content = "Hello {{ name }}{% if formal %}, sir{% endif %}!"
    result = substitute_placeholders(
        content, [], {"name": "Bob", "formal": "true"}, "test"
    )
    # "true" as string is truthy in Jinja2
    assert result == "Hello Bob, sir!"


def testsubstitute_placeholders_jinja2_missing_var_error() -> None:
    """Test that missing required variable raises error."""
    with pytest.raises(XPromptArgumentError, match="template error"):
        substitute_placeholders("Hello {{ name }}!", [], {}, "test")


# Tests for _expand_single_xprompt


def test_expand_single_xprompt_no_args() -> None:
    """Test expanding xprompt without arguments."""
    xprompt = XPrompt(name="foo", content="The foo content")
    result = _expand_single_xprompt(xprompt, [], {})
    assert result == "The foo content"


def test_expand_single_xprompt_with_positional_args() -> None:
    """Test expanding xprompt with positional arguments."""
    xprompt = XPrompt(name="greet", content="Hello {1}!")
    result = _expand_single_xprompt(xprompt, ["world"], {})
    assert result == "Hello world!"


def test_expand_single_xprompt_with_named_args_jinja2() -> None:
    """Test expanding Jinja2 xprompt with named arguments."""
    xprompt = XPrompt(name="greet", content="Hello {{ name }}!")
    result = _expand_single_xprompt(xprompt, [], {"name": "World"})
    assert result == "Hello World!"


def test_expand_single_xprompt_mixed_args_jinja2() -> None:
    """Test expanding Jinja2 xprompt with mixed positional and named args."""
    xprompt = XPrompt(name="msg", content="{{ _1 }} says {{ message }}")
    result = _expand_single_xprompt(xprompt, ["Alice"], {"message": "hello"})
    assert result == "Alice says hello"


# Tests for process_text_block


def testprocess_text_block_not_text_block() -> None:
    """Test that non-text-block values are returned unchanged."""
    assert _process_text_block("hello") == "hello"
    assert _process_text_block('"quoted"') == '"quoted"'
    assert _process_text_block("[[partial") == "[[partial"


def testprocess_text_block_simple() -> None:
    """Test processing a simple single-line text block."""
    assert _process_text_block("[[hello world]]") == "hello world"


def testprocess_text_block_empty() -> None:
    """Test processing an empty text block."""
    assert _process_text_block("[[]]") == ""


def testprocess_text_block_multiline_with_indentation() -> None:
    """Test processing a multiline text block with proper indentation."""
    text_block = """\
[[
  Line one.

  Line two.
]]"""
    result = _process_text_block(text_block)
    assert result == "Line one.\n\nLine two."


def testprocess_text_block_first_line_content() -> None:
    """Test that content on first line after [[ is stripped of leading whitespace."""
    text_block = "[[  content here]]"
    result = _process_text_block(text_block)
    assert result == "content here"


def testprocess_text_block_missing_indentation_error() -> None:
    """Test that missing 2-space indentation raises an error."""
    text_block = """\
[[
  Line one.
Line two without indent.
]]"""
    with pytest.raises(XPromptArgumentError, match="must start with 2 spaces"):
        _process_text_block(text_block)


def testprocess_text_block_preserves_extra_indentation() -> None:
    """Test that indentation beyond 2 spaces is preserved."""
    text_block = """\
[[
  First level.
    Second level.
      Third level.
]]"""
    result = _process_text_block(text_block)
    assert result == "First level.\n  Second level.\n    Third level."


# Tests for find_matching_paren_for_args


def test_find_matching_paren_simple() -> None:
    """Test finding matching paren in simple case."""
    assert find_matching_paren_for_args("(abc)", 0) == 4


def test_find_matching_paren_nested() -> None:
    """Test finding matching paren with nested parens."""
    assert find_matching_paren_for_args("(a(b)c)", 0) == 6


def test_find_matching_paren_with_quotes() -> None:
    """Test that parens inside quotes are ignored."""
    assert find_matching_paren_for_args('("a)b")', 0) == 6


def test_find_matching_paren_with_text_block() -> None:
    """Test that parens inside text blocks are ignored."""
    assert find_matching_paren_for_args("([[a)b]])", 0) == 8


def test_find_matching_paren_complex() -> None:
    """Test finding matching paren with mixed quotes and text blocks."""
    text = '(arg1, "val)", [[block)]], name=val)'
    assert find_matching_paren_for_args(text, 0) == len(text) - 1


def test_find_matching_paren_unclosed() -> None:
    """Test that unclosed paren returns None."""
    assert find_matching_paren_for_args("(abc", 0) is None


def test_find_matching_paren_not_at_paren() -> None:
    """Test that non-paren start returns None."""
    assert find_matching_paren_for_args("abc)", 0) is None


# Tests for parse_args with text blocks


def testparse_args_text_block_positional() -> None:
    """Test parsing a text block as a positional argument."""
    positional, named = parse_args("[[hello world]]")
    assert positional == ["hello world"]
    assert named == {}


def testparse_args_text_block_multiline() -> None:
    """Test parsing a multiline text block."""
    args_str = """\
[[
  This is line one.

  This is line two.
]]"""
    positional, named = parse_args(args_str)
    assert positional == ["This is line one.\n\nThis is line two."]
    assert named == {}


def testparse_args_text_block_named() -> None:
    """Test parsing a text block as a named argument."""
    positional, named = parse_args("msg=[[hello world]]")
    assert positional == []
    assert named == {"msg": "hello world"}


def testparse_args_text_block_with_commas() -> None:
    """Test that commas inside text blocks don't split."""
    positional, named = parse_args("[[a, b, c]]")
    assert positional == ["a, b, c"]
    assert named == {}


def testparse_args_text_block_with_parens() -> None:
    """Test that parentheses inside text blocks are preserved."""
    positional, named = parse_args("[[func(x)]]")
    assert positional == ["func(x)"]
    assert named == {}


def testparse_args_mixed_text_blocks_and_quotes() -> None:
    """Test parsing mixed text blocks and quoted strings."""
    positional, named = parse_args('"quoted", [[text block]], name=value')
    assert positional == ["quoted", "text block"]
    assert named == {"name": "value"}


def testparse_args_multiple_text_blocks() -> None:
    """Test parsing multiple text blocks."""
    args_str = "[[first]], [[second]]"
    positional, named = parse_args(args_str)
    assert positional == ["first", "second"]
    assert named == {}


def testparse_args_text_block_named_multiline() -> None:
    """Test parsing a multiline text block as a named argument."""
    args_str = """\
msg=[[
  Line one.
  Line two.
]]"""
    positional, named = parse_args(args_str)
    assert positional == []
    assert named == {"msg": "Line one.\nLine two."}


# Tests for parse_named_arg with text blocks


def testparse_named_arg_text_block_value() -> None:
    """Test parsing named arg with text block value."""
    name, value = _parse_named_arg("key=[[value with = sign]]")
    assert name == "key"
    assert value == "value with = sign"


def testparse_named_arg_text_block_positional() -> None:
    """Test parsing text block as positional (no = outside block)."""
    name, value = _parse_named_arg("[[content=here]]")
    assert name is None
    assert value == "[[content=here]]"


# Tests for parse_workflow_reference


def test_parse_workflow_reference_plain_name() -> None:
    """Test parsing a plain workflow name without arguments."""
    name, pos, named = parse_workflow_reference("split")
    assert name == "split"
    assert pos == []
    assert named == {}


def test_parse_workflow_reference_parenthesis_positional() -> None:
    """Test parsing workflow with positional args in parentheses."""
    name, pos, named = parse_workflow_reference("split(arg1, arg2)")
    assert name == "split"
    assert pos == ["arg1", "arg2"]
    assert named == {}


def test_parse_workflow_reference_parenthesis_named() -> None:
    """Test parsing workflow with named args in parentheses."""
    name, pos, named = parse_workflow_reference("foo(bar=2)")
    assert name == "foo"
    assert pos == []
    assert named == {"bar": "2"}


def test_parse_workflow_reference_parenthesis_mixed() -> None:
    """Test parsing workflow with mixed positional and named args."""
    name, pos, named = parse_workflow_reference("workflow(pos1, key=value, pos2)")
    assert name == "workflow"
    assert pos == ["pos1", "pos2"]
    assert named == {"key": "value"}


def test_parse_workflow_reference_simple_colon() -> None:
    """Test parsing workflow with simple colon syntax (no space)."""
    name, pos, named = parse_workflow_reference("foo:2")
    assert name == "foo"
    assert pos == ["2"]
    assert named == {}


def test_parse_workflow_reference_multiline_colon() -> None:
    """Test parsing workflow with multi-line colon syntax (space after colon)."""
    name, pos, named = parse_workflow_reference("foo: Some text here")
    assert name == "foo"
    assert pos == ["Some text here"]
    assert named == {}


def test_parse_workflow_reference_plus_suffix() -> None:
    """Test parsing workflow with plus suffix."""
    name, pos, named = parse_workflow_reference("foo+")
    assert name == "foo"
    assert pos == ["true"]
    assert named == {}


def test_parse_workflow_reference_empty_parens() -> None:
    """Test parsing workflow with empty parentheses."""
    name, pos, named = parse_workflow_reference("workflow()")
    assert name == "workflow"
    assert pos == []
    assert named == {}


def test_parse_workflow_reference_colon_empty_value() -> None:
    """Test parsing workflow with colon but empty value."""
    name, pos, named = parse_workflow_reference("foo:")
    assert name == "foo"
    assert pos == [""]
    assert named == {}
