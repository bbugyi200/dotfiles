"""Tests for the query language tokenizer."""

import pytest
from ace.query.tokenizer import TokenizerError, TokenType, tokenize


def test_tokenize_simple_string() -> None:
    """Test tokenizing a simple quoted string."""
    tokens = list(tokenize('"hello"'))
    assert len(tokens) == 2
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == "hello"
    assert tokens[0].case_sensitive is False
    assert tokens[1].type == TokenType.EOF


def test_tokenize_case_sensitive_string() -> None:
    """Test tokenizing a case-sensitive string with c prefix."""
    tokens = list(tokenize('c"Hello"'))
    assert len(tokens) == 2
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == "Hello"
    assert tokens[0].case_sensitive is True


def test_tokenize_and_operator() -> None:
    """Test tokenizing AND operator (case-insensitive)."""
    for keyword in ["AND", "and", "And", "aNd"]:
        tokens = list(tokenize(f'"{keyword}"'))
        # "AND" as a string, not keyword
        assert tokens[0].type == TokenType.STRING

    # AND as keyword
    tokens = list(tokenize('"a" AND "b"'))
    assert tokens[1].type == TokenType.AND


def test_tokenize_or_operator() -> None:
    """Test tokenizing OR operator (case-insensitive)."""
    tokens = list(tokenize('"a" OR "b"'))
    assert tokens[1].type == TokenType.OR


def test_tokenize_not_operator() -> None:
    """Test tokenizing NOT operator."""
    tokens = list(tokenize('!"a"'))
    assert tokens[0].type == TokenType.NOT
    assert tokens[1].type == TokenType.STRING


def test_tokenize_parentheses() -> None:
    """Test tokenizing parentheses."""
    tokens = list(tokenize('("a")'))
    assert tokens[0].type == TokenType.LPAREN
    assert tokens[1].type == TokenType.STRING
    assert tokens[2].type == TokenType.RPAREN


def test_tokenize_escape_sequences() -> None:
    """Test escape sequences in strings."""
    tokens = list(tokenize(r'"hello\nworld"'))
    assert tokens[0].value == "hello\nworld"

    tokens = list(tokenize(r'"say \"hi\""'))
    assert tokens[0].value == 'say "hi"'


def test_tokenize_unterminated_string_error() -> None:
    """Test error on unterminated string."""
    with pytest.raises(TokenizerError) as exc_info:
        list(tokenize('"unterminated'))
    assert "Unterminated string" in str(exc_info.value)


def test_tokenize_bare_word() -> None:
    """Test tokenizing bare word (hello -> STRING "hello")."""
    tokens = list(tokenize("hello"))
    assert len(tokens) == 2
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == "hello"
    assert tokens[0].case_sensitive is False
    assert tokens[1].type == TokenType.EOF


def test_tokenize_bare_word_with_underscores() -> None:
    """Test tokenizing bare word with underscores and hyphens."""
    tokens = list(tokenize("my_test-value"))
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == "my_test-value"


def test_tokenize_bare_word_with_numbers() -> None:
    """Test tokenizing bare word with numbers."""
    tokens = list(tokenize("foo123"))
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == "foo123"


def test_tokenize_bare_word_starting_with_underscore() -> None:
    """Test tokenizing bare word starting with underscore."""
    tokens = list(tokenize("_private"))
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == "_private"


def test_tokenize_bare_word_in_expression() -> None:
    """Test bare word in complex expression."""
    tokens = list(tokenize("foo AND bar"))
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == "foo"
    assert tokens[1].type == TokenType.AND
    assert tokens[2].type == TokenType.STRING
    assert tokens[2].value == "bar"


def test_tokenize_and_with_alphanumeric_suffix_is_bare_word() -> None:
    """Test that AND123 is treated as bare word, not keyword."""
    tokens = list(tokenize("AND123"))
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == "AND123"


def test_tokenize_at_not_standalone_is_error() -> None:
    """Test that @ followed by characters raises an error (@ must be standalone)."""
    with pytest.raises(TokenizerError) as exc_info:
        list(tokenize("@foo"))
    assert "Unexpected character" in str(exc_info.value)


def test_tokenize_triple_at() -> None:
    """Test tokenizing @@@ as RUNNING_AGENT."""
    tokens = list(tokenize("@@@"))
    assert len(tokens) == 2
    assert tokens[0].type == TokenType.RUNNING_AGENT
    assert tokens[0].value == "@@@"
    assert tokens[1].type == TokenType.EOF


