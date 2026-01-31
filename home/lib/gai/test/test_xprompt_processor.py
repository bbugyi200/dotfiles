"""Tests for the xprompt.processor module."""

import re

from xprompt.models import InputArg, InputType, XPrompt
from xprompt.processor import (
    _SHORTHAND_PATTERN,
    _XPROMPT_PATTERN,
    _find_shorthand_text_end,
    _preprocess_shorthand_syntax,
    _validate_and_convert_args,
)


def test_xprompt_pattern_simple_name() -> None:
    """Test that simple xprompt names match."""
    match = re.search(_XPROMPT_PATTERN, "#foo")
    assert match is not None
    assert match.group(1) == "foo"


def test_xprompt_pattern_with_underscore() -> None:
    """Test that xprompt names with underscores match."""
    match = re.search(_XPROMPT_PATTERN, "#foo_bar")
    assert match is not None
    assert match.group(1) == "foo_bar"


def test_xprompt_pattern_with_numbers() -> None:
    """Test that xprompt names with numbers match."""
    match = re.search(_XPROMPT_PATTERN, "#foo123")
    assert match is not None
    assert match.group(1) == "foo123"


def test_xprompt_pattern_namespaced_single() -> None:
    """Test that single-level namespaced xprompts match."""
    match = re.search(_XPROMPT_PATTERN, "#mentor/aaa")
    assert match is not None
    assert match.group(1) == "mentor/aaa"


def test_xprompt_pattern_namespaced_multi() -> None:
    """Test that multi-level namespaced xprompts match."""
    match = re.search(_XPROMPT_PATTERN, "#foo/bar/baz")
    assert match is not None
    assert match.group(1) == "foo/bar/baz"


def test_xprompt_pattern_namespaced_with_underscore() -> None:
    """Test that namespaced xprompts with underscores match."""
    match = re.search(_XPROMPT_PATTERN, "#my_namespace/my_xprompt")
    assert match is not None
    assert match.group(1) == "my_namespace/my_xprompt"


def test_xprompt_pattern_namespaced_with_numbers() -> None:
    """Test that namespaced xprompts with numbers match."""
    match = re.search(_XPROMPT_PATTERN, "#ns1/prompt2")
    assert match is not None
    assert match.group(1) == "ns1/prompt2"


def test_xprompt_pattern_namespaced_with_args() -> None:
    """Test that namespaced xprompts with parentheses match."""
    match = re.search(_XPROMPT_PATTERN, "#mentor/aaa(arg1)")
    assert match is not None
    assert match.group(1) == "mentor/aaa"
    assert match.group(2) == "("  # Open paren captured


def test_xprompt_pattern_namespaced_with_colon_arg() -> None:
    """Test that namespaced xprompts with colon args match."""
    match = re.search(_XPROMPT_PATTERN, "#foo/bar:value")
    assert match is not None
    assert match.group(1) == "foo/bar"
    assert match.group(3) == "value"


def test_xprompt_pattern_namespaced_with_plus() -> None:
    """Test that namespaced xprompts with plus suffix match."""
    match = re.search(_XPROMPT_PATTERN, "#foo/bar+")
    assert match is not None
    assert match.group(1) == "foo/bar"
    assert match.group(4) == "+"


def test_xprompt_pattern_after_whitespace() -> None:
    """Test that xprompts match after whitespace."""
    match = re.search(_XPROMPT_PATTERN, "text #mentor/aaa")
    assert match is not None
    assert match.group(1) == "mentor/aaa"


def test_xprompt_pattern_at_start() -> None:
    """Test that xprompts match at start of string."""
    match = re.search(_XPROMPT_PATTERN, "#mentor/aaa text")
    assert match is not None
    assert match.group(1) == "mentor/aaa"


def test_xprompt_pattern_after_open_paren() -> None:
    """Test that xprompts match after open parenthesis."""
    match = re.search(_XPROMPT_PATTERN, "(#mentor/aaa)")
    assert match is not None
    assert match.group(1) == "mentor/aaa"


