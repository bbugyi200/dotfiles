"""Tests for the query language parser and evaluator."""

import pytest
from ace.changespec import ChangeSpec
from ace.query import (
    AndExpr,
    NotExpr,
    OrExpr,
    QueryParseError,
    StringMatch,
    evaluate_query,
    parse_query,
    to_canonical_string,
)
from ace.query.tokenizer import TokenizerError, TokenType, tokenize
from ace.query.types import ERROR_SUFFIX_QUERY

# --- Tokenizer Tests ---


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


def test_tokenize_unknown_keyword_error() -> None:
    """Test error on unknown keyword."""
    with pytest.raises(TokenizerError) as exc_info:
        list(tokenize('"a" INVALID "b"'))
    assert "Unknown keyword" in str(exc_info.value)


def test_tokenize_bare_string() -> None:
    """Test tokenizing bare string shorthand (@foo)."""
    tokens = list(tokenize("@hello"))
    assert len(tokens) == 2
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == "hello"
    assert tokens[0].case_sensitive is False
    assert tokens[1].type == TokenType.EOF


def test_tokenize_bare_string_with_underscores() -> None:
    """Test tokenizing bare string with underscores and hyphens."""
    tokens = list(tokenize("@my_test-value"))
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == "my_test-value"


def test_tokenize_bare_string_empty_error() -> None:
    """Test error on empty bare string."""
    with pytest.raises(TokenizerError) as exc_info:
        list(tokenize("@ "))
    assert "Empty bare string" in str(exc_info.value)


def test_tokenize_bare_string_in_expression() -> None:
    """Test bare string in complex expression."""
    tokens = list(tokenize("@foo AND @bar"))
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == "foo"
    assert tokens[1].type == TokenType.AND
    assert tokens[2].type == TokenType.STRING
    assert tokens[2].value == "bar"


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


# --- Parser Tests ---


def test_parse_simple_string() -> None:
    """Test parsing a simple string."""
    result = parse_query('"foobar"')
    assert isinstance(result, StringMatch)
    assert result.value == "foobar"
    assert result.case_sensitive is False


def test_parse_case_sensitive_string() -> None:
    """Test parsing a case-sensitive string."""
    result = parse_query('c"FooBar"')
    assert isinstance(result, StringMatch)
    assert result.value == "FooBar"
    assert result.case_sensitive is True


def test_parse_not_expression() -> None:
    """Test parsing NOT expression."""
    result = parse_query('!"draft"')
    assert isinstance(result, NotExpr)
    assert isinstance(result.operand, StringMatch)
    assert result.operand.value == "draft"


def test_parse_double_not() -> None:
    """Test parsing double NOT (should cancel out conceptually)."""
    result = parse_query('!!"draft"')
    assert isinstance(result, NotExpr)
    assert isinstance(result.operand, NotExpr)
    assert isinstance(result.operand.operand, StringMatch)


def test_parse_and_expression() -> None:
    """Test parsing AND expression."""
    result = parse_query('"a" AND "b"')
    assert isinstance(result, AndExpr)
    assert len(result.operands) == 2
    assert result.operands[0].value == "a"  # type: ignore
    assert result.operands[1].value == "b"  # type: ignore


def test_parse_or_expression() -> None:
    """Test parsing OR expression."""
    result = parse_query('"a" OR "b"')
    assert isinstance(result, OrExpr)
    assert len(result.operands) == 2


def test_parse_and_or_precedence() -> None:
    """Test that AND binds tighter than OR."""
    # "a" OR "b" AND "c" should parse as "a" OR ("b" AND "c")
    result = parse_query('"a" OR "b" AND "c"')
    assert isinstance(result, OrExpr)
    assert len(result.operands) == 2
    assert isinstance(result.operands[0], StringMatch)
    assert isinstance(result.operands[1], AndExpr)


def test_parse_grouped_expression() -> None:
    """Test parsing grouped expression with parentheses."""
    result = parse_query('("a" OR "b") AND "c"')
    assert isinstance(result, AndExpr)
    assert len(result.operands) == 2
    assert isinstance(result.operands[0], OrExpr)
    assert isinstance(result.operands[1], StringMatch)


def test_parse_complex_expression() -> None:
    """Test parsing complex expression."""
    result = parse_query('"feature" AND ("test" OR "spec") AND !"skip"')
    assert isinstance(result, AndExpr)
    assert len(result.operands) == 3


