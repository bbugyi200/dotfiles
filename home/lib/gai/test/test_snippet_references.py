"""Tests for process_xprompt_references function (basic and section xprompts)."""

from unittest.mock import patch

from xprompt.models import XPrompt
from xprompt.processor import process_xprompt_references


def _make_xprompts(snippets: dict[str, str]) -> dict[str, XPrompt]:
    """Helper to convert string dict to XPrompt dict for mocking."""
    return {
        name: XPrompt(name=name, content=content) for name, content in snippets.items()
    }


# Tests for process_xprompt_references


def test_process_xprompt_references_no_hash() -> None:
    """Test that prompts without # are returned unchanged."""
    result = process_xprompt_references("No hash in this prompt")
    assert result == "No hash in this prompt"


def test_process_xprompt_references_no_snippets_defined() -> None:
    """Test with # but no snippets defined returns unchanged."""
    with patch("xprompt.processor.get_all_xprompts", return_value={}):
        result = process_xprompt_references("Using #foo here")
    assert result == "Using #foo here"


def test_process_xprompt_references_unknown_snippet_unchanged() -> None:
    """Test that unknown snippets are left unchanged."""
    snippets = {"bar": "bar content"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("Using #unknown here")
    assert result == "Using #unknown here"


def test_process_xprompt_references_simple_expansion() -> None:
    """Test simple snippet expansion."""
    snippets = {"foo": "expanded foo"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("Using #foo here")
    assert result == "Using expanded foo here"


def test_process_xprompt_references_at_start_of_line() -> None:
    """Test snippet at start of line."""
    snippets = {"foo": "expanded foo"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("#foo at start")
    assert result == "expanded foo at start"


def test_process_xprompt_references_multiple_snippets() -> None:
    """Test expanding multiple snippets in one prompt."""
    snippets = {"foo": "FOO", "bar": "BAR"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("Using #foo and #bar here")
    assert result == "Using FOO and BAR here"


def test_process_xprompt_references_with_args() -> None:
    """Test snippet expansion with arguments."""
    snippets = {"greet": "Hello {1}!"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("Message: #greet(world)")
    assert result == "Message: Hello world!"


def test_process_xprompt_references_with_multiple_args() -> None:
    """Test snippet expansion with multiple arguments."""
    snippets = {"msg": "{1} says {2}"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("#msg(Alice, hello)")
    assert result == "Alice says hello"


def test_process_xprompt_references_nested_expansion() -> None:
    """Test that snippets containing other snippets are expanded."""
    snippets = {"inner": "INNER", "outer": "prefix #inner suffix"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("#outer")
    assert result == "prefix INNER suffix"


def test_process_xprompt_references_multi_level_nesting() -> None:
    """Test three levels of snippet nesting."""
    # Snippets must use whitespace before nested references for pattern matching
    snippets = {
        "level1": "L1",
        "level2": "L2 #level1",
        "level3": "L3 #level2",
    }
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("#level3")
    assert result == "L3 L2 L1"


def test_process_xprompt_references_markdown_heading_not_expanded() -> None:
    """Test that markdown headings are not treated as snippets."""
    snippets = {"Heading": "Should not expand"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("# Heading here")
    # The space after # means it's not a snippet
    assert result == "# Heading here"


def test_process_xprompt_references_after_punctuation() -> None:
    """Test snippet after opening parenthesis."""
    snippets = {"foo": "FOO"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("(#foo)")
    assert result == "(FOO)"


def test_process_xprompt_references_in_brackets() -> None:
    """Test snippet in brackets."""
    snippets = {"foo": "FOO"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("[#foo]")
    assert result == "[FOO]"


def test_process_xprompt_references_in_braces() -> None:
    """Test snippet in braces."""
    snippets = {"foo": "FOO"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("{#foo}")
    assert result == "{FOO}"


def test_process_xprompt_references_with_optional_arg_using_default() -> None:
    """Test snippet with optional arg using default value."""
    snippets = {"opt": "Value is {1:DEFAULT}"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("#opt()")
    assert result == "Value is DEFAULT"


def test_process_xprompt_references_preserves_surrounding_text() -> None:
    """Test that surrounding text is preserved."""
    snippets = {"foo": "FOO"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("before #foo after")
    assert result == "before FOO after"


def test_process_xprompt_references_multiline_prompt() -> None:
    """Test snippet expansion in multiline prompt."""
    snippets = {"foo": "FOO"}
    prompt = """Line 1
#foo
Line 3"""
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references(prompt)
    expected = """Line 1
FOO
Line 3"""
    assert result == expected


def test_process_xprompt_references_hash_in_middle_of_word() -> None:
    """Test that # in middle of word is not treated as snippet."""
    snippets = {"foo": "FOO"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("word#foo")
    # Should NOT expand because # is not after whitespace
    assert result == "word#foo"


# Tests for section snippets (content starting with ###)


def test_process_snippet_section_snippet_at_start_of_line() -> None:
    """Test that section snippet at start of line gets no prefix."""
    snippets = {"sec": "### Section\nContent"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("#sec")
    assert result == "### Section\nContent"


def test_process_snippet_section_snippet_inline() -> None:
    """Test that section snippet after text gets \\n\\n prefix."""
    snippets = {"sec": "### Section\nContent"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("Hello #sec")
    assert result == "Hello \n\n### Section\nContent"


def test_process_snippet_multiple_section_snippets_inline() -> None:
    """Test that chained section snippets each get \\n\\n prefix."""
    snippets = {"foo": "### Foo\nFoo content", "bar": "### Bar\nBar content"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("Hello #foo #bar")
    assert result == "Hello \n\n### Foo\nFoo content \n\n### Bar\nBar content"


def test_process_snippet_section_snippet_after_newline() -> None:
    """Test that section snippet at start of second line gets no prefix."""
    snippets = {"sec": "### Section\nContent"}
    prompt = "First line\n#sec"
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references(prompt)
    assert result == "First line\n### Section\nContent"


def test_process_snippet_section_snippet_after_whitespace_only() -> None:
    """Test that section snippet after indentation gets \\n\\n prefix."""
    snippets = {"sec": "### Section\nContent"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("    #sec")
    assert result == "    \n\n### Section\nContent"


def test_process_snippet_regular_snippet_inline() -> None:
    """Test that non-section snippets inline don't get \\n\\n prefix."""
    snippets = {"reg": "Regular content"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("Hello #reg")
    assert result == "Hello Regular content"


def test_process_snippet_nested_section_snippet() -> None:
    """Test nested section snippets are handled correctly."""
    snippets = {"inner": "### Inner\nInner content", "outer": "Prefix #inner"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("#outer")
    # outer expands to "Prefix #inner", then inner expands with \n\n prefix
    assert result == "Prefix \n\n### Inner\nInner content"


# Tests for horizontal rule snippets (content starting with ---)


def test_process_snippet_hr_snippet_at_start_of_line() -> None:
    """Test that HR snippet at start of line gets no prefix."""
    snippets = {"hr": "---\nContent below rule"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("#hr")
    assert result == "---\nContent below rule"


def test_process_snippet_hr_snippet_inline() -> None:
    """Test that HR snippet after text gets \\n\\n prefix."""
    snippets = {"hr": "---\nContent below rule"}
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references("Hello #hr")
    assert result == "Hello \n\n---\nContent below rule"


def test_process_snippet_hr_snippet_after_newline() -> None:
    """Test that HR snippet at start of second line gets no prefix."""
    snippets = {"hr": "---\nContent below rule"}
    prompt = "First line\n#hr"
    with patch(
        "xprompt.processor.get_all_xprompts", return_value=_make_xprompts(snippets)
    ):
        result = process_xprompt_references(prompt)
    assert result == "First line\n---\nContent below rule"
