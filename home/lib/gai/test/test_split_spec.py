"""Tests for the split_spec module."""

import pytest
from split_spec import (
    SplitSpec,
    _SplitEntry,
    format_split_spec_as_markdown,
    parse_split_spec,
    topological_sort_entries,
    validate_split_spec,
)


def test_parse_split_spec_basic() -> None:
    """Test parsing a basic SplitSpec."""
    yaml_content = """
- name: feature_a
  description: First feature
- name: feature_b
  description: Second feature
"""
    spec = parse_split_spec(yaml_content)

    assert len(spec.entries) == 2
    assert spec.entries[0].name == "feature_a"
    assert spec.entries[0].description == "First feature"
    assert spec.entries[0].parent is None
    assert spec.entries[1].name == "feature_b"
    assert spec.entries[1].description == "Second feature"


def test_parse_split_spec_with_parent() -> None:
    """Test parsing a SplitSpec with parent references."""
    yaml_content = """
- name: parent_cl
  description: Parent CL
- name: child_cl
  description: Child CL
  parent: parent_cl
"""
    spec = parse_split_spec(yaml_content)

    assert len(spec.entries) == 2
    assert spec.entries[0].parent is None
    assert spec.entries[1].parent == "parent_cl"


def test_parse_split_spec_multiline_description() -> None:
    """Test parsing a SplitSpec with multiline description."""
    yaml_content = """
- name: feature
  description: |
    Line 1
    Line 2
    Line 3
"""
    spec = parse_split_spec(yaml_content)

    assert spec.entries[0].description == "Line 1\nLine 2\nLine 3"


def test_parse_split_spec_missing_name() -> None:
    """Test parsing fails when name is missing."""
    yaml_content = """
- description: No name
"""
    with pytest.raises(ValueError, match="missing required 'name' field"):
        parse_split_spec(yaml_content)


def test_parse_split_spec_invalid_yaml() -> None:
    """Test parsing fails on invalid YAML."""
    yaml_content = """
- name: [invalid
"""
    with pytest.raises(ValueError, match="Invalid YAML"):
        parse_split_spec(yaml_content)


def test_parse_split_spec_not_list() -> None:
    """Test parsing fails when root is not a list."""
    yaml_content = """
name: single_entry
description: Not a list
"""
    with pytest.raises(ValueError, match="must be a list"):
        parse_split_spec(yaml_content)


def test_validate_split_spec_valid() -> None:
    """Test validation passes with valid spec."""
    spec = SplitSpec(
        entries=[
            _SplitEntry(name="parent", description="Parent"),
            _SplitEntry(name="child", description="Child", parent="parent"),
        ]
    )

    is_valid, error = validate_split_spec(spec)
    assert is_valid is True
    assert error is None


def test_validate_split_spec_invalid_parent() -> None:
    """Test validation fails with invalid parent reference."""
    spec = SplitSpec(
        entries=[
            _SplitEntry(
                name="child",
                description="Child",
                parent="nonexistent",
            ),
        ]
    )

    is_valid, error = validate_split_spec(spec)
    assert is_valid is False
    assert error is not None
    assert "invalid parent reference" in error.lower()


def test_validate_split_spec_duplicate_names() -> None:
    """Test validation fails with duplicate entry names."""
    spec = SplitSpec(
        entries=[
            _SplitEntry(name="feature", description="First"),
            _SplitEntry(name="feature", description="Second"),
        ]
    )

    is_valid, error = validate_split_spec(spec)
    assert is_valid is False
    assert error is not None
    assert "duplicate" in error.lower()


def test_validate_split_spec_cycle() -> None:
    """Test validation fails with cycle in parent references."""
    spec = SplitSpec(
        entries=[
            _SplitEntry(name="a", description="A", parent="c"),
            _SplitEntry(name="b", description="B", parent="a"),
            _SplitEntry(name="c", description="C", parent="b"),
        ]
    )

    is_valid, error = validate_split_spec(spec)
    assert is_valid is False
    assert error is not None
    assert "cycle" in error.lower()


def test_topological_sort_no_parents() -> None:
    """Test topological sort with no parent relationships."""
    entries = [
        _SplitEntry(name="a", description="A"),
        _SplitEntry(name="b", description="B"),
        _SplitEntry(name="c", description="C"),
    ]

    sorted_entries = topological_sort_entries(entries)

    # Order should be preserved when no parents
    names = [e.name for e in sorted_entries]
    assert names == ["a", "b", "c"]


def test_topological_sort_simple_chain() -> None:
    """Test topological sort with simple parent chain."""
    entries = [
        _SplitEntry(name="child", description="C", parent="parent"),
        _SplitEntry(name="parent", description="P"),
    ]

    sorted_entries = topological_sort_entries(entries)

    names = [e.name for e in sorted_entries]
    assert names.index("parent") < names.index("child")


def test_topological_sort_deep_chain() -> None:
    """Test topological sort with deep parent chain."""
    entries = [
        _SplitEntry(name="c", description="C", parent="b"),
        _SplitEntry(name="a", description="A"),
        _SplitEntry(name="b", description="B", parent="a"),
    ]

    sorted_entries = topological_sort_entries(entries)

    names = [e.name for e in sorted_entries]
    assert names.index("a") < names.index("b")
    assert names.index("b") < names.index("c")


def test_topological_sort_multiple_roots() -> None:
    """Test topological sort with multiple root entries."""
    entries = [
        _SplitEntry(name="child_a", description="CA", parent="root_a"),
        _SplitEntry(name="root_a", description="RA"),
        _SplitEntry(name="child_b", description="CB", parent="root_b"),
        _SplitEntry(name="root_b", description="RB"),
    ]

    sorted_entries = topological_sort_entries(entries)

    names = [e.name for e in sorted_entries]
    assert names.index("root_a") < names.index("child_a")
    assert names.index("root_b") < names.index("child_b")


def test_topological_sort_external_parent() -> None:
    """Test topological sort with parent not in the spec."""
    entries = [
        _SplitEntry(name="child", description="C", parent="external_parent"),
        _SplitEntry(name="sibling", description="S"),
    ]

    # Should not raise an error, external parents are treated as roots
    sorted_entries = topological_sort_entries(entries)
    assert len(sorted_entries) == 2


def test_format_split_spec_as_markdown() -> None:
    """Test formatting a SplitSpec as markdown."""
    spec = SplitSpec(
        entries=[
            _SplitEntry(name="parent", description="Parent desc"),
            _SplitEntry(
                name="child",
                description="Child desc",
                parent="parent",
            ),
        ]
    )

    markdown = format_split_spec_as_markdown(spec)

    assert "### 1. parent" in markdown
    assert "### 2. child" in markdown
    assert "**Parent:** parent" in markdown
    assert "Parent desc" in markdown
    assert "Child desc" in markdown


def test_format_split_spec_empty_description() -> None:
    """Test formatting with empty description."""
    spec = SplitSpec(
        entries=[
            _SplitEntry(name="feature", description=""),
        ]
    )

    markdown = format_split_spec_as_markdown(spec)

    assert "(none)" in markdown
