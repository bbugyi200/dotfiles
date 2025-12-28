"""Tests for the query language parser and evaluator."""

import pytest
from search.changespec import ChangeSpec
from search.query import (
    AndExpr,
    NotExpr,
    OrExpr,
    QueryParseError,
    StringMatch,
    evaluate_query,
    parse_query,
)
from search.query.tokenizer import TokenizerError, TokenType, tokenize

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
