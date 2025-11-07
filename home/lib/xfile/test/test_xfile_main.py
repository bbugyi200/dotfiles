"""Tests for xfile.main module."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path to import main module
sys.path.insert(0, str(Path(__file__).parent.parent))

import main  # type: ignore[import-not-found]


def test_main_list_xfiles() -> None:
    """Test listing xfiles with --list flag."""
    result: int = main.main(["--list"])  # type: ignore[call-arg]
    assert result == 0


def test_main_missing_xfiles_arg() -> None:
    """Test that main returns error when no xfiles specified."""
    # Should fail when no xfiles provided
    with pytest.raises(SystemExit) as exc_info:
        main.main([])  # type: ignore[call-arg]
    assert exc_info.value.code != 0


def test_main_nonexistent_xfile() -> None:
    """Test that main returns error for nonexistent xfile."""
    result: int = main.main(["nonexistent_xfile_that_does_not_exist_12345"])  # type: ignore[call-arg]
    assert result == 1


def test_main_with_glob_pattern_in_xfile() -> None:
    """Test processing an xfile that contains glob patterns."""
    # Create a temporary directory with test files
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        test_files = ["test1.py", "test2.py", "test.txt"]
        for filename in test_files:
            Path(tmpdir, filename).touch()

        # Create an xfiles directory with an xfile
        xfiles_dir = Path(tmpdir) / "xfiles"
        xfiles_dir.mkdir()
        test_xfile = xfiles_dir / "test.txt"
        test_xfile.write_text("*.py\n")

        # Change to temp directory and run main
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            result: int = main.main(["test"])  # type: ignore[call-arg]
            assert result == 0
        finally:
            os.chdir(old_cwd)


def test_expand_braces_no_braces() -> None:
    """Test that patterns without braces are returned unchanged."""
    result: list[str] = main._expand_braces("file.txt")  # type: ignore[attr-defined]
    assert result == ["file.txt"]


def test_expand_braces_simple() -> None:
    """Test simple brace expansion."""
    result: list[str] = main._expand_braces("file.{py,txt}")  # type: ignore[attr-defined]
    assert result == ["file.py", "file.txt"]


def test_expand_braces_multiple_options() -> None:
    """Test brace expansion with multiple options."""
    result: list[str] = main._expand_braces("test.{a,b,c}")  # type: ignore[attr-defined]
    assert result == ["test.a", "test.b", "test.c"]


def test_format_output_path_relative() -> None:
    """Test formatting path as relative."""
    cwd: Path = Path("/home/user/project")
    path: Path = Path("/home/user/project/file.txt")
    result: str = main._format_output_path(  # type: ignore[attr-defined]
        path, absolute=False, prefix_at=False, cwd=cwd
    )
    assert result == "file.txt"


def test_format_output_path_absolute() -> None:
    """Test formatting path as absolute."""
    cwd: Path = Path("/home/user/project")
    path: Path = Path("/home/user/project/file.txt")
    result: str = main._format_output_path(  # type: ignore[attr-defined]
        path, absolute=True, prefix_at=False, cwd=cwd
    )
    assert result == "/home/user/project/file.txt"


def test_format_output_path_with_prefix() -> None:
    """Test formatting path with @ prefix."""
    cwd: Path = Path("/home/user/project")
    path: Path = Path("/home/user/project/file.txt")
    result: str = main._format_output_path(  # type: ignore[attr-defined]
        path, absolute=False, prefix_at=True, cwd=cwd
    )
    assert result == "@file.txt"


def test_format_output_path_outside_cwd() -> None:
    """Test formatting path outside cwd returns absolute path."""
    cwd: Path = Path("/home/user/project")
    path: Path = Path("/etc/config.txt")
    result: str = main._format_output_path(  # type: ignore[attr-defined]
        path, absolute=False, prefix_at=False, cwd=cwd
    )
    assert result == "/etc/config.txt"


def test_make_relative_to_home_inside_home() -> None:
    """Test converting path inside home directory."""
    home: Path = Path.home()
    path: Path = home / "Documents" / "file.txt"
    result: Path = main._make_relative_to_home(path)  # type: ignore[attr-defined]
    assert result == Path("~") / "Documents" / "file.txt"


def test_make_relative_to_home_outside_home() -> None:
    """Test converting path outside home directory."""
    path: Path = Path("/etc/config.txt")
    result: Path = main._make_relative_to_home(path)  # type: ignore[attr-defined]
    assert result == path


def test_get_global_xfiles_dir() -> None:
    """Test getting global xfiles directory path."""
    result: Path = main._get_global_xfiles_dir()  # type: ignore[attr-defined]
    expected: Path = Path.home() / ".local/share/nvim/codecompanion/user/xfiles"
    assert result == expected


def test_get_local_xfiles_dir() -> None:
    """Test getting local xfiles directory path."""
    result: Path = main._get_local_xfiles_dir()  # type: ignore[attr-defined]
    expected: Path = Path.cwd() / "xfiles"
    assert result == expected
