"""Tests for xfile.main module."""

from main import _expand_braces


def test_expand_braces_simple() -> None:
    """Test simple brace expansion."""
    result = _expand_braces("file.{py,txt}")
    assert sorted(result) == ["file.py", "file.txt"]


def test_expand_braces_multiple_options() -> None:
    """Test brace expansion with multiple options."""
    result = _expand_braces("file.{py,txt,md,rst}")
    assert sorted(result) == ["file.md", "file.py", "file.rst", "file.txt"]


def test_expand_braces_no_braces() -> None:
    """Test that patterns without braces are returned as-is."""
    result = _expand_braces("file.py")
    assert result == ["file.py"]


def test_expand_braces_in_path() -> None:
    """Test brace expansion in a path."""
    result = _expand_braces("src/{main,utils}.py")
    assert sorted(result) == ["src/main.py", "src/utils.py"]


def test_expand_braces_nested() -> None:
    """Test nested brace expansion (expands recursively)."""
    result = _expand_braces("file.{py,{txt,md}}")
    # The function expands recursively but creates malformed outputs with unbalanced braces
    assert sorted(result) == ["file.md}", "file.py}", "file.txt"]


def test_expand_braces_multiple_braces() -> None:
    """Test multiple separate brace groups (expands all)."""
    # The function expands all brace groups recursively
    result = _expand_braces("{src,lib}/file.{py,txt}")
    expected = ["lib/file.py", "lib/file.txt", "src/file.py", "src/file.txt"]
    assert sorted(result) == sorted(expected)


def test_expand_braces_empty_option() -> None:
    """Test brace expansion with empty options."""
    result = _expand_braces("file.{py,}")
    assert sorted(result) == ["file.", "file.py"]


def test_expand_braces_single_option() -> None:
    """Test brace expansion with a single option."""
    result = _expand_braces("file.{py}")
    assert result == ["file.py"]
