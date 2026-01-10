"""Tests for the snippet_processor module."""

from unittest.mock import patch

import pytest
from gemini_wrapper.snippet_processor import (
    _expand_single_snippet,
    _is_jinja2_template,
    _parse_args,
    _parse_named_arg,
    _SnippetArgumentError,
    _SnippetNotFoundError,
    _substitute_placeholders,
    process_snippet_references,
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


# Tests for _is_jinja2_template


def test_is_jinja2_template_variable() -> None:
    """Test detection of Jinja2 variable syntax."""
    assert _is_jinja2_template("Hello {{ name }}!") is True


def test_is_jinja2_template_control() -> None:
    """Test detection of Jinja2 control syntax."""
    assert _is_jinja2_template("{% if x %}yes{% endif %}") is True


def test_is_jinja2_template_comment() -> None:
    """Test detection of Jinja2 comment syntax."""
    assert _is_jinja2_template("{# comment #}") is True


def test_is_jinja2_template_legacy() -> None:
    """Test that legacy syntax is not detected as Jinja2."""
    assert _is_jinja2_template("Hello {1}!") is False
    assert _is_jinja2_template("{1:default}") is False


def test_is_jinja2_template_multiline() -> None:
    """Test detection in multiline content."""
    content = """Line 1
    {{ var }}
    Line 3"""
    assert _is_jinja2_template(content) is True


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


# Tests for process_snippet_references


def test_process_snippet_references_no_hash() -> None:
    """Test that prompts without # are returned unchanged."""
    result = process_snippet_references("No hash in this prompt")
    assert result == "No hash in this prompt"


def test_process_snippet_references_no_snippets_defined() -> None:
    """Test with # but no snippets defined returns unchanged."""
    with patch("gemini_wrapper.snippet_processor.get_all_snippets", return_value={}):
        result = process_snippet_references("Using #foo here")
    assert result == "Using #foo here"


def test_process_snippet_references_unknown_snippet_unchanged() -> None:
    """Test that unknown snippets are left unchanged."""
    snippets = {"bar": "bar content"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("Using #unknown here")
    assert result == "Using #unknown here"


def test_process_snippet_references_simple_expansion() -> None:
    """Test simple snippet expansion."""
    snippets = {"foo": "expanded foo"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("Using #foo here")
    assert result == "Using expanded foo here"


def test_process_snippet_references_at_start_of_line() -> None:
    """Test snippet at start of line."""
    snippets = {"foo": "expanded foo"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#foo at start")
    assert result == "expanded foo at start"


def test_process_snippet_references_multiple_snippets() -> None:
    """Test expanding multiple snippets in one prompt."""
    snippets = {"foo": "FOO", "bar": "BAR"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("Using #foo and #bar here")
    assert result == "Using FOO and BAR here"


def test_process_snippet_references_with_args() -> None:
    """Test snippet expansion with arguments."""
    snippets = {"greet": "Hello {1}!"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("Message: #greet(world)")
    assert result == "Message: Hello world!"


def test_process_snippet_references_with_multiple_args() -> None:
    """Test snippet expansion with multiple arguments."""
    snippets = {"msg": "{1} says {2}"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#msg(Alice, hello)")
    assert result == "Alice says hello"


def test_process_snippet_references_nested_expansion() -> None:
    """Test that snippets containing other snippets are expanded."""
    snippets = {"inner": "INNER", "outer": "prefix #inner suffix"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#outer")
    assert result == "prefix INNER suffix"


def test_process_snippet_references_multi_level_nesting() -> None:
    """Test three levels of snippet nesting."""
    # Snippets must use whitespace before nested references for pattern matching
    snippets = {
        "level1": "L1",
        "level2": "L2 #level1",
        "level3": "L3 #level2",
    }
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#level3")
    assert result == "L3 L2 L1"


def test_process_snippet_references_markdown_heading_not_expanded() -> None:
    """Test that markdown headings are not treated as snippets."""
    snippets = {"Heading": "Should not expand"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("# Heading here")
    # The space after # means it's not a snippet
    assert result == "# Heading here"


def test_process_snippet_references_after_punctuation() -> None:
    """Test snippet after opening parenthesis."""
    snippets = {"foo": "FOO"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("(#foo)")
    assert result == "(FOO)"


def test_process_snippet_references_in_brackets() -> None:
    """Test snippet in brackets."""
    snippets = {"foo": "FOO"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("[#foo]")
    assert result == "[FOO]"


def test_process_snippet_references_in_braces() -> None:
    """Test snippet in braces."""
    snippets = {"foo": "FOO"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("{#foo}")
    assert result == "{FOO}"


def test_process_snippet_references_with_optional_arg_using_default() -> None:
    """Test snippet with optional arg using default value."""
    snippets = {"opt": "Value is {1:DEFAULT}"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#opt()")
    assert result == "Value is DEFAULT"


def test_process_snippet_references_preserves_surrounding_text() -> None:
    """Test that surrounding text is preserved."""
    snippets = {"foo": "FOO"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("before #foo after")
    assert result == "before FOO after"


def test_process_snippet_references_multiline_prompt() -> None:
    """Test snippet expansion in multiline prompt."""
    snippets = {"foo": "FOO"}
    prompt = """Line 1
#foo
Line 3"""
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references(prompt)
    expected = """Line 1
FOO
Line 3"""
    assert result == expected


def test_process_snippet_references_hash_in_middle_of_word() -> None:
    """Test that # in middle of word is not treated as snippet."""
    snippets = {"foo": "FOO"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("word#foo")
    # Should NOT expand because # is not after whitespace
    assert result == "word#foo"


# Tests for section snippets (content starting with ###)


def test_process_snippet_section_snippet_at_start_of_line() -> None:
    """Test that section snippet at start of line gets no prefix."""
    snippets = {"sec": "### Section\nContent"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#sec")
    assert result == "### Section\nContent"


def test_process_snippet_section_snippet_inline() -> None:
    """Test that section snippet after text gets \\n\\n prefix."""
    snippets = {"sec": "### Section\nContent"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("Hello #sec")
    assert result == "Hello \n\n### Section\nContent"


def test_process_snippet_multiple_section_snippets_inline() -> None:
    """Test that chained section snippets each get \\n\\n prefix."""
    snippets = {"foo": "### Foo\nFoo content", "bar": "### Bar\nBar content"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("Hello #foo #bar")
    assert result == "Hello \n\n### Foo\nFoo content \n\n### Bar\nBar content"


def test_process_snippet_section_snippet_after_newline() -> None:
    """Test that section snippet at start of second line gets no prefix."""
    snippets = {"sec": "### Section\nContent"}
    prompt = "First line\n#sec"
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references(prompt)
    assert result == "First line\n### Section\nContent"


def test_process_snippet_section_snippet_after_whitespace_only() -> None:
    """Test that section snippet after indentation gets \\n\\n prefix."""
    snippets = {"sec": "### Section\nContent"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("    #sec")
    assert result == "    \n\n### Section\nContent"


def test_process_snippet_regular_snippet_inline() -> None:
    """Test that non-section snippets inline don't get \\n\\n prefix."""
    snippets = {"reg": "Regular content"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("Hello #reg")
    assert result == "Hello Regular content"


def test_process_snippet_nested_section_snippet() -> None:
    """Test nested section snippets are handled correctly."""
    snippets = {"inner": "### Inner\nInner content", "outer": "Prefix #inner"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#outer")
    # outer expands to "Prefix #inner", then inner expands with \n\n prefix
    assert result == "Prefix \n\n### Inner\nInner content"


# Tests for colon syntax (#name:arg)


def test_process_snippet_colon_syntax_basic() -> None:
    """Test basic colon syntax expands like parenthesis syntax."""
    snippets = {"greet": "Hello {1}!"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#greet:world")
    assert result == "Hello world!"


def test_process_snippet_colon_syntax_numeric_arg() -> None:
    """Test colon syntax with numeric argument."""
    snippets = {"issue": "Issue #{1}"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#issue:123")
    assert result == "Issue #123"


def test_process_snippet_colon_syntax_with_dots() -> None:
    """Test colon syntax with dots in argument (e.g., filenames)."""
    snippets = {"file": "File: {1}"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#file:test.txt")
    assert result == "File: test.txt"


def test_process_snippet_colon_syntax_with_hyphens() -> None:
    """Test colon syntax with hyphens in argument."""
    snippets = {"tag": "Tag: {1}"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#tag:foo-bar-baz")
    assert result == "Tag: foo-bar-baz"


def test_process_snippet_colon_syntax_with_underscores() -> None:
    """Test colon syntax with underscores in argument."""
    snippets = {"var": "Var: {1}"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#var:my_variable")
    assert result == "Var: my_variable"


def test_process_snippet_colon_syntax_terminates_at_whitespace() -> None:
    """Test colon syntax arg terminates at whitespace."""
    snippets = {"greet": "Hello {1}!"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#greet:world and more text")
    assert result == "Hello world! and more text"


def test_process_snippet_colon_syntax_terminates_at_closing_paren() -> None:
    """Test colon syntax arg terminates at closing parenthesis."""
    snippets = {"foo": "FOO({1})"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("(#foo:bar)")
    assert result == "(FOO(bar))"


def test_process_snippet_colon_syntax_terminates_at_closing_bracket() -> None:
    """Test colon syntax arg terminates at closing bracket."""
    snippets = {"foo": "FOO[{1}]"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("[#foo:bar]")
    assert result == "[FOO[bar]]"


def test_process_snippet_colon_syntax_terminates_at_closing_brace() -> None:
    """Test colon syntax arg terminates at closing brace."""
    snippets = {"foo": "FOO({1})"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("{#foo:bar}")
    assert result == "{FOO(bar)}"


def test_process_snippet_colon_syntax_at_start_of_line() -> None:
    """Test colon syntax at start of line."""
    snippets = {"greet": "Hello {1}!"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#greet:world")
    assert result == "Hello world!"


def test_process_snippet_colon_syntax_after_newline() -> None:
    """Test colon syntax after newline."""
    snippets = {"greet": "Hello {1}!"}
    prompt = "First line\n#greet:world"
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references(prompt)
    assert result == "First line\nHello world!"


def test_process_snippet_paren_syntax_still_works_with_colon() -> None:
    """Test parenthesis syntax still works alongside colon syntax."""
    snippets = {"greet": "Hello {1}!"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#greet(world)")
    assert result == "Hello world!"


def test_process_snippet_paren_syntax_multiple_args_still_works() -> None:
    """Test parenthesis syntax with multiple args still works."""
    snippets = {"msg": "{1} says {2}"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#msg(Alice, hello)")
    assert result == "Alice says hello"


def test_process_snippet_colon_and_paren_in_same_prompt() -> None:
    """Test using both colon and parenthesis syntax in same prompt."""
    snippets = {"greet": "Hello {1}!", "msg": "{1} says {2}"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#greet:world and #msg(Alice, hi)")
    assert result == "Hello world! and Alice says hi"


# Tests for Jinja2 templates with process_snippet_references


def test_process_snippet_jinja2_named_args() -> None:
    """Test Jinja2 snippet with named arguments."""
    snippets = {"greet": "Hello {{ name }}!"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#greet(name=World)")
    assert result == "Hello World!"


def test_process_snippet_jinja2_multiple_named_args() -> None:
    """Test Jinja2 snippet with multiple named arguments."""
    snippets = {"msg": "{{ sender }} says {{ message }}"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#msg(sender=Alice, message=hello)")
    assert result == "Alice says hello"


def test_process_snippet_jinja2_quoted_named_args() -> None:
    """Test Jinja2 snippet with quoted named arguments containing spaces."""
    snippets = {"greet": "Hello {{ name }}!"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references('#greet(name="Big World")')
    assert result == "Hello Big World!"


def test_process_snippet_jinja2_mixed_args() -> None:
    """Test Jinja2 snippet with mixed positional and named arguments."""
    snippets = {"msg": "{{ _1 }} says {{ message }}"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#msg(Alice, message=hello)")
    assert result == "Alice says hello"


def test_process_snippet_jinja2_conditional() -> None:
    """Test Jinja2 snippet with conditional."""
    snippets = {"greet": "Hello {{ name }}{% if formal %}, sir{% endif %}!"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#greet(name=Bob, formal=yes)")
    assert result == "Hello Bob, sir!"


def test_process_snippet_jinja2_default_filter() -> None:
    """Test Jinja2 snippet with default filter."""
    snippets = {"greet": "Hello {{ name | default('World') }}!"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#greet()")
    assert result == "Hello World!"


def test_process_snippet_jinja2_upper_filter() -> None:
    """Test Jinja2 snippet with upper filter."""
    snippets = {"shout": "{{ text | upper }}"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#shout(text=hello)")
    assert result == "HELLO"


def test_process_snippet_jinja2_colon_syntax() -> None:
    """Test Jinja2 snippet with colon syntax maps to _1."""
    snippets = {"greet": "Hello {{ _1 }}!"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#greet:World")
    assert result == "Hello World!"


def test_process_snippet_nested_jinja2() -> None:
    """Test nested Jinja2 snippets."""
    snippets = {
        "inner": "{{ name | upper }}",
        "outer": "Greeting: #inner(name=world)",
    }
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#outer()")
    assert result == "Greeting: WORLD"


def test_process_snippet_legacy_still_works() -> None:
    """Test that legacy {1} placeholder syntax still works."""
    snippets = {"greet": "Hello {1}!"}
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#greet(World)")
    assert result == "Hello World!"


def test_process_snippet_legacy_and_jinja2_together() -> None:
    """Test that legacy and Jinja2 snippets can coexist."""
    snippets = {
        "legacy": "Hello {1}!",
        "jinja": "Goodbye {{ name }}!",
    }
    with patch(
        "gemini_wrapper.snippet_processor.get_all_snippets", return_value=snippets
    ):
        result = process_snippet_references("#legacy(World) and #jinja(name=Universe)")
    assert result == "Hello World! and Goodbye Universe!"
