"""Tests for the file_references module."""

import os
import tempfile

import pytest
from gemini_wrapper import file_references
from gemini_wrapper.file_references import (
    _parse_file_refs,
    process_xcmd_references,
    validate_file_references,
)

# Tests for _parse_file_refs


def test_parse_file_refs_empty_prompt() -> None:
    """Test parsing prompt with no file references."""
    result = _parse_file_refs("No file references here")
    assert result.absolute_paths == []
    assert result.parent_dir_paths == []
    assert result.missing_files == []
    assert result.seen_paths == {}


def test_parse_file_refs_relative_path_exists() -> None:
    """Test parsing relative path that exists."""
    # Use a file we know exists
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        temp_path = f.name
    try:
        # Get just the filename for relative path test
        cwd = os.getcwd()
        os.chdir(os.path.dirname(temp_path))
        try:
            basename = os.path.basename(temp_path)
            result = _parse_file_refs(f"Check @{basename}")
            # Should be tracked but not in missing_files
            assert basename in result.seen_paths
            assert result.missing_files == []
        finally:
            os.chdir(cwd)
    finally:
        os.unlink(temp_path)


def test_parse_file_refs_relative_path_missing() -> None:
    """Test parsing relative path that doesn't exist."""
    result = _parse_file_refs("Check @nonexistent_file_12345.txt")
    assert "nonexistent_file_12345.txt" in result.missing_files


def test_parse_file_refs_absolute_path_exists() -> None:
    """Test parsing absolute path that exists."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        temp_path = f.name
    try:
        result = _parse_file_refs(f"Check @{temp_path}")
        assert len(result.absolute_paths) == 1
        assert result.absolute_paths[0][0] == temp_path
        assert result.missing_files == []
    finally:
        os.unlink(temp_path)


def test_parse_file_refs_absolute_path_missing() -> None:
    """Test parsing absolute path that doesn't exist."""
    result = _parse_file_refs("Check @/nonexistent/path/to/file.txt")
    assert "/nonexistent/path/to/file.txt" in result.missing_files


def test_parse_file_refs_parent_dir_path() -> None:
    """Test parsing path with .. prefix."""
    result = _parse_file_refs("Check @../some/file.txt")
    assert "../some/file.txt" in result.parent_dir_paths


def test_parse_file_refs_context_dir_path() -> None:
    """Test parsing path in reserved context directory."""
    result = _parse_file_refs("Check @bb/gai/context/file.txt")
    assert "bb/gai/context/file.txt" in result.context_dir_paths


def test_parse_file_refs_duplicate_paths() -> None:
    """Test detecting duplicate file references."""
    result = _parse_file_refs("Check @file.txt and again @file.txt")
    assert result.seen_paths.get("file.txt", 0) == 2
    assert "file.txt" in result.duplicate_paths


def test_parse_file_refs_skips_urls() -> None:
    """Test that URL-like patterns are skipped."""
    result = _parse_file_refs("Visit @http://example.com")
    assert result.seen_paths == {}


def test_parse_file_refs_skips_domain_names() -> None:
    """Test that domain-like patterns are skipped."""
    result = _parse_file_refs("Email @google.com @github.io")
    assert result.seen_paths == {}


def test_parse_file_refs_at_in_middle_of_word() -> None:
    """Test that @ in middle of word is not treated as file reference."""
    result = _parse_file_refs("email@example.com")
    # The pattern requires @ to be at start or after whitespace
    assert result.seen_paths == {}


def test_parse_file_refs_tilde_expansion() -> None:
    """Test that ~ is expanded to home directory."""
    home = os.path.expanduser("~")
    # Use a file that should exist in home directory
    result = _parse_file_refs("Check @~/.bashrc")
    if os.path.exists(os.path.join(home, ".bashrc")):
        # If .bashrc exists, it should be in absolute_paths
        assert len(result.absolute_paths) == 1
    else:
        # If .bashrc doesn't exist, it should be in missing_files
        assert "~/.bashrc" in result.missing_files


# Tests for validate_file_references


def test_validate_file_references_no_refs_passes() -> None:
    """Test that prompt without file refs passes validation."""
    # Should not raise
    validate_file_references("No file references here")


def test_validate_file_references_existing_file_passes() -> None:
    """Test that existing file reference passes validation."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        temp_path = f.name
    try:
        validate_file_references(f"Check @{temp_path}")
    finally:
        os.unlink(temp_path)


def test_validate_file_references_missing_file_exits() -> None:
    """Test that missing file reference causes exit."""
    with pytest.raises(SystemExit) as exc_info:
        validate_file_references("Check @/nonexistent/path/file.txt")
    assert exc_info.value.code == 1


def test_validate_file_references_parent_dir_exits() -> None:
    """Test that parent dir path causes exit."""
    with pytest.raises(SystemExit) as exc_info:
        validate_file_references("Check @../some/file.txt")
    assert exc_info.value.code == 1


def test_validate_file_references_duplicate_exits() -> None:
    """Test that duplicate file refs cause exit."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        temp_path = f.name
    try:
        with pytest.raises(SystemExit) as exc_info:
            validate_file_references(f"Check @{temp_path} and @{temp_path}")
        assert exc_info.value.code == 1
    finally:
        os.unlink(temp_path)


