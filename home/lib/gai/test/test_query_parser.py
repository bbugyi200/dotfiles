"""Tests for the query language parser (AST building)."""

import pytest
from ace.query import (
    AndExpr,
    NotExpr,
    OrExpr,
    QueryParseError,
    StringMatch,
    parse_query,
)
from ace.query.types import ERROR_SUFFIX_QUERY


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


def test_parse_bare_word() -> None:
    """Test parsing bare word."""
    result = parse_query("foobar")
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


def test_parse_double_exclamation() -> None:
    """Test parsing !! as NOT !!! (identical AST)."""
    result = parse_query("!!")
    assert isinstance(result, NotExpr)
    assert isinstance(result.operand, StringMatch)
    assert result.operand.is_error_suffix is True


def test_parse_double_exclamation_and_string() -> None:
    """Test parsing !! AND "foo"."""
    result = parse_query('!! AND "foo"')
    assert isinstance(result, AndExpr)
    assert len(result.operands) == 2
    assert isinstance(result.operands[0], NotExpr)
    assert isinstance(result.operands[0].operand, StringMatch)
    assert result.operands[0].operand.is_error_suffix is True
    assert isinstance(result.operands[1], StringMatch)
    assert result.operands[1].value == "foo"


def test_parse_double_exclamation_implicit_and() -> None:
    """Test parsing !! "foo" (implicit AND with NOT !!!)."""
    result = parse_query('!! "foo"')
    assert isinstance(result, AndExpr)
    assert len(result.operands) == 2
    assert isinstance(result.operands[0], NotExpr)
    assert isinstance(result.operands[0].operand, StringMatch)
    assert result.operands[0].operand.is_error_suffix is True
    assert isinstance(result.operands[1], StringMatch)
    assert result.operands[1].value == "foo"


def test_parse_any_special() -> None:
    """Test parsing !@$ as (!!! OR @@@ OR $$$)."""
    result = parse_query("!@$")
    assert isinstance(result, OrExpr)
    assert len(result.operands) == 3
    # Check that all three special types are present
    has_error = has_agent = has_process = False
    for op in result.operands:
        assert isinstance(op, StringMatch)
        if op.is_error_suffix:
            has_error = True
        if op.is_running_agent:
            has_agent = True
        if op.is_running_process:
            has_process = True
    assert has_error and has_agent and has_process


def test_parse_any_special_and_string() -> None:
    """Test parsing !@$ AND "foo"."""
    result = parse_query('!@$ AND "foo"')
    assert isinstance(result, AndExpr)
    assert len(result.operands) == 2
    assert isinstance(result.operands[0], OrExpr)
    assert isinstance(result.operands[1], StringMatch)
    assert result.operands[1].value == "foo"


def test_parse_any_special_implicit_and() -> None:
    """Test parsing !@$ "foo" (implicit AND)."""
    result = parse_query('!@$ "foo"')
    assert isinstance(result, AndExpr)
    assert len(result.operands) == 2
    assert isinstance(result.operands[0], OrExpr)
    assert isinstance(result.operands[1], StringMatch)
    assert result.operands[1].value == "foo"