def test_parse_error_empty_query() -> None:
    """Test error on empty query."""
    with pytest.raises(QueryParseError) as exc_info:
        parse_query("")
    assert "Empty query" in str(exc_info.value)


def test_parse_error_unmatched_paren() -> None:
    """Test error on unmatched parenthesis."""
    with pytest.raises(QueryParseError) as exc_info:
        parse_query('("a"')
    assert "RPAREN" in str(exc_info.value)


def test_parse_error_missing_operand() -> None:
    """Test error on missing operand after AND."""
    with pytest.raises(QueryParseError) as exc_info:
        parse_query('"a" AND')
    assert "Expected" in str(exc_info.value)


def test_parse_bare_string() -> None:
    """Test parsing bare string shorthand."""
    result = parse_query("@foobar")
    assert isinstance(result, StringMatch)
    assert result.value == "foobar"
    assert result.case_sensitive is False


def test_parse_implicit_and() -> None:
    """Test parsing implicit AND (juxtaposition)."""
    result = parse_query('"a" "b"')
    assert isinstance(result, AndExpr)
    assert len(result.operands) == 2
    assert result.operands[0].value == "a"  # type: ignore
    assert result.operands[1].value == "b"  # type: ignore


def test_parse_implicit_and_multiple() -> None:
    """Test parsing multiple implicit ANDs."""
    result = parse_query('"a" "b" "c"')
    assert isinstance(result, AndExpr)
    assert len(result.operands) == 3


def test_parse_implicit_and_with_explicit() -> None:
    """Test mixing implicit and explicit ANDs."""
    result = parse_query('"a" AND "b" "c"')
    assert isinstance(result, AndExpr)
    assert len(result.operands) == 3


def test_parse_implicit_and_with_or() -> None:
    """Test implicit AND with OR."""
    # "a" "b" OR "c" should parse as ("a" AND "b") OR "c"
    result = parse_query('"a" "b" OR "c"')
    assert isinstance(result, OrExpr)
    assert len(result.operands) == 2
    assert isinstance(result.operands[0], AndExpr)
    assert isinstance(result.operands[1], StringMatch)


def test_parse_implicit_and_with_not() -> None:
    """Test implicit AND with NOT."""
    result = parse_query('"a" !"b"')
    assert isinstance(result, AndExpr)
    assert len(result.operands) == 2
    assert isinstance(result.operands[0], StringMatch)
    assert isinstance(result.operands[1], NotExpr)


def test_parse_implicit_and_with_parens() -> None:
    """Test implicit AND with parentheses."""
    result = parse_query('"a" ("b" OR "c")')
    assert isinstance(result, AndExpr)
    assert len(result.operands) == 2
    assert isinstance(result.operands[0], StringMatch)
    assert isinstance(result.operands[1], OrExpr)


def test_parse_user_example() -> None:
    """Test the example from the user request."""
    result = parse_query('"foo" "bar" ("baz" or "pig")')
    assert isinstance(result, AndExpr)
    assert len(result.operands) == 3
    assert isinstance(result.operands[0], StringMatch)
    assert result.operands[0].value == "foo"  # type: ignore
    assert isinstance(result.operands[1], StringMatch)
    assert result.operands[1].value == "bar"  # type: ignore
    assert isinstance(result.operands[2], OrExpr)


def test_parse_triple_exclamation() -> None:
    """Test parsing !!! as error suffix search."""
    result = parse_query("!!!")
    assert isinstance(result, StringMatch)
    assert result.value == ERROR_SUFFIX_QUERY
    assert result.is_error_suffix is True


def test_parse_standalone_exclamation() -> None:
    """Test parsing standalone ! as error suffix search."""
    result = parse_query("!")
    assert isinstance(result, StringMatch)
    assert result.value == ERROR_SUFFIX_QUERY
    assert result.is_error_suffix is True


def test_parse_error_suffix_and_string() -> None:
    """Test parsing !!! AND "foo"."""
    result = parse_query('!!! AND "foo"')
    assert isinstance(result, AndExpr)
    assert len(result.operands) == 2
    assert isinstance(result.operands[0], StringMatch)
    assert result.operands[0].is_error_suffix is True
    assert isinstance(result.operands[1], StringMatch)
    assert result.operands[1].value == "foo"


