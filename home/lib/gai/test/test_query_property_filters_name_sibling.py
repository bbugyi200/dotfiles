"""Tests for name and sibling property filter functionality in the query language."""

from typing import Any

import pytest
from ace.query import (
    PropertyMatch,
    evaluate_query,
    parse_query,
    to_canonical_string,
)
from ace.query.tokenizer import TokenizerError, TokenType, tokenize

# --- Sibling Filter Tokenizer Tests ---


def test_tokenize_sibling_shorthand() -> None:
    """Test tokenizing ~name as sibling:name."""
    tokens = list(tokenize("~sibling_name"))
    assert len(tokens) == 2
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "sibling_name"
    assert tokens[0].property_key == "sibling"


# --- Name Filter Tokenizer Tests ---


def test_tokenize_name_shorthand() -> None:
    """Test tokenizing &myname as name:myname."""
    tokens = list(tokenize("&myname"))
    assert len(tokens) == 2
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "myname"
    assert tokens[0].property_key == "name"


def test_tokenize_name_shorthand_with_underscore() -> None:
    """Test tokenizing &my_name as name:my_name."""
    tokens = list(tokenize("&my_name"))
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "my_name"
    assert tokens[0].property_key == "name"


def test_tokenize_name_shorthand_with_hyphen() -> None:
    """Test tokenizing &my-name as name:my-name."""
    tokens = list(tokenize("&my-name"))
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "my-name"
    assert tokens[0].property_key == "name"


def test_tokenize_explicit_name_property() -> None:
    """Test tokenizing name:myname explicitly."""
    tokens = list(tokenize("name:myname"))
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "myname"
    assert tokens[0].property_key == "name"


def test_tokenize_name_shorthand_error() -> None:
    """Test that & without name raises error."""
    with pytest.raises(TokenizerError) as exc_info:
        list(tokenize("&"))
    assert "Expected name after '&'" in str(exc_info.value)


# --- Name Filter Parser Tests ---


def test_parse_name_property() -> None:
    """Test parsing name property filter."""
    result = parse_query("&myname")
    assert isinstance(result, PropertyMatch)
    assert result.key == "name"
    assert result.value == "myname"


def test_parse_explicit_name_property() -> None:
    """Test parsing explicit name syntax."""
    result = parse_query("name:myname")
    assert isinstance(result, PropertyMatch)
    assert result.key == "name"
    assert result.value == "myname"


# --- Name Filter Canonicalization Tests ---


def test_canonical_name_property() -> None:
    """Test canonicalization of name property."""
    result = parse_query("&myname")
    assert to_canonical_string(result) == "name:myname"


# --- Name Filter Evaluator Tests ---


def test_evaluate_name_match(
    make_changespec: Any,
) -> None:
    """Test name filter matches exactly."""
    query = parse_query("&my_feature")
    cs = make_changespec.create(name="my_feature")
    assert evaluate_query(query, cs) is True


def test_evaluate_name_case_insensitive(
    make_changespec: Any,
) -> None:
    """Test name matching is case-insensitive."""
    query = parse_query("name:MY_FEATURE")
    cs = make_changespec.create(name="my_feature")
    assert evaluate_query(query, cs) is True


def test_evaluate_name_no_match(
    make_changespec: Any,
) -> None:
    """Test name filter does not match different name."""
    query = parse_query("&other_feature")
    cs = make_changespec.create(name="my_feature")
    assert evaluate_query(query, cs) is False


def test_evaluate_name_partial_no_match(
    make_changespec: Any,
) -> None:
    """Test name filter requires exact match, not partial."""
    query = parse_query("&feature")
    cs = make_changespec.create(name="my_feature")
    assert evaluate_query(query, cs) is False


