"""End-to-end integration tests for the query language."""

from typing import Any

from ace.query import evaluate_query, parse_query


def test_full_pipeline_simple(make_changespec: Any) -> None:
    """Test full pipeline with simple query."""
    changespecs = [
        make_changespec.create(name="feature_a", status="Drafted"),
        make_changespec.create(name="feature_b", status="Mailed"),
        make_changespec.create(name="bugfix_c", status="Drafted"),
    ]

    query = parse_query('"feature"')
    results = [cs for cs in changespecs if evaluate_query(query, cs)]
    assert len(results) == 2
    assert results[0].name == "feature_a"
    assert results[1].name == "feature_b"


def test_full_pipeline_complex(make_changespec: Any) -> None:
    """Test full pipeline with complex query."""
    changespecs = [
        make_changespec.create(name="feature_a", status="Drafted"),
        make_changespec.create(name="feature_b", status="Mailed"),
        make_changespec.create(name="bugfix_c", status="Drafted"),
    ]

    query = parse_query('"feature" AND "Drafted"')
    results = [cs for cs in changespecs if evaluate_query(query, cs)]
    assert len(results) == 1
    assert results[0].name == "feature_a"
