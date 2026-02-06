"""Tests for xprompt._parsing functions."""

import pytest
from xprompt._exceptions import XPromptArgumentError
from xprompt._parsing import (
    _find_shorthand_text_end,
    _parse_named_arg,
    _process_text_block,
    escape_for_xprompt,
    find_matching_paren_for_args,
    parse_args,
    parse_workflow_reference,
    preprocess_shorthand_syntax,
)


def test_escape_for_xprompt_plain_text() -> None:
    """Test escape_for_xprompt with plain text."""
    assert escape_for_xprompt("hello world") == "hello world"


def test_escape_for_xprompt_double_quotes() -> None:
    """Test escape_for_xprompt escapes double quotes."""
    assert escape_for_xprompt('say "hello"') == 'say \\"hello\\"'


def test_escape_for_xprompt_backslashes() -> None:
    """Test escape_for_xprompt escapes backslashes."""
    assert escape_for_xprompt("path\\to\\file") == "path\\\\to\\\\file"


def test_escape_for_xprompt_mixed() -> None:
    """Test escape_for_xprompt with both quotes and backslashes."""
    assert escape_for_xprompt('a\\"b') == 'a\\\\\\"b'


# Tests for _process_text_block


def test_process_text_block_non_block() -> None:
    """Test _process_text_block returns non-block values unchanged."""
    assert _process_text_block("hello world") == "hello world"


def test_process_text_block_simple() -> None:
    """Test _process_text_block with a simple text block."""
    result = _process_text_block("[[hello]]")
    assert result == "hello"


def test_process_text_block_multiline() -> None:
    """Test _process_text_block with multiline content."""
    result = _process_text_block("[[first line\n  second line\n  third line]]")
    assert result == "first line\nsecond line\nthird line"


def test_process_text_block_empty_lines() -> None:
    """Test _process_text_block preserves empty lines."""
    result = _process_text_block("[[first\n\n  third]]")
    assert result == "first\n\nthird"


def test_process_text_block_bad_indent() -> None:
    """Test _process_text_block raises on bad indentation."""
    with pytest.raises(XPromptArgumentError, match="must start with 2 spaces"):
        _process_text_block("[[first\nbad indent]]")


# Tests for _find_shorthand_text_end


def test_find_shorthand_text_end_at_double_newline() -> None:
    """Test _find_shorthand_text_end finds double newline."""
    assert _find_shorthand_text_end("hello\n\nworld", 0) == 5


def test_find_shorthand_text_end_at_end_of_string() -> None:
    """Test _find_shorthand_text_end returns len when no double newline."""
    assert _find_shorthand_text_end("hello world", 0) == 11


# Tests for preprocess_shorthand_syntax


def test_preprocess_shorthand_no_match() -> None:
    """Test preprocess_shorthand_syntax with no matching xprompts."""
    result = preprocess_shorthand_syntax("#unknown: text", set())
    assert result == "#unknown: text"


def test_preprocess_shorthand_match() -> None:
    """Test preprocess_shorthand_syntax converts matching xprompts."""
    result = preprocess_shorthand_syntax("#test: hello world", {"test"})
    assert result == "#test([[hello world]])"


def test_preprocess_shorthand_multiline() -> None:
    """Test preprocess_shorthand_syntax with multiline text."""
    result = preprocess_shorthand_syntax("#test: line1\nline2\n\nother", {"test"})
    assert result == "#test([[line1\n  line2]])\n\nother"


def test_preprocess_shorthand_multiline_with_whitespace_line() -> None:
    """Test preprocess_shorthand_syntax handles whitespace-only continuation lines."""
    # A line with spaces is not a double newline, so text continues.
    # The whitespace-only line triggers the empty line branch (line.strip() == "").
    result = preprocess_shorthand_syntax("#test: line1\n  \nline3", {"test"})
    assert result == "#test([[line1\n\n  line3]])"


# Tests for find_matching_paren_for_args


def test_find_matching_paren_simple() -> None:
    """Test find_matching_paren_for_args with simple parens."""
    assert find_matching_paren_for_args("(hello)", 0) == 6


def test_find_matching_paren_not_at_paren() -> None:
    """Test find_matching_paren_for_args returns None when not at paren."""
    assert find_matching_paren_for_args("hello", 0) is None


def test_find_matching_paren_with_text_block() -> None:
    """Test find_matching_paren_for_args handles text blocks."""
    assert find_matching_paren_for_args("([[content]]))", 0) == 12


def test_find_matching_paren_nested() -> None:
    """Test find_matching_paren_for_args handles nested parens."""
    assert find_matching_paren_for_args("(a(b)c)", 0) == 6


def test_find_matching_paren_with_quotes() -> None:
    """Test find_matching_paren_for_args handles quoted strings."""
    assert find_matching_paren_for_args('("hello)")', 0) == 9


# Tests for _parse_named_arg


def test_parse_named_arg_positional() -> None:
    """Test _parse_named_arg with positional value."""
    name, value = _parse_named_arg("hello")
    assert name is None
    assert value == "hello"


def test_parse_named_arg_named() -> None:
    """Test _parse_named_arg with named value."""
    name, value = _parse_named_arg('key="value"')
    assert name == "key"
    assert value == "value"


def test_parse_named_arg_text_block() -> None:
    """Test _parse_named_arg with text block value."""
    name, value = _parse_named_arg("key=[[content]]")
    assert name == "key"
    assert value == "content"


# Tests for parse_args


def test_parse_args_empty() -> None:
    """Test parse_args with empty string."""
    pos, named = parse_args("")
    assert pos == []
    assert named == {}


def test_parse_args_positional_only() -> None:
    """Test parse_args with positional args only."""
    pos, named = parse_args("a, b, c")
    assert pos == ["a", "b", "c"]
    assert named == {}


def test_parse_args_named_only() -> None:
    """Test parse_args with named args only."""
    pos, named = parse_args('x="1", y="2"')
    assert pos == []
    assert named == {"x": "1", "y": "2"}


def test_parse_args_mixed() -> None:
    """Test parse_args with mixed positional and named args."""
    pos, named = parse_args('hello, key="val"')
    assert pos == ["hello"]
    assert named == {"key": "val"}


def test_parse_args_with_text_block() -> None:
    """Test parse_args with text block argument."""
    _, named = parse_args("key=[[multi\n  line]]")
    assert named == {"key": "multi\nline"}


def test_parse_args_quoted_positional() -> None:
    """Test parse_args strips quotes from positional args."""
    pos, _ = parse_args('"hello world"')
    assert pos == ["hello world"]


# Tests for parse_workflow_reference


def test_parse_workflow_reference_plain() -> None:
    """Test parse_workflow_reference with plain name."""
    name, pos, named = parse_workflow_reference("myworkflow")
    assert name == "myworkflow"
    assert pos == []
    assert named == {}


def test_parse_workflow_reference_plus() -> None:
    """Test parse_workflow_reference with plus syntax."""
    name, pos, _ = parse_workflow_reference("myworkflow+")
    assert name == "myworkflow"
    assert pos == ["true"]


def test_parse_workflow_reference_colon() -> None:
    """Test parse_workflow_reference with colon syntax."""
    name, pos, _ = parse_workflow_reference("myworkflow:value")
    assert name == "myworkflow"
    assert pos == ["value"]


def test_parse_workflow_reference_paren() -> None:
    """Test parse_workflow_reference with parenthesis syntax."""
    name, pos, named = parse_workflow_reference('myworkflow(a, key="b")')
    assert name == "myworkflow"
    assert pos == ["a"]
    assert named == {"key": "b"}
