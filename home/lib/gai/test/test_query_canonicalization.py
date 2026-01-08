"""Tests for query canonicalization (converting parsed queries to canonical string form)."""

from ace.query import parse_query, to_canonical_string


def test_canonical_simple_string() -> None:
    """Test canonicalization of simple string."""
    result = parse_query('"foo"')
    assert to_canonical_string(result) == '"foo"'


def test_canonical_case_sensitive_string() -> None:
    """Test canonicalization of case-sensitive string."""
    result = parse_query('c"Foo"')
    assert to_canonical_string(result) == 'c"Foo"'


def test_canonical_bare_word() -> None:
    """Test canonicalization of bare word."""
    result = parse_query("foo")
    assert to_canonical_string(result) == '"foo"'


def test_canonical_not() -> None:
    """Test canonicalization of NOT expression."""
    result = parse_query('!"foo"')
    assert to_canonical_string(result) == 'NOT "foo"'


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
    result = parse_query('foo bar ("baz" or "pig")')
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


def test_canonical_double_exclamation() -> None:
    """Test canonicalization of !! becomes NOT !!!."""
    result = parse_query("!!")
    assert to_canonical_string(result) == "NOT !!!"


def test_canonical_double_exclamation_in_expression() -> None:
    """Test canonicalization of !! in AND expression."""
    result = parse_query('!! AND "foo"')
    assert to_canonical_string(result) == 'NOT !!! AND "foo"'


def test_canonical_not_keyword_with_error_suffix() -> None:
    """Test canonicalization of NOT keyword followed by error suffix.

    This is a regression test for a bug where 'NOT !!!' was incorrectly
    transformed to '"NOT" !!!' because the NOT keyword wasn't being
    recognized by the tokenizer.
    """
    result = parse_query("NOT !!!")
    assert to_canonical_string(result) == "NOT !!!"


def test_canonical_not_keyword_with_string() -> None:
    """Test canonicalization of NOT keyword followed by a string."""
    result = parse_query('NOT "foo"')
    assert to_canonical_string(result) == 'NOT "foo"'


def test_canonical_not_keyword_case_insensitive() -> None:
    """Test canonicalization of NOT keyword is case-insensitive."""
    result = parse_query('not "foo"')
    assert to_canonical_string(result) == 'NOT "foo"'


def test_canonical_any_special() -> None:
    """Test canonicalization of !@$ shorthand."""
    result = parse_query("!@$")
    assert to_canonical_string(result) == "!@$"


def test_canonical_any_special_in_expression() -> None:
    """Test canonicalization of !@$ in AND expression."""
    result = parse_query('!@$ AND "foo"')
    assert to_canonical_string(result) == '!@$ AND "foo"'


def test_canonical_any_special_implicit_and() -> None:
    """Test canonicalization of !@$ with implicit AND."""
    result = parse_query('!@$ "foo"')
    assert to_canonical_string(result) == '!@$ AND "foo"'