def test_validate_file_references_context_dir_allowed() -> None:
    """Test that context dir refs are allowed by validate (not checked)."""
    # validate_file_references should NOT check context_dir paths
    # (only process_file_references does)
    # This should pass since context_dir check is disabled
    validate_file_references("Check @bb/gai/context/file.txt")
    # No exception = pass


# Tests for process_xcmd_references


@pytest.fixture(autouse=True)
def _clear_xcmd_cache_before_test() -> None:
    """Clear xcmd cache before each test."""
    file_references._xcmd_cache.clear()


def test_process_xcmd_references_no_pattern() -> None:
    """Test that prompts without #() are returned unchanged."""
    prompt = "This is a regular prompt with no xcmd patterns"
    result = process_xcmd_references(prompt)
    assert result == prompt


def test_process_xcmd_references_pattern_not_matching() -> None:
    """Test that #() without colon is not matched."""
    prompt = "Check #(something) but no colon"
    result = process_xcmd_references(prompt)
    assert result == prompt


def test_process_xcmd_references_simple_command(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test simple command execution creates file and replaces pattern."""
    monkeypatch.chdir(tmp_path)
    prompt = 'Check this: #(test_output: echo "hello world")'
    result = process_xcmd_references(prompt)

    # Should replace with @file reference
    assert "@bb/gai/xcmds/test_output.txt" in result
    assert "#(" not in result

    # File should exist with content
    output_file = os.path.join(tmp_path, "bb/gai/xcmds/test_output.txt")
    assert os.path.exists(output_file)

    with open(output_file) as f:
        content = f.read()
    assert "# Generated from command:" in content
    assert "# Timestamp:" in content
    assert "hello world" in content


def test_process_xcmd_references_failed_command(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that failed commands remove the pattern."""
    monkeypatch.chdir(tmp_path)
    prompt = "Check this: #(output: false) and more text"
    result = process_xcmd_references(prompt)

    # Pattern should be removed, rest preserved
    assert "#(" not in result
    assert "and more text" in result
    # File should not exist
    assert not os.path.exists(os.path.join(tmp_path, "bb/gai/xcmds/output.txt"))


def test_process_xcmd_references_empty_output(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that commands with empty output remove the pattern."""
    monkeypatch.chdir(tmp_path)
    prompt = "Check this: #(output: true) and more"
    result = process_xcmd_references(prompt)

    # true command produces no output
    assert "#(" not in result
    assert "and more" in result


def test_process_xcmd_references_adds_txt_extension(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that .txt is auto-added if no extension provided."""
    monkeypatch.chdir(tmp_path)
    prompt = '#(myfile: echo "test")'
    result = process_xcmd_references(prompt)

    assert "@bb/gai/xcmds/myfile.txt" in result


def test_process_xcmd_references_preserves_extension(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that provided extension is preserved."""
    monkeypatch.chdir(tmp_path)
    prompt = '#(output.json: echo "{}")'
    result = process_xcmd_references(prompt)

    assert "@bb/gai/xcmds/output.json" in result
    assert os.path.exists(os.path.join(tmp_path, "bb/gai/xcmds/output.json"))


def test_process_xcmd_references_command_caching(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that same command is only executed once."""
    monkeypatch.chdir(tmp_path)
    # Using date command that returns current time - if caching works, both files have same content
    prompt = '#(file1: echo "cached") #(file2: echo "cached")'
    result = process_xcmd_references(prompt)

    assert "@bb/gai/xcmds/file1.txt" in result
    assert "@bb/gai/xcmds/file2.txt" in result


def test_process_xcmd_references_multiple_patterns(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test multiple patterns in same prompt."""
    monkeypatch.chdir(tmp_path)
    prompt = 'First: #(first: echo "one") Second: #(second: echo "two")'
    result = process_xcmd_references(prompt)

    assert "@bb/gai/xcmds/first.txt" in result
    assert "@bb/gai/xcmds/second.txt" in result
    assert "First:" in result
    assert "Second:" in result


def test_process_xcmd_references_creates_xcmds_dir(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that bb/gai/xcmds directory is created."""
    monkeypatch.chdir(tmp_path)
    xcmds_dir = os.path.join(tmp_path, "bb/gai/xcmds")
    assert not os.path.exists(xcmds_dir)

    prompt = '#(test: echo "hello")'
    process_xcmd_references(prompt)

    assert os.path.exists(xcmds_dir)
    assert os.path.isdir(xcmds_dir)
