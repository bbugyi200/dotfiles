"""Tests for standalone step execution and xprompt utilities."""

import pytest
from main.query_handler._query import _evaluate_standalone_condition
from shared_utils import dump_yaml
from xprompt._exceptions import XPromptArgumentError
from xprompt._jinja import (
    _substitute_legacy_placeholders,
    is_jinja2_template,
    render_toplevel_jinja2,
    substitute_placeholders,
    validate_and_convert_args,
)
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
from xprompt.models import (
    InputArg,
    InputType,
    XPrompt,
    XPromptValidationError,
    xprompt_to_workflow,
)
from xprompt.workflow_executor_utils import parse_bash_output


def test_evaluate_standalone_condition_truthy_string() -> None:
    """Test condition evaluates to True for truthy string values."""
    context = {"check_changes": {"has_changes": "true"}}
    result = _evaluate_standalone_condition("{{ check_changes.has_changes }}", context)
    assert result is True


def test_evaluate_standalone_condition_false_string() -> None:
    """Test condition evaluates to False for 'false' string."""
    context = {"check_changes": {"has_changes": "false"}}
    result = _evaluate_standalone_condition("{{ check_changes.has_changes }}", context)
    assert result is False


def test_evaluate_standalone_condition_empty_string() -> None:
    """Test condition evaluates to False for empty string."""
    context = {"value": ""}
    result = _evaluate_standalone_condition("{{ value }}", context)
    assert result is False


def test_evaluate_standalone_condition_missing_variable() -> None:
    """Test condition evaluates to False when variable is missing."""
    result = _evaluate_standalone_condition("{{ nonexistent }}", {})
    assert result is False


def test_evaluate_standalone_condition_boolean_true() -> None:
    """Test condition with boolean True value."""
    context = {"flag": True}
    result = _evaluate_standalone_condition("{{ flag }}", context)
    assert result is True


def test_evaluate_standalone_condition_none_value() -> None:
    """Test condition evaluates to False for 'none' string."""
    context = {"value": "none"}
    result = _evaluate_standalone_condition("{{ value }}", context)
    assert result is False


def test_evaluate_standalone_condition_zero_value() -> None:
    """Test condition evaluates to False for '0' string."""
    context = {"value": "0"}
    result = _evaluate_standalone_condition("{{ value }}", context)
    assert result is False


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


# Tests for preprocess_shorthand_syntax with empty lines (covers line 89)


def test_preprocess_shorthand_multiline_with_whitespace_line() -> None:
    """Test preprocess_shorthand_syntax handles whitespace-only continuation lines."""
    # A line with spaces is not a double newline, so text continues.
    # The whitespace-only line triggers the empty line branch (line.strip() == "").
    result = preprocess_shorthand_syntax("#test: line1\n  \nline3", {"test"})
    assert result == "#test([[line1\n\n  line3]])"


# Tests for is_jinja2_template


def test_is_jinja2_template_variable() -> None:
    """Test is_jinja2_template detects {{ }} variable syntax."""
    assert is_jinja2_template("Hello {{ name }}") is True


def test_is_jinja2_template_control() -> None:
    """Test is_jinja2_template detects {% %} control structures."""
    assert is_jinja2_template("{% if x %}hello{% endif %}") is True


def test_is_jinja2_template_comment() -> None:
    """Test is_jinja2_template detects {# #} comment syntax."""
    assert is_jinja2_template("{# a comment #}") is True


def test_is_jinja2_template_plain() -> None:
    """Test is_jinja2_template returns False for plain text."""
    assert is_jinja2_template("just plain text") is False


# Tests for _substitute_legacy_placeholders


def test_substitute_legacy_simple() -> None:
    """Test _substitute_legacy_placeholders with simple replacement."""
    result = _substitute_legacy_placeholders("Hello {1}!", ["world"], "test")
    assert result == "Hello world!"


