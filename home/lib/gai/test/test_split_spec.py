"""Tests for the split_spec module."""

import pytest
from split_spec import (
    SplitEntry,
    SplitSpec,
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
  files:
    - src/a.py
    - src/b.py
- name: feature_b
  description: Second feature
  files:
    - src/c.py
"""
    spec = parse_split_spec(yaml_content)

    assert len(spec.entries) == 2
    assert spec.entries[0].name == "feature_a"
    assert spec.entries[0].description == "First feature"
    assert spec.entries[0].files == ["src/a.py", "src/b.py"]
    assert spec.entries[0].parent is None
    assert spec.entries[1].name == "feature_b"
    assert spec.entries[1].files == ["src/c.py"]


def test_parse_split_spec_with_parent() -> None:
    """Test parsing a SplitSpec with parent references."""
    yaml_content = """
- name: parent_cl
  description: Parent CL
  files:
    - src/parent.py
- name: child_cl
  description: Child CL
  parent: parent_cl
  files:
    - src/child.py
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
  files:
    - src/file.py
"""
    spec = parse_split_spec(yaml_content)

    assert spec.entries[0].description == "Line 1\nLine 2\nLine 3"


def test_parse_split_spec_missing_name() -> None:
    """Test parsing fails when name is missing."""
    yaml_content = """
- description: No name
  files:
    - src/file.py
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
files:
  - src/file.py
"""
    with pytest.raises(ValueError, match="must be a list"):
        parse_split_spec(yaml_content)


def test_parse_split_spec_empty_files() -> None:
    """Test parsing with empty files list."""
    yaml_content = """
- name: feature
  description: Empty files
  files: []
"""
    spec = parse_split_spec(yaml_content)
    assert spec.entries[0].files == []


def test_validate_split_spec_valid() -> None:
    """Test validation passes with valid spec."""
    spec = SplitSpec(
        entries=[
            SplitEntry(name="parent", description="Parent", files=["a.py"]),
            SplitEntry(
                name="child", description="Child", files=["b.py"], parent="parent"
            ),
        ]
    )

    is_valid, error = validate_split_spec(spec)
    assert is_valid is True
    assert error is None


def test_validate_split_spec_invalid_parent() -> None:
    """Test validation fails with invalid parent reference."""
    spec = SplitSpec(
        entries=[
            SplitEntry(
                name="child",
                description="Child",
                files=["a.py"],
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
            SplitEntry(name="feature", description="First", files=["a.py"]),
            SplitEntry(name="feature", description="Second", files=["b.py"]),
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
            SplitEntry(name="a", description="A", files=["a.py"], parent="c"),
            SplitEntry(name="b", description="B", files=["b.py"], parent="a"),
            SplitEntry(name="c", description="C", files=["c.py"], parent="b"),
        ]
    )

    is_valid, error = validate_split_spec(spec)
    assert is_valid is False
    assert error is not None
    assert "cycle" in error.lower()


def test_topological_sort_no_parents() -> None:
    """Test topological sort with no parent relationships."""
    entries = [
        SplitEntry(name="a", description="A", files=["a.py"]),
        SplitEntry(name="b", description="B", files=["b.py"]),
        SplitEntry(name="c", description="C", files=["c.py"]),
    ]

    sorted_entries = topological_sort_entries(entries)

    # Order should be preserved when no parents
    names = [e.name for e in sorted_entries]
    assert names == ["a", "b", "c"]


def test_topological_sort_simple_chain() -> None:
    """Test topological sort with simple parent chain."""
    entries = [
        SplitEntry(name="child", description="C", files=["c.py"], parent="parent"),
        SplitEntry(name="parent", description="P", files=["p.py"]),
    ]

    sorted_entries = topological_sort_entries(entries)

    names = [e.name for e in sorted_entries]
    assert names.index("parent") < names.index("child")


def test_topological_sort_deep_chain() -> None:
    """Test topological sort with deep parent chain."""
    entries = [
        SplitEntry(name="c", description="C", files=["c.py"], parent="b"),
        SplitEntry(name="a", description="A", files=["a.py"]),
        SplitEntry(name="b", description="B", files=["b.py"], parent="a"),
    ]

    sorted_entries = topological_sort_entries(entries)

    names = [e.name for e in sorted_entries]
    assert names.index("a") < names.index("b")
    assert names.index("b") < names.index("c")


def test_topological_sort_multiple_roots() -> None:
    """Test topological sort with multiple root entries."""
    entries = [
        SplitEntry(name="child_a", description="CA", files=["ca.py"], parent="root_a"),
        SplitEntry(name="root_a", description="RA", files=["ra.py"]),
        SplitEntry(name="child_b", description="CB", files=["cb.py"], parent="root_b"),
        SplitEntry(name="root_b", description="RB", files=["rb.py"]),
    ]

    sorted_entries = topological_sort_entries(entries)

    names = [e.name for e in sorted_entries]
    assert names.index("root_a") < names.index("child_a")
    assert names.index("root_b") < names.index("child_b")


def test_topological_sort_external_parent() -> None:
    """Test topological sort with parent not in the spec."""
    entries = [
        SplitEntry(
            name="child", description="C", files=["c.py"], parent="external_parent"
        ),
        SplitEntry(name="sibling", description="S", files=["s.py"]),
    ]

    # Should not raise an error, external parents are treated as roots
    sorted_entries = topological_sort_entries(entries)
    assert len(sorted_entries) == 2


def test_format_split_spec_as_markdown() -> None:
    """Test formatting a SplitSpec as markdown."""
    spec = SplitSpec(
        entries=[
            SplitEntry(name="parent", description="Parent desc", files=["a.py"]),
            SplitEntry(
                name="child",
                description="Child desc",
                files=["b.py", "c.py"],
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
    assert "`a.py`" in markdown
    assert "`b.py`" in markdown
    assert "`c.py`" in markdown


def test_format_split_spec_empty_description() -> None:
    """Test formatting with empty description."""
    spec = SplitSpec(
        entries=[
            SplitEntry(name="feature", description="", files=["a.py"]),
        ]
    )

    markdown = format_split_spec_as_markdown(spec)

    assert "(none)" in markdown
