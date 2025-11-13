"""Tests for gai.fix_tests_workflow.agents module."""

from fix_tests_workflow.agents.validation import _parse_file_bullets_from_todos


def test_parse_file_bullets_from_todos_with_new_file() -> None:
    """Test parsing NEW file bullets."""
    content = """
+ NEW path/to/file.py
  - Add functionality
"""
    result = _parse_file_bullets_from_todos(content)
    assert len(result) == 1
    assert result[0] == ("path/to/file.py", True)


def test_parse_file_bullets_from_todos_with_existing_file() -> None:
    """Test parsing existing file bullets."""
    content = """
+ @path/to/file.py
  - Update function
"""
    result = _parse_file_bullets_from_todos(content)
    assert len(result) == 1
    assert result[0] == ("path/to/file.py", False)


def test_parse_file_bullets_from_todos_strips_google3_prefix_new() -> None:
    """Test that google3/ prefix is stripped from NEW files."""
    content = """
+ NEW google3/path/to/file.py
  - Add functionality
"""
    result = _parse_file_bullets_from_todos(content)
    assert len(result) == 1
    assert result[0] == ("path/to/file.py", True)
    # Verify google3/ was stripped
    assert not result[0][0].startswith("google3/")


def test_parse_file_bullets_from_todos_strips_google3_prefix_existing() -> None:
    """Test that google3/ prefix is stripped from existing files."""
    content = """
+ @google3/path/to/file.py
  - Update function
"""
    result = _parse_file_bullets_from_todos(content)
    assert len(result) == 1
    assert result[0] == ("path/to/file.py", False)
    # Verify google3/ was stripped
    assert not result[0][0].startswith("google3/")


def test_parse_file_bullets_from_todos_multiple_files() -> None:
    """Test parsing multiple file bullets."""
    content = """
+ @file1.py
  - Change 1
+ NEW file2.py
  - Change 2
+ @google3/file3.py
  - Change 3
"""
    result = _parse_file_bullets_from_todos(content)
    assert len(result) == 3
    assert result[0] == ("file1.py", False)
    assert result[1] == ("file2.py", True)
    assert result[2] == ("file3.py", False)


def test_parse_file_bullets_from_todos_empty_content() -> None:
    """Test parsing empty content."""
    result = _parse_file_bullets_from_todos("")
    assert len(result) == 0


def test_parse_file_bullets_from_todos_no_bullets() -> None:
    """Test parsing content with no file bullets."""
    content = """
Some text without bullets
More text
"""
    result = _parse_file_bullets_from_todos(content)
    assert len(result) == 0


def test_parse_file_bullets_from_todos_ignores_invalid_bullets() -> None:
    """Test that invalid bullet formats are ignored."""
    content = """
+ invalid_format_without_prefix
+ @valid/file.py
+ NEW another/valid.py
"""
    result = _parse_file_bullets_from_todos(content)
    # Only the valid bullets should be parsed
    assert len(result) == 2
    assert result[0] == ("valid/file.py", False)
    assert result[1] == ("another/valid.py", True)
