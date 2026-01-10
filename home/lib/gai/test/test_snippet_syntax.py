"""Tests for snippet syntax features (colon syntax and Jinja2 templates)."""

from unittest.mock import patch

from gemini_wrapper.snippet_processor import process_snippet_references

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
