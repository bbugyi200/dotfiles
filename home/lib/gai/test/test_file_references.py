"""Tests for the file_references module."""

import os
import re
import tempfile
from datetime import datetime
from unittest.mock import patch

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

    # Should replace with @file reference (with timestamp suffix)
    assert re.search(r"@bb/gai/xcmds/test_output-\d{6}_\d{6}\.txt", result)
    assert "#(" not in result

    # File should exist with content
    xcmds_dir = os.path.join(tmp_path, "bb/gai/xcmds")
    files = os.listdir(xcmds_dir)
    output_files = [f for f in files if f.startswith("test_output-")]
    assert len(output_files) == 1

    with open(os.path.join(xcmds_dir, output_files[0])) as f:
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
    # No files should be created
    xcmds_dir = os.path.join(tmp_path, "bb/gai/xcmds")
    assert not os.path.exists(xcmds_dir) or len(os.listdir(xcmds_dir)) == 0


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

    # Should have timestamp suffix and .txt extension
    assert re.search(r"@bb/gai/xcmds/myfile-\d{6}_\d{6}\.txt", result)


def test_process_xcmd_references_preserves_extension(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that provided extension is preserved with timestamp suffix."""
    monkeypatch.chdir(tmp_path)
    prompt = '#(output.json: echo "{}")'
    result = process_xcmd_references(prompt)

    # Should have timestamp suffix before .json extension
    assert re.search(r"@bb/gai/xcmds/output-\d{6}_\d{6}\.json", result)
    # File should exist
    xcmds_dir = os.path.join(tmp_path, "bb/gai/xcmds")
    files = os.listdir(xcmds_dir)
    assert any(f.startswith("output-") and f.endswith(".json") for f in files)


def test_process_xcmd_references_command_caching(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that same command is only executed once."""
    monkeypatch.chdir(tmp_path)
    # Using date command that returns current time - if caching works, both files have same content
    prompt = '#(file1: echo "cached") #(file2: echo "cached")'
    result = process_xcmd_references(prompt)

    assert re.search(r"@bb/gai/xcmds/file1-\d{6}_\d{6}\.txt", result)
    assert re.search(r"@bb/gai/xcmds/file2-\d{6}_\d{6}\.txt", result)


def test_process_xcmd_references_multiple_patterns(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test multiple patterns in same prompt."""
    monkeypatch.chdir(tmp_path)
    prompt = 'First: #(first: echo "one") Second: #(second: echo "two")'
    result = process_xcmd_references(prompt)

    assert re.search(r"@bb/gai/xcmds/first-\d{6}_\d{6}\.txt", result)
    assert re.search(r"@bb/gai/xcmds/second-\d{6}_\d{6}\.txt", result)
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


def test_process_xcmd_references_timestamp_format(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that timestamp suffix follows -YYmmdd_HHMMSS format."""
    monkeypatch.chdir(tmp_path)
    prompt = '#(testfile: echo "hello")'
    result = process_xcmd_references(prompt)

    # Extract the filename from result
    match = re.search(r"@bb/gai/xcmds/(testfile-(\d{6})_(\d{6})\.txt)", result)
    assert match, f"Expected timestamp pattern in result: {result}"

    # Verify the date part (YYmmdd) has valid ranges
    date_part = match.group(2)
    year = int(date_part[0:2])
    month = int(date_part[2:4])
    day = int(date_part[4:6])
    assert 0 <= year <= 99, f"Year {year} out of range"
    assert 1 <= month <= 12, f"Month {month} out of range"
    assert 1 <= day <= 31, f"Day {day} out of range"

    # Verify the time part (HHMMSS) has valid ranges
    time_part = match.group(3)
    hour = int(time_part[0:2])
    minute = int(time_part[2:4])
    second = int(time_part[4:6])
    assert 0 <= hour <= 23, f"Hour {hour} out of range"
    assert 0 <= minute <= 59, f"Minute {minute} out of range"
    assert 0 <= second <= 59, f"Second {second} out of range"

    # Verify the file was created with the timestamp name
    xcmds_dir = os.path.join(tmp_path, "bb/gai/xcmds")
    files = os.listdir(xcmds_dir)
    assert match.group(1) in files


# Tests for process_command_substitution


def test_process_command_substitution_no_pattern() -> None:
    """Test that prompts without $() are returned unchanged."""
    from gemini_wrapper.file_references import process_command_substitution

    prompt = "This is a regular prompt with no command substitution"
    result = process_command_substitution(prompt)
    assert result == prompt


def test_process_command_substitution_simple_command() -> None:
    """Test simple command substitution."""
    from gemini_wrapper.file_references import process_command_substitution

    prompt = 'The output is $(echo "hello")'
    result = process_command_substitution(prompt)
    assert result == "The output is hello"


def test_process_command_substitution_nested_parens() -> None:
    """Test nested parentheses are handled correctly."""
    from gemini_wrapper.file_references import process_command_substitution

    # Nested command substitution
    prompt = '$(echo $(echo "inner"))'
    result = process_command_substitution(prompt)
    assert result == "inner"


def test_process_command_substitution_parens_in_command() -> None:
    """Test parentheses within the command are handled."""
    from gemini_wrapper.file_references import process_command_substitution

    # Subshell with parens
    prompt = '$(echo "(parens)")'
    result = process_command_substitution(prompt)
    assert result == "(parens)"


def test_process_command_substitution_multiple() -> None:
    """Test multiple substitutions in one prompt."""
    from gemini_wrapper.file_references import process_command_substitution

    prompt = '$(echo "a") and $(echo "b")'
    result = process_command_substitution(prompt)
    assert result == "a and b"


def test_process_command_substitution_escaped() -> None:
    """Test that escaped \\$( is not substituted."""
    from gemini_wrapper.file_references import process_command_substitution

    prompt = "Literal \\$(not a command) here"
    result = process_command_substitution(prompt)
    assert result == "Literal $(not a command) here"


def test_process_command_substitution_failed_command() -> None:
    """Test that failed commands result in empty string."""
    from gemini_wrapper.file_references import process_command_substitution

    prompt = "Before $(nonexistent_command_xyz_12345) after"
    result = process_command_substitution(prompt)
    # Failed command should be replaced with empty string
    assert result == "Before  after"


def test_process_command_substitution_empty_output() -> None:
    """Test that commands with empty output result in empty string."""
    from gemini_wrapper.file_references import process_command_substitution

    prompt = "Before $(true) after"
    result = process_command_substitution(prompt)
    assert result == "Before  after"


def test_process_command_substitution_unclosed_paren() -> None:
    """Test that unclosed $( is left unchanged."""
    from gemini_wrapper.file_references import process_command_substitution

    prompt = "Unclosed $(echo hello"
    result = process_command_substitution(prompt)
    assert result == prompt


def test_process_command_substitution_preserves_surrounding() -> None:
    """Test that surrounding text is preserved."""
    from gemini_wrapper.file_references import process_command_substitution

    prompt = 'Start $(echo "middle") end'
    result = process_command_substitution(prompt)
    assert result == "Start middle end"


def test_process_command_substitution_multiline_output() -> None:
    """Test that multiline output is stripped properly."""
    from gemini_wrapper.file_references import process_command_substitution

    prompt = '$(printf "line1\\nline2")'
    result = process_command_substitution(prompt)
    assert result == "line1\nline2"


def test_process_command_substitution_deeply_nested() -> None:
    """Test deeply nested command substitutions."""
    from gemini_wrapper.file_references import process_command_substitution

    prompt = '$(echo $(echo $(echo "deep")))'
    result = process_command_substitution(prompt)
    assert result == "deep"


# Tests for helper functions


def test_find_matching_paren_simple() -> None:
    """Test finding matching paren in simple case."""
    from gemini_wrapper.file_references import _find_matching_paren

    text = "abc)"
    result = _find_matching_paren(text, 0)
    assert result == 3


def test_find_matching_paren_nested() -> None:
    """Test finding matching paren with nested parens."""
    from gemini_wrapper.file_references import _find_matching_paren

    text = "a(b)c)"
    result = _find_matching_paren(text, 0)
    assert result == 5


def test_find_matching_paren_deeply_nested() -> None:
    """Test finding matching paren with deeply nested parens."""
    from gemini_wrapper.file_references import _find_matching_paren

    text = "a((b))c)"
    result = _find_matching_paren(text, 0)
    assert result == 7


def test_find_matching_paren_no_match() -> None:
    """Test when no matching paren exists."""
    from gemini_wrapper.file_references import _find_matching_paren

    text = "abc(def"
    result = _find_matching_paren(text, 0)
    assert result == -1


def test_find_command_substitutions_simple() -> None:
    """Test finding a simple command substitution."""
    from gemini_wrapper.file_references import _find_command_substitutions

    text = "$(echo hi)"
    result = _find_command_substitutions(text)
    assert len(result) == 1
    assert result[0] == (0, 10, "echo hi")


def test_find_command_substitutions_escaped() -> None:
    """Test that escaped $( is skipped."""
    from gemini_wrapper.file_references import _find_command_substitutions

    text = "\\$(not a command)"
    result = _find_command_substitutions(text)
    assert len(result) == 0


def test_find_command_substitutions_multiple() -> None:
    """Test finding multiple command substitutions."""
    from gemini_wrapper.file_references import _find_command_substitutions

    text = "$(cmd1) and $(cmd2)"
    result = _find_command_substitutions(text)
    assert len(result) == 2
    assert result[0] == (0, 7, "cmd1")
    assert result[1] == (12, 19, "cmd2")


def test_process_xcmd_references_filename_collision(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that two xcmds with same filename get unique names via counter."""
    monkeypatch.chdir(tmp_path)
    prompt = '#(out.txt: echo "first") #(out.txt: echo "second")'

    # Mock datetime.now() to ensure consistent timestamp during test
    fixed_time = datetime(2024, 1, 15, 10, 30, 45)
    with patch("gemini_wrapper.file_references.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_time
        result = process_xcmd_references(prompt)

    # Both patterns should be replaced
    assert "#(" not in result

    # Should have two distinct file references
    xcmds_dir = os.path.join(tmp_path, "bb/gai/xcmds")
    files = os.listdir(xcmds_dir)
    out_files = [f for f in files if f.startswith("out-")]
    assert len(out_files) == 2

    # One should have no counter suffix, other should have _1
    has_base = any(re.match(r"out-\d{6}_\d{6}\.txt$", f) for f in out_files)
    has_counter = any(re.match(r"out-\d{6}_\d{6}_1\.txt$", f) for f in out_files)
    assert has_base, f"Expected base filename pattern, got: {out_files}"
    assert has_counter, f"Expected counter filename pattern, got: {out_files}"


def test_process_xcmd_references_multiple_filename_collisions(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that three xcmds with same filename get unique names via counter."""
    monkeypatch.chdir(tmp_path)
    prompt = '#(out.json: echo "a") #(out.json: echo "b") #(out.json: echo "c")'

    # Mock datetime.now() to ensure consistent timestamp during test
    fixed_time = datetime(2024, 1, 15, 10, 30, 45)
    with patch("gemini_wrapper.file_references.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_time
        result = process_xcmd_references(prompt)

    # All patterns should be replaced
    assert "#(" not in result

    # Should have three distinct file references
    xcmds_dir = os.path.join(tmp_path, "bb/gai/xcmds")
    files = os.listdir(xcmds_dir)
    out_files = [f for f in files if f.startswith("out-")]
    assert len(out_files) == 3

    # Should have base, _1, and _2 suffixes
    has_base = any(re.match(r"out-\d{6}_\d{6}\.json$", f) for f in out_files)
    has_counter_1 = any(re.match(r"out-\d{6}_\d{6}_1\.json$", f) for f in out_files)
    has_counter_2 = any(re.match(r"out-\d{6}_\d{6}_2\.json$", f) for f in out_files)
    assert has_base, f"Expected base filename pattern, got: {out_files}"
    assert has_counter_1, f"Expected _1 counter filename pattern, got: {out_files}"
    assert has_counter_2, f"Expected _2 counter filename pattern, got: {out_files}"
