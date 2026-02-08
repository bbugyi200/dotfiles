"""Tests for xprompt._parsing functions."""

import pytest
from xprompt._exceptions import XPromptArgumentError
from xprompt._parsing import (
    _find_double_colon_text_end,
    _find_shorthand_text_end,
    _format_as_text_block,
    _parse_named_arg,
    _preprocess_paren_shorthand,
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


# Tests for _format_as_text_block


def test_format_as_text_block_single_line() -> None:
    """Test _format_as_text_block with a single line."""
    assert _format_as_text_block("hello") == "hello"


def test_format_as_text_block_multiline() -> None:
    """Test _format_as_text_block indents continuation lines."""
    assert _format_as_text_block("line1\nline2\nline3") == "line1\n  line2\n  line3"


def test_format_as_text_block_empty_lines() -> None:
    """Test _format_as_text_block preserves empty lines."""
    assert _format_as_text_block("line1\n\nline3") == "line1\n\n  line3"


# Tests for _preprocess_paren_shorthand


def test_paren_shorthand_basic() -> None:
    """Test #name(arg): text → #name(arg, [[text]])."""
    result = _preprocess_paren_shorthand("#test(arg1): hello world", {"test"})
    assert result == "#test(arg1, [[hello world]])"


def test_paren_shorthand_multiline_double_newline() -> None:
    """Test paren shorthand with multiline text terminated by \\n\\n."""
    result = _preprocess_paren_shorthand("#test(arg1): line1\nline2\n\nother", {"test"})
    assert result == "#test(arg1, [[line1\n  line2]])\n\nother"


def test_paren_shorthand_multiline_eof() -> None:
    """Test paren shorthand with multiline text terminated by EOF."""
    result = _preprocess_paren_shorthand("#test(arg1): line1\nline2", {"test"})
    assert result == "#test(arg1, [[line1\n  line2]])"


def test_paren_shorthand_no_colon_space_not_treated() -> None:
    """Test #name(args) without ): is NOT treated as shorthand."""
    prompt = "#test(arg1)"
    result = _preprocess_paren_shorthand(prompt, {"test"})
    assert result == "#test(arg1)"


def test_paren_shorthand_unknown_name() -> None:
    """Test unknown names are not processed."""
    prompt = "#unknown(arg): hello"
    result = _preprocess_paren_shorthand(prompt, {"test"})
    assert result == "#unknown(arg): hello"


def test_paren_shorthand_empty_parens() -> None:
    """Test #name(): text → #name([[text]])."""
    result = _preprocess_paren_shorthand("#test(): hello world", {"test"})
    assert result == "#test([[hello world]])"


def test_paren_shorthand_file_xprompt_pattern() -> None:
    """Test real-world _file xprompt pattern from one_line_chart_rpc.yml."""
    prompt = "#_file(api_research): Can you help me do some research?"
    result = _preprocess_paren_shorthand(prompt, {"_file"})
    assert result == "#_file(api_research, [[Can you help me do some research?]])"


def test_paren_shorthand_not_at_line_start() -> None:
    """Test paren shorthand not at line start is ignored."""
    prompt = "text before #test(arg): hello"
    result = _preprocess_paren_shorthand(prompt, {"test"})
    assert result == "text before #test(arg): hello"


def test_mixed_paren_and_simple_shorthand() -> None:
    """Test mixed paren + simple shorthand in same prompt."""
    prompt = "#file(name): some text\n\n#simple: other text"
    result = preprocess_shorthand_syntax(prompt, {"file", "simple"})
    assert result == "#file(name, [[some text]])\n\n#simple([[other text]])"


def test_paren_shorthand_multiline_file_pattern() -> None:
    """Test multi-line paren shorthand matching workflow file pattern."""
    prompt = (
        "#_file(prior_art): Can you help me do some research on prior art\n"
        "that uses the API?"
    )
    result = _preprocess_paren_shorthand(prompt, {"_file"})
    assert result == (
        "#_file(prior_art, [[Can you help me do some research on prior art\n"
        "  that uses the API?]])"
    )


# Tests for _find_double_colon_text_end


def test_find_double_colon_text_end_at_eof() -> None:
    """Test _find_double_colon_text_end returns len when no next directive."""
    assert _find_double_colon_text_end("hello world", 0) == 11


def test_find_double_colon_text_end_preserves_blank_lines() -> None:
    """Test that blank lines do NOT terminate double-colon text."""
    prompt = "line1\n\nline3"
    assert _find_double_colon_text_end(prompt, 0) == len(prompt)


def test_find_double_colon_text_end_at_single_colon_directive() -> None:
    """Test termination at a #name: directive on next line."""
    prompt = "some text\n#other: more"
    end = _find_double_colon_text_end(prompt, 0)
    assert end == 9
    assert prompt[end:] == "\n#other: more"


def test_find_double_colon_text_end_at_double_colon_directive() -> None:
    """Test termination at a #name:: directive on next line."""
    prompt = "some text\n#other:: more"
    end = _find_double_colon_text_end(prompt, 0)
    assert end == 9
    assert prompt[end:] == "\n#other:: more"


def test_find_double_colon_text_end_at_paren_directive() -> None:
    """Test termination at a #name( directive on next line."""
    prompt = "some text\n#other(args)"
    end = _find_double_colon_text_end(prompt, 0)
    assert end == 9
    assert prompt[end:] == "\n#other(args)"


# Tests for simple double-colon shorthand


def test_double_colon_shorthand_basic() -> None:
    """Test basic #name:: text conversion."""
    result = preprocess_shorthand_syntax("#foo:: hello world", {"foo"})
    assert result == "#foo([[hello world]])"


def test_double_colon_shorthand_preserves_blank_lines() -> None:
    """Test that blank lines within double-colon text are preserved."""
    prompt = "#foo:: line1\n\nline3"
    result = preprocess_shorthand_syntax(prompt, {"foo"})
    assert result == "#foo([[line1\n\n  line3]])"


def test_double_colon_shorthand_terminated_by_next_directive() -> None:
    """Test double-colon text ends at the next directive."""
    prompt = "#foo:: line1\n\nline3\n#bar: other"
    result = preprocess_shorthand_syntax(prompt, {"foo", "bar"})
    assert result == "#foo([[line1\n\n  line3]])\n#bar([[other]])"


def test_double_colon_shorthand_unknown_name_ignored() -> None:
    """Test that unknown names are not processed for double-colon."""
    prompt = "#unknown:: some text"
    result = preprocess_shorthand_syntax(prompt, {"foo"})
    assert result == "#unknown:: some text"


def test_double_colon_shorthand_not_mid_line() -> None:
    """Test double-colon shorthand is not matched mid-line."""
    prompt = "text before #foo:: hello"
    result = preprocess_shorthand_syntax(prompt, {"foo"})
    assert result == "text before #foo:: hello"


# Tests for paren double-colon shorthand


def test_paren_double_colon_shorthand_basic() -> None:
    """Test #name(arg):: text → #name(arg, [[text]])."""
    result = _preprocess_paren_shorthand("#test(arg1):: hello world", {"test"})
    assert result == "#test(arg1, [[hello world]])"


def test_paren_double_colon_shorthand_preserves_blank_lines() -> None:
    """Test paren double-colon preserves blank lines in text."""
    prompt = "#test(arg1):: line1\n\nline3"
    result = _preprocess_paren_shorthand(prompt, {"test"})
    assert result == "#test(arg1, [[line1\n\n  line3]])"


def test_paren_double_colon_shorthand_empty_parens() -> None:
    """Test #name():: text → #name([[text]])."""
    result = _preprocess_paren_shorthand("#test():: hello world", {"test"})
    assert result == "#test([[hello world]])"


# Tests for mixed directives


def test_mixed_double_colon_and_single_colon() -> None:
    """Test double-colon and single-colon directives in same prompt."""
    prompt = "#foo:: para one\n\npara two\n#bar: single line"
    result = preprocess_shorthand_syntax(prompt, {"foo", "bar"})
    assert result == "#foo([[para one\n\n  para two]])\n#bar([[single line]])"
