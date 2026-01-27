"""Tests for xcmd (external command) reference processing in file_references module."""

import os
import re
from datetime import datetime
from unittest.mock import patch

import pytest
from gemini_wrapper import file_references
from gemini_wrapper.file_references import process_xcmd_references


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