def test_parse_error_suffix_implicit_and() -> None:
    """Test parsing ! "foo" (implicit AND with error suffix)."""
    result = parse_query('! "foo"')
    assert isinstance(result, AndExpr)
    assert len(result.operands) == 2
    assert isinstance(result.operands[0], StringMatch)
    assert result.operands[0].is_error_suffix is True
    assert isinstance(result.operands[1], StringMatch)
    assert result.operands[1].value == "foo"


# --- Canonicalization Tests ---


def test_canonical_simple_string() -> None:
    """Test canonicalization of simple string."""
    result = parse_query('"foo"')
    assert to_canonical_string(result) == '"foo"'


def test_canonical_case_sensitive_string() -> None:
    """Test canonicalization of case-sensitive string."""
    result = parse_query('c"Foo"')
    assert to_canonical_string(result) == 'c"Foo"'


def test_canonical_bare_string() -> None:
    """Test canonicalization of bare string shorthand."""
    result = parse_query("@foo")
    assert to_canonical_string(result) == '"foo"'


def test_canonical_not() -> None:
    """Test canonicalization of NOT expression."""
    result = parse_query('!"foo"')
    assert to_canonical_string(result) == '!"foo"'


def test_canonical_explicit_and() -> None:
    """Test canonicalization of explicit AND."""
    result = parse_query('"a" AND "b"')
    assert to_canonical_string(result) == '"a" AND "b"'


def test_canonical_implicit_and() -> None:
    """Test canonicalization of implicit AND."""
    result = parse_query('"a" "b"')
    assert to_canonical_string(result) == '"a" AND "b"'


def test_canonical_or() -> None:
    """Test canonicalization of OR expression."""
    result = parse_query('"a" OR "b"')
    assert to_canonical_string(result) == '"a" OR "b"'


def test_canonical_complex() -> None:
    """Test canonicalization of complex expression."""
    result = parse_query('@foo @bar ("baz" or "pig")')
    assert to_canonical_string(result) == '"foo" AND "bar" AND ("baz" OR "pig")'


def test_canonical_user_example() -> None:
    """Test the example from the user request."""
    result = parse_query('"foo" "bar" ("baz" or "pig")')
    assert to_canonical_string(result) == '"foo" AND "bar" AND ("baz" OR "pig")'


def test_canonical_escape_sequences() -> None:
    """Test canonicalization preserves escape sequences."""
    result = parse_query(r'"hello\nworld"')
    assert to_canonical_string(result) == r'"hello\nworld"'


def test_canonical_escape_quotes() -> None:
    """Test canonicalization escapes quotes properly."""
    result = parse_query(r'"say \"hi\""')
    assert to_canonical_string(result) == r'"say \"hi\""'


def test_canonical_error_suffix() -> None:
    """Test canonicalization of error suffix shorthand."""
    result = parse_query("!!!")
    assert to_canonical_string(result) == "!!!"


def test_canonical_standalone_exclamation() -> None:
    """Test canonicalization of standalone ! becomes !!!."""
    result = parse_query("!")
    assert to_canonical_string(result) == "!!!"


def test_canonical_error_suffix_in_expression() -> None:
    """Test canonicalization of error suffix in AND expression."""
    result = parse_query('!!! AND "foo"')
    assert to_canonical_string(result) == '!!! AND "foo"'


# --- Evaluator Tests ---


def _make_changespec(
    name: str = "test",
    description: str = "desc",
    status: str = "Drafted",
    file_path: str = "/home/user/.gai/projects/myproject/myproject.gp",
) -> ChangeSpec:
    """Helper to create a ChangeSpec for testing."""
    return ChangeSpec(
        name=name,
        description=description,
        parent=None,
        cl=None,
        status=status,
        test_targets=None,
        kickstart=None,
        file_path=file_path,
        line_number=1,
        history=None,
        hooks=None,
        comments=None,
    )


def test_evaluate_string_match_case_insensitive() -> None:
    """Test case-insensitive string matching."""
    query = parse_query('"feature"')
    cs = _make_changespec(name="my_FEATURE_test")
    assert evaluate_query(query, cs) is True


def test_evaluate_string_match_case_sensitive() -> None:
    """Test case-sensitive string matching."""
    query = parse_query('c"Feature"')
    cs = _make_changespec(name="my_Feature_test")
    assert evaluate_query(query, cs) is True

    cs2 = _make_changespec(name="my_feature_test")
    assert evaluate_query(query, cs2) is False