def test_xprompt_pattern_after_quote() -> None:
    """Test that xprompts match after quote."""
    match = re.search(_XPROMPT_PATTERN, '"#mentor/aaa"')
    assert match is not None
    assert match.group(1) == "mentor/aaa"


def test_xprompt_pattern_not_after_letter() -> None:
    """Test that xprompts don't match after letter (e.g., C#)."""
    match = re.search(_XPROMPT_PATTERN, "C#mentor")
    assert match is None


def test_xprompt_pattern_not_double_slash() -> None:
    """Test that double slashes don't match (invalid namespace)."""
    match = re.search(_XPROMPT_PATTERN, "#foo//bar")
    assert match is not None
    # Should only match #foo, not #foo//bar
    assert match.group(1) == "foo"


def test_xprompt_pattern_not_leading_slash() -> None:
    """Test that leading slash doesn't match."""
    match = re.search(_XPROMPT_PATTERN, "#/foo")
    assert match is None


def test_xprompt_pattern_not_trailing_slash() -> None:
    """Test that trailing slash is not part of the match."""
    match = re.search(_XPROMPT_PATTERN, "#foo/")
    assert match is not None
    # Should only match #foo, the trailing slash is not valid namespace
    assert match.group(1) == "foo"


def test_validate_and_convert_args_positional_to_named() -> None:
    """Test that positional args are mapped to named args using input definitions.

    When an xprompt has YAML frontmatter with input definitions like:
        input:
          - name: prompt
            type: text

    And a positional argument is passed like #xprompt([[text]]), the text
    should be accessible both as _1 (positional) and as the named variable
    'prompt' defined in the input specification.
    """
    xprompt = XPrompt(
        name="mentor",
        content="{{ prompt }}",
        inputs=[InputArg(name="prompt", type=InputType.TEXT)],
    )
    positional_args = ["This is my prompt text"]
    named_args: dict[str, str] = {}

    conv_positional, conv_named = _validate_and_convert_args(
        xprompt, positional_args, named_args
    )

    # The positional arg should be in both lists
    assert conv_positional == ["This is my prompt text"]
    # The positional arg should also be mapped to the named arg 'prompt'
    assert conv_named == {"prompt": "This is my prompt text"}


def test_validate_and_convert_args_multiple_positional_to_named() -> None:
    """Test that multiple positional args are mapped to their respective names."""
    xprompt = XPrompt(
        name="test",
        content="{{ first }} and {{ second }}",
        inputs=[
            InputArg(name="first", type=InputType.LINE),
            InputArg(name="second", type=InputType.LINE),
        ],
    )
    positional_args = ["value1", "value2"]
    named_args: dict[str, str] = {}

    conv_positional, conv_named = _validate_and_convert_args(
        xprompt, positional_args, named_args
    )

    assert conv_positional == ["value1", "value2"]
    assert conv_named == {"first": "value1", "second": "value2"}


def test_validate_and_convert_args_explicit_named_arg_not_overwritten() -> None:
    """Test that explicit named args take precedence over positional mapping."""
    xprompt = XPrompt(
        name="test",
        content="{{ prompt }}",
        inputs=[InputArg(name="prompt", type=InputType.TEXT)],
    )
    # Both a positional and a named arg provided for the same input
    positional_args = ["positional value"]
    named_args = {"prompt": "explicit named value"}

    conv_positional, conv_named = _validate_and_convert_args(
        xprompt, positional_args, named_args
    )

    # Positional still maps to named, but then named_args processing overwrites
    assert conv_positional == ["positional value"]
    assert conv_named == {"prompt": "explicit named value"}


# --- Shorthand syntax tests ---


def test_shorthand_pattern_at_start_of_string() -> None:
    """Test that shorthand pattern matches at start of string."""
    match = re.search(_SHORTHAND_PATTERN, "#foo: some text")
    assert match is not None
    assert match.group(1) == "foo"


def test_shorthand_pattern_after_newline() -> None:
    """Test that shorthand pattern matches after newline."""
    match = re.search(_SHORTHAND_PATTERN, "prefix\n#bar: text here")
    assert match is not None
    assert match.group(1) == "bar"