def test_substitute_legacy_multiple() -> None:
    """Test _substitute_legacy_placeholders with multiple args."""
    result = _substitute_legacy_placeholders("{1} and {2}", ["foo", "bar"], "test")
    assert result == "foo and bar"


def test_substitute_legacy_default() -> None:
    """Test _substitute_legacy_placeholders uses default when arg missing."""
    result = _substitute_legacy_placeholders("{1:fallback}", [], "test")
    assert result == "fallback"


def test_substitute_legacy_missing_arg_error() -> None:
    """Test _substitute_legacy_placeholders raises on missing required arg."""
    with pytest.raises(XPromptArgumentError, match="requires argument"):
        _substitute_legacy_placeholders("{1}", [], "test")


# Tests for render_toplevel_jinja2


def test_render_toplevel_jinja2_simple() -> None:
    """Test render_toplevel_jinja2 with plain text (no Jinja2)."""
    result = render_toplevel_jinja2("Hello world")
    assert result == "Hello world"


# Tests for substitute_placeholders


def test_substitute_placeholders_jinja2_mode() -> None:
    """Test substitute_placeholders uses Jinja2 when template detected."""
    result = substitute_placeholders("Hello {{ name }}", [], {"name": "world"}, "test")
    assert result == "Hello world"


def test_substitute_placeholders_legacy_mode() -> None:
    """Test substitute_placeholders uses legacy when no Jinja2 syntax."""
    result = substitute_placeholders("Hello {1}", ["world"], {}, "test")
    assert result == "Hello world"


# Tests for parse_bash_output


def test_parse_bash_output_json() -> None:
    """Test parse_bash_output with valid JSON."""
    result = parse_bash_output('{"key": "value", "num": 42}')
    assert result == {"key": "value", "num": 42}


def test_parse_bash_output_invalid_json() -> None:
    """Test parse_bash_output with invalid JSON falls through."""
    result = parse_bash_output("{not valid json")
    assert result == {"_output": "{not valid json"}


def test_parse_bash_output_key_value() -> None:
    """Test parse_bash_output with key=value format."""
    result = parse_bash_output("name=alice\nage=30")
    assert result == {"name": "alice", "age": "30"}


def test_parse_bash_output_plain_text() -> None:
    """Test parse_bash_output with plain text output."""
    result = parse_bash_output("just some output")
    assert result == {"_output": "just some output"}


def test_parse_bash_output_empty_lines() -> None:
    """Test parse_bash_output skips empty lines."""
    result = parse_bash_output("key=val\n\nother=thing")
    assert result == {"key": "val", "other": "thing"}


def test_parse_bash_output_empty() -> None:
    """Test parse_bash_output with empty input."""
    result = parse_bash_output("")
    assert result == {}


def test_parse_bash_output_json_array() -> None:
    """Test parse_bash_output with JSON array."""
    result = parse_bash_output("[1, 2, 3]")
    assert result == [1, 2, 3]


# Tests for dump_yaml


def test_dump_yaml_single_line() -> None:
    """Test dump_yaml with single-line string (covers else branch)."""
    result = dump_yaml({"msg": "hello"})
    assert "msg: hello" in result


def test_dump_yaml_multiline() -> None:
    """Test dump_yaml with multiline string uses literal block style."""
    result = dump_yaml({"msg": "line1\nline2\n"})
    assert "msg:" in result
    # Should use literal block style (|)
    assert "|" in result


# Tests for InputArg.validate_and_convert


def test_input_arg_word_valid() -> None:
    """Test InputArg validates word type correctly."""
    arg = InputArg(name="x", type=InputType.WORD)
    assert arg.validate_and_convert("hello") == "hello"


def test_input_arg_word_with_spaces() -> None:
    """Test InputArg rejects word with spaces."""
    arg = InputArg(name="x", type=InputType.WORD)
    with pytest.raises(XPromptValidationError, match="expects word"):
        arg.validate_and_convert("hello world")


