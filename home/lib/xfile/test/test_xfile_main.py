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