def test_tokenize_standalone_at() -> None:
    """Test standalone @ at end tokenizes as RUNNING_AGENT."""
    tokens = list(tokenize("@"))
    assert len(tokens) == 2
    assert tokens[0].type == TokenType.RUNNING_AGENT
    assert tokens[0].value == "@"
    assert tokens[1].type == TokenType.EOF


def test_tokenize_at_with_space() -> None:
    """Test @ followed by space tokenizes as RUNNING_AGENT."""
    tokens = list(tokenize('@ "foo"'))
    assert tokens[0].type == TokenType.RUNNING_AGENT
    assert tokens[0].value == "@"
    assert tokens[1].type == TokenType.STRING
    assert tokens[1].value == "foo"


def test_tokenize_not_at_standalone() -> None:
    """Test standalone !@ tokenizes as NOT_RUNNING_AGENT."""
    tokens = list(tokenize("!@"))
    assert len(tokens) == 2
    assert tokens[0].type == TokenType.NOT_RUNNING_AGENT
    assert tokens[0].value == "!@"
    assert tokens[1].type == TokenType.EOF


def test_tokenize_not_at_with_space() -> None:
    """Test !@ followed by space tokenizes as NOT_RUNNING_AGENT."""
    tokens = list(tokenize('!@ "foo"'))
    assert tokens[0].type == TokenType.NOT_RUNNING_AGENT
    assert tokens[0].value == "!@"
    assert tokens[1].type == TokenType.STRING
    assert tokens[1].value == "foo"


def test_tokenize_triple_exclamation() -> None:
    """Test tokenizing !!! as ERROR_SUFFIX."""
    tokens = list(tokenize("!!!"))
    assert len(tokens) == 2
    assert tokens[0].type == TokenType.ERROR_SUFFIX
    assert tokens[0].value == "!!!"
    assert tokens[1].type == TokenType.EOF


def test_tokenize_standalone_exclamation() -> None:
    """Test standalone ! at end tokenizes as ERROR_SUFFIX."""
    tokens = list(tokenize("!"))
    assert len(tokens) == 2
    assert tokens[0].type == TokenType.ERROR_SUFFIX
    assert tokens[0].value == "!"
    assert tokens[1].type == TokenType.EOF


def test_tokenize_exclamation_with_space() -> None:
    """Test ! followed by space tokenizes as ERROR_SUFFIX."""
    tokens = list(tokenize('! "foo"'))
    assert tokens[0].type == TokenType.ERROR_SUFFIX
    assert tokens[0].value == "!"
    assert tokens[1].type == TokenType.STRING
    assert tokens[1].value == "foo"


def test_tokenize_not_operator_still_works() -> None:
    """Test !"foo" still tokenizes as NOT followed by STRING."""
    tokens = list(tokenize('!"foo"'))
    assert tokens[0].type == TokenType.NOT
    assert tokens[0].value == "!"
    assert tokens[1].type == TokenType.STRING
    assert tokens[1].value == "foo"


def test_tokenize_triple_exclamation_in_expression() -> None:
    """Test !!! in complex expression."""
    tokens = list(tokenize('!!! AND "foo"'))
    assert tokens[0].type == TokenType.ERROR_SUFFIX
    assert tokens[0].value == "!!!"
    assert tokens[1].type == TokenType.AND
    assert tokens[2].type == TokenType.STRING
    assert tokens[2].value == "foo"


def test_tokenize_double_exclamation_standalone() -> None:
    """Test standalone !! tokenizes as NOT_ERROR_SUFFIX."""
    tokens = list(tokenize("!!"))
    assert len(tokens) == 2
    assert tokens[0].type == TokenType.NOT_ERROR_SUFFIX
    assert tokens[0].value == "!!"
    assert tokens[1].type == TokenType.EOF


def test_tokenize_double_exclamation_with_space() -> None:
    """Test !! followed by space tokenizes as NOT_ERROR_SUFFIX."""
    tokens = list(tokenize('!! "foo"'))
    assert tokens[0].type == TokenType.NOT_ERROR_SUFFIX
    assert tokens[0].value == "!!"
    assert tokens[1].type == TokenType.STRING
    assert tokens[1].value == "foo"


def test_tokenize_double_exclamation_not_standalone() -> None:
    """Test !!"foo" tokenizes as NOT NOT STRING (not NOT_ERROR_SUFFIX)."""
    tokens = list(tokenize('!!"foo"'))
    assert tokens[0].type == TokenType.NOT
    assert tokens[1].type == TokenType.NOT
    assert tokens[2].type == TokenType.STRING
    assert tokens[2].value == "foo"