def test_shorthand_pattern_namespaced() -> None:
    """Test that shorthand pattern matches namespaced xprompts."""
    match = re.search(_SHORTHAND_PATTERN, "#mentor/aaa: some text")
    assert match is not None
    assert match.group(1) == "mentor/aaa"


def test_shorthand_pattern_not_mid_line() -> None:
    """Test that shorthand pattern doesn't match mid-line."""
    match = re.search(_SHORTHAND_PATTERN, "text #foo: bar")
    assert match is None


def test_shorthand_pattern_requires_space_after_colon() -> None:
    """Test that pattern requires space after colon (distinguishes from :arg)."""
    # Without space - should not match shorthand pattern
    match = re.search(_SHORTHAND_PATTERN, "#foo:bar")
    assert match is None


def test_find_shorthand_text_end_at_blank_line() -> None:
    """Test finding end at blank line."""
    prompt = "some text here\n\nmore text"
    end = _find_shorthand_text_end(prompt, 0)
    assert end == 14
    assert prompt[end : end + 2] == "\n\n"


def test_find_shorthand_text_end_at_eof() -> None:
    """Test finding end at end of string."""
    prompt = "no blank line here"
    end = _find_shorthand_text_end(prompt, 0)
    assert end == len(prompt)


def test_preprocess_shorthand_single_line() -> None:
    """Test preprocessing single-line shorthand."""
    prompt = "#foo: simple text"
    result = _preprocess_shorthand_syntax(prompt, {"foo"})
    assert result == "#foo([[simple text]])"


def test_preprocess_shorthand_multiline_until_blank() -> None:
    """Test preprocessing multi-line shorthand until blank line."""
    prompt = "#foo: line one\nline two\n\nother text"
    result = _preprocess_shorthand_syntax(prompt, {"foo"})
    assert result == "#foo([[line one\n  line two]])\n\nother text"


def test_preprocess_shorthand_multiline_until_eof() -> None:
    """Test preprocessing multi-line shorthand until end of string."""
    prompt = "#foo: line one\nline two\nline three"
    result = _preprocess_shorthand_syntax(prompt, {"foo"})
    assert result == "#foo([[line one\n  line two\n  line three]])"


def test_preprocess_shorthand_unknown_name_unchanged() -> None:
    """Test that unknown xprompt names are not processed."""
    prompt = "#unknown: some text"
    result = _preprocess_shorthand_syntax(prompt, {"foo", "bar"})
    assert result == "#unknown: some text"


def test_preprocess_shorthand_namespaced() -> None:
    """Test preprocessing namespaced xprompt shorthand."""
    prompt = "#mentor/aaa: review this code"
    result = _preprocess_shorthand_syntax(prompt, {"mentor/aaa"})
    assert result == "#mentor/aaa([[review this code]])"


def test_preprocess_shorthand_multiple_in_prompt() -> None:
    """Test preprocessing multiple shorthands in one prompt."""
    prompt = "#foo: text one\n\n#bar: text two"
    result = _preprocess_shorthand_syntax(prompt, {"foo", "bar"})
    assert result == "#foo([[text one]])\n\n#bar([[text two]])"


def test_preprocess_shorthand_not_at_line_start() -> None:
    """Test that shorthand mid-line is not processed."""
    prompt = "Use #foo: inline"
    result = _preprocess_shorthand_syntax(prompt, {"foo"})
    # Should remain unchanged because #foo: is not at line start
    assert result == "Use #foo: inline"


def test_preprocess_shorthand_preserves_trailing_content() -> None:
    """Test that content after blank line terminator is preserved."""
    # \n\n terminates the shorthand, third \n and "more text" are preserved
    prompt = "#foo: line one\n\n\nmore text"
    result = _preprocess_shorthand_syntax(prompt, {"foo"})
    # Should end at first \n\n, keeping the trailing \n before "more text"
    assert result == "#foo([[line one]])\n\n\nmore text"
