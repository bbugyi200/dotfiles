"""Tests for xfile.main module."""

import os
import sys
import tempfile
from pathlib import Path

# Add parent directory to path to import main module
sys.path.insert(0, str(Path(__file__).parent.parent))

import main  # type: ignore[import-not-found]


def test_main_list_xfiles() -> None:
    """Test listing xfiles with --list flag."""
    result: int = main.main(["--list"])  # type: ignore[call-arg]
    assert result == 0


def test_main_missing_xfiles_arg() -> None:
    """Test that main processes STDIN when no xfiles specified."""
    # Create a temporary directory with test files
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test content")

        # Create an xfiles directory with an xfile
        xfiles_dir = Path(tmpdir) / "xfiles"
        xfiles_dir.mkdir()
        test_xfile = xfiles_dir / "myxfile.txt"
        test_xfile.write_text(str(test_file))

        # Change to temp directory
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            # Mock stdin with content containing x::myxfile pattern
            import io

            original_stdin = sys.stdin
            sys.stdin = io.StringIO("Before x::myxfile After")

            # Capture stdout
            from io import StringIO

            captured_output = StringIO()
            original_stdout = sys.stdout
            sys.stdout = captured_output

            try:
                result: int = main.main([])  # type: ignore[call-arg]
                assert result == 0

                # Check that the pattern was replaced
                output = captured_output.getvalue()
                assert "Before" in output
                assert "After" in output
                assert "### Context Files" in output
                assert "@" in output  # Should have @ prefix
            finally:
                sys.stdin = original_stdin
                sys.stdout = original_stdout
        finally:
            os.chdir(old_cwd)


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
        path, absolute=False, cwd=cwd
    )
    assert result == "file.txt"


def test_format_output_path_absolute() -> None:
    """Test formatting path as absolute."""
    cwd: Path = Path("/home/user/project")
    path: Path = Path("/home/user/project/file.txt")
    result: str = main._format_output_path(  # type: ignore[attr-defined]
        path, absolute=True, cwd=cwd
    )
    assert result == "/home/user/project/file.txt"


def test_format_output_path_outside_cwd() -> None:
    """Test formatting path outside cwd returns absolute path."""
    cwd: Path = Path("/home/user/project")
    path: Path = Path("/etc/config.txt")
    result: str = main._format_output_path(  # type: ignore[attr-defined]
        path, absolute=False, cwd=cwd
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


def test_parse_xfile_metadata_with_header() -> None:
    """Test parsing xfile with custom header."""
    with tempfile.TemporaryDirectory() as tmpdir:
        xfile_path = Path(tmpdir) / "test.txt"
        xfile_path.write_text("# My Custom Files\n\nfile1.txt\nfile2.txt")

        header, descriptions = main._parse_xfile_metadata(xfile_path)  # type: ignore[attr-defined]

        assert header == "My Custom Files"
        assert descriptions == {}


def test_parse_xfile_metadata_without_header() -> None:
    """Test parsing xfile without header uses default."""
    with tempfile.TemporaryDirectory() as tmpdir:
        xfile_path = Path(tmpdir) / "test.txt"
        xfile_path.write_text("file1.txt\nfile2.txt")

        header, descriptions = main._parse_xfile_metadata(xfile_path)  # type: ignore[attr-defined]

        assert header == "Context Files"
        assert descriptions == {}


def test_parse_xfile_metadata_with_descriptions() -> None:
    """Test parsing xfile with file descriptions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        xfile_path = Path(tmpdir) / "test.txt"
        content = """# This is a config file
config.txt

# These are data files
data1.txt
data2.txt"""
        xfile_path.write_text(content)

        header, descriptions = main._parse_xfile_metadata(xfile_path)  # type: ignore[attr-defined]

        assert header == "Context Files"
        assert descriptions["config.txt"] == "This is a config file"
        assert descriptions["data1.txt"] == "These are data files"
        assert descriptions["data2.txt"] == "These are data files"


def test_format_xfile_with_custom_header() -> None:
    """Test formatting xfile with custom header."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test content")

        # Create xfile with custom header (use relative path)
        xfiles_dir = Path(tmpdir) / "xfiles"
        xfiles_dir.mkdir()
        xfile_path = xfiles_dir / "myxfile.txt"
        xfile_path.write_text("# My Special Files\n\ntest.txt")

        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            result = main._format_xfile_with_at_prefix("myxfile", False)  # type: ignore[attr-defined]

            assert "### My Special Files" in result
            assert "@test.txt" in result
        finally:
            os.chdir(old_cwd)


def test_format_xfile_with_single_file_description() -> None:
    """Test formatting xfile with single file description."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file
        test_file = Path(tmpdir) / "config.txt"
        test_file.write_text("config content")

        # Create xfile with description (use relative path)
        xfiles_dir = Path(tmpdir) / "xfiles"
        xfiles_dir.mkdir()
        xfile_path = xfiles_dir / "myxfile.txt"
        xfile_path.write_text("# This is a configuration file\nconfig.txt")

        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            result = main._format_xfile_with_at_prefix("myxfile", False)  # type: ignore[attr-defined]

            assert "### Context Files" in result
            assert "@config.txt - This is a configuration file" in result
        finally:
            os.chdir(old_cwd)


def test_format_xfile_with_group_description() -> None:
    """Test formatting xfile with group description for multiple files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        file1 = Path(tmpdir) / "data1.txt"
        file1.write_text("data1")
        file2 = Path(tmpdir) / "data2.txt"
        file2.write_text("data2")

        # Create xfile with group description (use relative paths)
        xfiles_dir = Path(tmpdir) / "xfiles"
        xfiles_dir.mkdir()
        xfile_path = xfiles_dir / "myxfile.txt"
        xfile_path.write_text("# These are data files\ndata1.txt\ndata2.txt")

        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            result = main._format_xfile_with_at_prefix("myxfile", False)  # type: ignore[attr-defined]

            assert "### Context Files" in result
            assert "+ These are data files:" in result
            assert "  - @data1.txt" in result
            assert "  - @data2.txt" in result
        finally:
            os.chdir(old_cwd)