def test_evaluate_name_combined_with_status(
    make_changespec: Any,
) -> None:
    """Test combining name and status filters."""
    query = parse_query("&my_feature %d")
    cs1 = make_changespec.create(name="my_feature", status="Drafted")
    assert evaluate_query(query, cs1) is True

    cs2 = make_changespec.create(name="my_feature", status="Mailed")
    assert evaluate_query(query, cs2) is False

    cs3 = make_changespec.create(name="other_feature", status="Drafted")
    assert evaluate_query(query, cs3) is False


# --- Sibling Filter Tokenizer Tests ---


def test_tokenize_explicit_sibling_property() -> None:
    """Test tokenizing sibling:myname explicitly."""
    tokens = list(tokenize("sibling:myname"))
    assert len(tokens) == 2
    assert tokens[0].type == TokenType.PROPERTY
    assert tokens[0].value == "myname"
    assert tokens[0].property_key == "sibling"


# --- Sibling Filter Parser Tests ---


def test_parse_sibling_property() -> None:
    """Test parsing sibling property filter."""
    result = parse_query("sibling:myname")
    assert isinstance(result, PropertyMatch)
    assert result.key == "sibling"
    assert result.value == "myname"


# --- Sibling Filter Canonicalization Tests ---


def test_canonical_sibling_property() -> None:
    """Test canonicalization of sibling property."""
    result = parse_query("sibling:myname")
    assert to_canonical_string(result) == "sibling:myname"


# --- Sibling Filter Evaluator Tests ---


def test_evaluate_sibling_exact_match(
    make_changespec: Any,
) -> None:
    """Test sibling filter matches exact name."""
    query = parse_query("sibling:foo")
    cs = make_changespec.create(name="foo")
    assert evaluate_query(query, cs) is True


def test_evaluate_sibling_matches_with_suffix(
    make_changespec: Any,
) -> None:
    """Test sibling:foo matches foo__2."""
    query = parse_query("sibling:foo")
    cs = make_changespec.create(name="foo__2")
    assert evaluate_query(query, cs) is True


def test_evaluate_sibling_matches_base_to_suffix(
    make_changespec: Any,
) -> None:
    """Test sibling:foo__3 matches foo (base name)."""
    query = parse_query("sibling:foo__3")
    cs = make_changespec.create(name="foo")
    assert evaluate_query(query, cs) is True


def test_evaluate_sibling_matches_suffix_to_suffix(
    make_changespec: Any,
) -> None:
    """Test sibling:foo__1 matches foo__5."""
    query = parse_query("sibling:foo__1")
    cs = make_changespec.create(name="foo__5")
    assert evaluate_query(query, cs) is True


def test_evaluate_sibling_case_insensitive(
    make_changespec: Any,
) -> None:
    """Test sibling matching is case-insensitive."""
    query = parse_query("sibling:FOO")
    cs = make_changespec.create(name="foo__2")
    assert evaluate_query(query, cs) is True


def test_evaluate_sibling_no_match_different_base(
    make_changespec: Any,
) -> None:
    """Test sibling filter doesn't match different base name."""
    query = parse_query("sibling:foo")
    cs = make_changespec.create(name="bar")
    assert evaluate_query(query, cs) is False

    cs2 = make_changespec.create(name="foobar")
    assert evaluate_query(query, cs2) is False

    cs3 = make_changespec.create(name="bar__2")
    assert evaluate_query(query, cs3) is False


def test_evaluate_sibling_combined_with_status(
    make_changespec: Any,
) -> None:
    """Test combining sibling and status filters."""
    query = parse_query("sibling:feature %d")
    cs1 = make_changespec.create(name="feature", status="Drafted")
    assert evaluate_query(query, cs1) is True

    cs2 = make_changespec.create(name="feature__2", status="Drafted")
    assert evaluate_query(query, cs2) is True

    cs3 = make_changespec.create(name="feature__3", status="Mailed")
    assert evaluate_query(query, cs3) is False

    cs4 = make_changespec.create(name="other_feature", status="Drafted")
    assert evaluate_query(query, cs4) is False