def test_evaluate_not_match() -> None:
    """Test NOT expression evaluation."""
    query = parse_query('!"draft"')
    # Use status="Mailed" to avoid default "Drafted" status containing "draft"
    cs1 = _make_changespec(name="my_feature", status="Mailed")
    assert evaluate_query(query, cs1) is True

    cs2 = _make_changespec(name="draft_feature", status="Mailed")
    assert evaluate_query(query, cs2) is False


def test_evaluate_and_match() -> None:
    """Test AND expression evaluation."""
    query = parse_query('"feature" AND "test"')
    cs1 = _make_changespec(name="feature", description="test code")
    assert evaluate_query(query, cs1) is True

    cs2 = _make_changespec(name="feature", description="production")
    assert evaluate_query(query, cs2) is False


def test_evaluate_or_match() -> None:
    """Test OR expression evaluation."""
    query = parse_query('"feature" OR "bugfix"')
    cs1 = _make_changespec(name="my_feature")
    assert evaluate_query(query, cs1) is True

    cs2 = _make_changespec(name="my_bugfix")
    assert evaluate_query(query, cs2) is True

    cs3 = _make_changespec(name="refactor")
    assert evaluate_query(query, cs3) is False


def test_evaluate_complex_query() -> None:
    """Test complex query evaluation."""
    query = parse_query('("feature" OR "bugfix") AND !"skip"')

    cs1 = _make_changespec(name="my_feature")
    assert evaluate_query(query, cs1) is True

    cs2 = _make_changespec(name="skip_feature")
    assert evaluate_query(query, cs2) is False

    cs3 = _make_changespec(name="refactor")
    assert evaluate_query(query, cs3) is False


def test_evaluate_matches_status() -> None:
    """Test matching against status field."""
    query = parse_query('"Drafted"')
    cs = _make_changespec(status="Drafted")
    assert evaluate_query(query, cs) is True


def test_evaluate_matches_project() -> None:
    """Test matching against project basename."""
    query = parse_query('"myproject"')
    cs = _make_changespec(file_path="/home/user/.gai/projects/myproject/myproject.gp")
    assert evaluate_query(query, cs) is True


def test_evaluate_matches_description() -> None:
    """Test matching against description."""
    query = parse_query('"important fix"')
    cs = _make_changespec(description="This is an important fix for the bug")
    assert evaluate_query(query, cs) is True


def test_evaluate_error_suffix_matches_status_with_ready_to_mail() -> None:
    """Test !!! matches ChangeSpec with READY TO MAIL in status."""
    query = parse_query("!!!")
    cs = _make_changespec(status="Drafted - (!: READY TO MAIL)")
    assert evaluate_query(query, cs) is True


def test_evaluate_error_suffix_no_match_plain_status() -> None:
    """Test !!! does not match ChangeSpec without error suffix format."""
    query = parse_query("!!!")
    cs = _make_changespec(status="Drafted")
    assert evaluate_query(query, cs) is False


def test_evaluate_error_suffix_combined_with_project() -> None:
    """Test !!! AND @myproject matches correctly."""
    query = parse_query('!!! AND "myproject"')
    cs = _make_changespec(
        status="Drafted - (!: READY TO MAIL)",
        file_path="/home/user/.gai/projects/myproject/myproject.gp",
    )
    assert evaluate_query(query, cs) is True


# --- Integration Tests ---


def test_full_pipeline_simple() -> None:
    """Test full pipeline with simple query."""
    changespecs = [
        _make_changespec(name="feature_a", status="Drafted"),
        _make_changespec(name="feature_b", status="Mailed"),
        _make_changespec(name="bugfix_c", status="Drafted"),
    ]

    query = parse_query('"feature"')
    results = [cs for cs in changespecs if evaluate_query(query, cs)]
    assert len(results) == 2
    assert results[0].name == "feature_a"
    assert results[1].name == "feature_b"


def test_full_pipeline_complex() -> None:
    """Test full pipeline with complex query."""
    changespecs = [
        _make_changespec(name="feature_a", status="Drafted"),
        _make_changespec(name="feature_b", status="Mailed"),
        _make_changespec(name="bugfix_c", status="Drafted"),
    ]

    query = parse_query('"feature" AND "Drafted"')
    results = [cs for cs in changespecs if evaluate_query(query, cs)]
    assert len(results) == 1
    assert results[0].name == "feature_a"