def test_input_arg_line_valid() -> None:
    """Test InputArg validates line type correctly."""
    arg = InputArg(name="x", type=InputType.LINE)
    assert arg.validate_and_convert("hello world") == "hello world"


def test_input_arg_line_with_newline() -> None:
    """Test InputArg rejects line with newlines."""
    arg = InputArg(name="x", type=InputType.LINE)
    with pytest.raises(XPromptValidationError, match="expects line"):
        arg.validate_and_convert("hello\nworld")


def test_input_arg_text_any_content() -> None:
    """Test InputArg text type accepts anything."""
    arg = InputArg(name="x", type=InputType.TEXT)
    assert arg.validate_and_convert("hello\nworld") == "hello\nworld"


def test_input_arg_int_valid() -> None:
    """Test InputArg validates int type correctly."""
    arg = InputArg(name="x", type=InputType.INT)
    assert arg.validate_and_convert("42") == 42


def test_input_arg_int_invalid() -> None:
    """Test InputArg rejects invalid int."""
    arg = InputArg(name="x", type=InputType.INT)
    with pytest.raises(XPromptValidationError, match="expects int"):
        arg.validate_and_convert("abc")


def test_input_arg_float_valid() -> None:
    """Test InputArg validates float type correctly."""
    arg = InputArg(name="x", type=InputType.FLOAT)
    assert arg.validate_and_convert("3.14") == pytest.approx(3.14)


def test_input_arg_float_invalid() -> None:
    """Test InputArg rejects invalid float."""
    arg = InputArg(name="x", type=InputType.FLOAT)
    with pytest.raises(XPromptValidationError, match="expects float"):
        arg.validate_and_convert("not_a_float")


def test_input_arg_bool_true() -> None:
    """Test InputArg validates bool true values."""
    arg = InputArg(name="x", type=InputType.BOOL)
    assert arg.validate_and_convert("true") is True
    assert arg.validate_and_convert("yes") is True
    assert arg.validate_and_convert("1") is True
    assert arg.validate_and_convert("on") is True


def test_input_arg_bool_false() -> None:
    """Test InputArg validates bool false values."""
    arg = InputArg(name="x", type=InputType.BOOL)
    assert arg.validate_and_convert("false") is False
    assert arg.validate_and_convert("no") is False
    assert arg.validate_and_convert("0") is False
    assert arg.validate_and_convert("off") is False


def test_input_arg_bool_invalid() -> None:
    """Test InputArg rejects invalid bool."""
    arg = InputArg(name="x", type=InputType.BOOL)
    with pytest.raises(XPromptValidationError, match="expects bool"):
        arg.validate_and_convert("maybe")


# Tests for XPrompt


def test_xprompt_get_input_by_name_found() -> None:
    """Test XPrompt.get_input_by_name returns matching input."""
    xp = XPrompt(
        name="test",
        content="hello",
        inputs=[InputArg(name="x"), InputArg(name="y")],
    )
    result = xp.get_input_by_name("y")
    assert result is not None
    assert result.name == "y"


def test_xprompt_get_input_by_name_not_found() -> None:
    """Test XPrompt.get_input_by_name returns None when not found."""
    xp = XPrompt(name="test", content="hello", inputs=[InputArg(name="x")])
    assert xp.get_input_by_name("z") is None


def test_xprompt_get_input_by_position_valid() -> None:
    """Test XPrompt.get_input_by_position with valid index."""
    xp = XPrompt(
        name="test",
        content="hello",
        inputs=[InputArg(name="a"), InputArg(name="b")],
    )
    result = xp.get_input_by_position(1)
    assert result is not None
    assert result.name == "b"


def test_xprompt_get_input_by_position_out_of_range() -> None:
    """Test XPrompt.get_input_by_position returns None for out of range."""
    xp = XPrompt(name="test", content="hello", inputs=[InputArg(name="a")])
    assert xp.get_input_by_position(5) is None


