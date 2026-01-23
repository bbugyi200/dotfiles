"""Tests for get_raw_changespec_text() function."""

import tempfile
from pathlib import Path

from ace.changespec import ChangeSpec, get_raw_changespec_text


def test_get_raw_changespec_text_basic() -> None:
    """Test extracting raw text from a basic ChangeSpec file."""
    content = """\
NAME: test_cl
DESCRIPTION: Test description
STATUS: Drafted
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        f.flush()

        cs = ChangeSpec(
            name="test_cl",
            description="Test description",
            status="Drafted",
            parent=None,
            cl=None,
            test_targets=None,
            kickstart=None,
            file_path=f.name,
            line_number=1,
        )
        result = get_raw_changespec_text(cs)
        assert result is not None
        assert "NAME: test_cl" in result
        assert "DESCRIPTION: Test description" in result
        assert "STATUS: Drafted" in result

    Path(f.name).unlink()


def test_get_raw_changespec_text_with_changespec_header_delimiter() -> None:
    """Test extraction stops at ## ChangeSpec header."""
    content = """\
## ChangeSpec
NAME: first_cl
DESCRIPTION: First CL
STATUS: Drafted

## ChangeSpec
NAME: second_cl
DESCRIPTION: Second CL
STATUS: WIP
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        f.flush()

        cs = ChangeSpec(
            name="first_cl",
            description="First CL",
            status="Drafted",
            parent=None,
            cl=None,
            test_targets=None,
            kickstart=None,
            file_path=f.name,
            line_number=2,  # Line after the header
        )
        result = get_raw_changespec_text(cs)
        assert result is not None
        assert "NAME: first_cl" in result
        assert "NAME: second_cl" not in result

    Path(f.name).unlink()


def test_get_raw_changespec_text_with_two_blank_lines_delimiter() -> None:
    """Test extraction stops at two consecutive blank lines."""
    content = """\
NAME: first_cl
DESCRIPTION: First CL
STATUS: Drafted


NAME: second_cl
DESCRIPTION: Second CL
STATUS: WIP
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        f.flush()

        cs = ChangeSpec(
            name="first_cl",
            description="First CL",
            status="Drafted",
            parent=None,
            cl=None,
            test_targets=None,
            kickstart=None,
            file_path=f.name,
            line_number=1,
        )
        result = get_raw_changespec_text(cs)
        assert result is not None
        assert "NAME: first_cl" in result
        assert "NAME: second_cl" not in result

    Path(f.name).unlink()


def test_get_raw_changespec_text_with_name_delimiter() -> None:
    """Test extraction stops at NAME: line (ChangeSpec without header)."""
    content = """\
NAME: first_cl
DESCRIPTION: First CL
STATUS: Drafted
NAME: second_cl
DESCRIPTION: Second CL
STATUS: WIP
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        f.flush()

        cs = ChangeSpec(
            name="first_cl",
            description="First CL",
            status="Drafted",
            parent=None,
            cl=None,
            test_targets=None,
            kickstart=None,
            file_path=f.name,
            line_number=1,
        )
        result = get_raw_changespec_text(cs)
        assert result is not None
        assert "NAME: first_cl" in result
        assert "NAME: second_cl" not in result

    Path(f.name).unlink()


def test_get_raw_changespec_text_eof() -> None:
    """Test extraction handles end of file properly."""
    content = """\
NAME: last_cl
DESCRIPTION: Last CL
STATUS: Drafted"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        f.flush()

        cs = ChangeSpec(
            name="last_cl",
            description="Last CL",
            status="Drafted",
            parent=None,
            cl=None,
            test_targets=None,
            kickstart=None,
            file_path=f.name,
            line_number=1,
        )
        result = get_raw_changespec_text(cs)
        assert result is not None
        assert "NAME: last_cl" in result
        assert "DESCRIPTION: Last CL" in result
        assert "STATUS: Drafted" in result

    Path(f.name).unlink()


def test_get_raw_changespec_text_file_not_found() -> None:
    """Test returns None when file doesn't exist."""
    cs = ChangeSpec(
        name="test_cl",
        description="Test description",
        status="Drafted",
        parent=None,
        cl=None,
        test_targets=None,
        kickstart=None,
        file_path="/nonexistent/path/file.gp",
        line_number=1,
    )
    result = get_raw_changespec_text(cs)
    assert result is None


def test_get_raw_changespec_text_invalid_line_number() -> None:
    """Test returns None when line number is out of range."""
    content = "NAME: test_cl\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        f.flush()

        cs = ChangeSpec(
            name="test_cl",
            description="Test description",
            status="Drafted",
            parent=None,
            cl=None,
            test_targets=None,
            kickstart=None,
            file_path=f.name,
            line_number=100,  # Way beyond file length
        )
        result = get_raw_changespec_text(cs)
        assert result is None

    Path(f.name).unlink()


def test_get_raw_changespec_text_preserves_multiline_description() -> None:
    """Test that multiline descriptions are preserved exactly."""
    content = """\
NAME: test_cl
DESCRIPTION:
  This is line 1
  This is line 2
  This is line 3
STATUS: Drafted
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        f.flush()

        cs = ChangeSpec(
            name="test_cl",
            description="This is line 1\nThis is line 2\nThis is line 3",
            status="Drafted",
            parent=None,
            cl=None,
            test_targets=None,
            kickstart=None,
            file_path=f.name,
            line_number=1,
        )
        result = get_raw_changespec_text(cs)
        assert result is not None
        # Should preserve the exact indentation format
        assert "  This is line 1" in result
        assert "  This is line 2" in result
        assert "  This is line 3" in result

    Path(f.name).unlink()


def test_get_raw_changespec_text_preserves_multiline_test_targets() -> None:
    """Test that multiline TEST TARGETS are preserved exactly."""
    content = """\
NAME: test_cl
DESCRIPTION: Test
TEST TARGETS:
  //foo:test1
  //bar:test2
  //baz:test3
STATUS: Drafted
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        f.flush()

        cs = ChangeSpec(
            name="test_cl",
            description="Test",
            status="Drafted",
            parent=None,
            cl=None,
            test_targets=["//foo:test1", "//bar:test2", "//baz:test3"],
            kickstart=None,
            file_path=f.name,
            line_number=1,
        )
        result = get_raw_changespec_text(cs)
        assert result is not None
        # Should preserve the multiline format
        assert "TEST TARGETS:" in result
        assert "  //foo:test1" in result
        assert "  //bar:test2" in result
        assert "  //baz:test3" in result

    Path(f.name).unlink()