# Tests for xprompt_to_workflow


def test_xprompt_to_workflow() -> None:
    """Test converting XPrompt to Workflow."""
    xp = XPrompt(name="mytest", content="hello {{ name }}", source_path="/test.md")
    wf = xprompt_to_workflow(xp)
    assert wf.name == "mytest"
    assert len(wf.steps) == 1
    assert wf.steps[0].name == "main"
    assert wf.steps[0].prompt_part == "hello {{ name }}"
    assert wf.source_path == "/test.md"


# Tests for validate_and_convert_args


def test_validate_and_convert_args_no_inputs() -> None:
    """Test validate_and_convert_args passes through when no inputs defined."""
    xp = XPrompt(name="test", content="hello")
    pos, named = validate_and_convert_args(xp, ["a", "b"], {"c": "d"})
    assert pos == ["a", "b"]
    assert named == {"c": "d"}


def test_validate_and_convert_args_positional() -> None:
    """Test validate_and_convert_args converts positional args."""
    xp = XPrompt(
        name="test",
        content="hello",
        inputs=[InputArg(name="count", type=InputType.INT)],
    )
    pos, named = validate_and_convert_args(xp, ["42"], {})
    assert pos == [42]
    assert named == {"count": 42}


def test_validate_and_convert_args_named() -> None:
    """Test validate_and_convert_args converts named args."""
    xp = XPrompt(
        name="test",
        content="hello",
        inputs=[InputArg(name="flag", type=InputType.BOOL)],
    )
    pos, named = validate_and_convert_args(xp, [], {"flag": "true"})
    assert pos == []
    assert named == {"flag": True}


def test_validate_and_convert_args_defaults() -> None:
    """Test validate_and_convert_args applies defaults for missing inputs."""
    xp = XPrompt(
        name="test",
        content="hello",
        inputs=[InputArg(name="x", type=InputType.LINE, default="fallback")],
    )
    _, named = validate_and_convert_args(xp, [], {})
    assert named == {"x": "fallback"}


def test_validate_and_convert_args_extra_positional() -> None:
    """Test validate_and_convert_args passes through extra positional args."""
    xp = XPrompt(
        name="test",
        content="hello",
        inputs=[InputArg(name="x", type=InputType.LINE)],
    )
    pos, _ = validate_and_convert_args(xp, ["a", "extra"], {})
    assert pos == ["a", "extra"]


def test_validate_and_convert_args_unknown_named() -> None:
    """Test validate_and_convert_args passes through unknown named args."""
    xp = XPrompt(
        name="test",
        content="hello",
        inputs=[InputArg(name="x", type=InputType.LINE)],
    )
    _, named = validate_and_convert_args(xp, [], {"unknown": "val"})
    assert named == {"unknown": "val"}


def test_validate_and_convert_args_positional_error() -> None:
    """Test validate_and_convert_args raises on positional conversion error."""
    xp = XPrompt(
        name="test",
        content="hello",
        inputs=[InputArg(name="n", type=InputType.INT)],
    )
    with pytest.raises(XPromptArgumentError, match="argument error"):
        validate_and_convert_args(xp, ["not_a_number"], {})


def test_validate_and_convert_args_named_error() -> None:
    """Test validate_and_convert_args raises on named conversion error."""
    xp = XPrompt(
        name="test",
        content="hello",
        inputs=[InputArg(name="n", type=InputType.INT)],
    )
    with pytest.raises(XPromptArgumentError, match="argument error"):
        validate_and_convert_args(xp, [], {"n": "not_a_number"})


def test_input_arg_path_with_spaces() -> None:
    """Test InputArg rejects path with spaces."""
    arg = InputArg(name="x", type=InputType.PATH)
    with pytest.raises(XPromptValidationError, match="expects path"):
        arg.validate_and_convert("path with spaces")
