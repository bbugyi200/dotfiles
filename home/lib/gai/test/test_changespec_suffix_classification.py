"""Tests for suffix classification functions in ace/changespec/models.py."""

from ace.changespec.models import (
    is_plain_suffix,
    is_running_process_suffix,
)


# Tests for is_running_process_suffix
def test_is_running_process_suffix_none() -> None:
    """Test that None suffix is not a running process."""
    assert is_running_process_suffix(None) is False


def test_is_running_process_suffix_single_digit() -> None:
    """Test that single digit is NOT a PID (it's a commit reference)."""
    assert is_running_process_suffix("3") is False
    assert is_running_process_suffix("1") is False
    assert is_running_process_suffix("9") is False


def test_is_running_process_suffix_two_digits() -> None:
    """Test that two digits is NOT a PID (it's a commit reference)."""
    assert is_running_process_suffix("12") is False
    assert is_running_process_suffix("99") is False


def test_is_running_process_suffix_three_digits() -> None:
    """Test that three digits is NOT a PID (it's a commit reference)."""
    assert is_running_process_suffix("123") is False
    assert is_running_process_suffix("999") is False


def test_is_running_process_suffix_four_digits() -> None:
    """Test that four digits IS a PID."""
    assert is_running_process_suffix("1234") is True
    assert is_running_process_suffix("9999") is True


def test_is_running_process_suffix_five_digits() -> None:
    """Test that five digits IS a PID."""
    assert is_running_process_suffix("12345") is True


def test_is_running_process_suffix_six_digits() -> None:
    """Test that six digits IS a PID."""
    assert is_running_process_suffix("123456") is True


def test_is_running_process_suffix_non_digit() -> None:
    """Test that non-digit suffixes are not PIDs."""
    assert is_running_process_suffix("abc") is False
    assert is_running_process_suffix("12a") is False
    assert is_running_process_suffix("a12") is False
    assert is_running_process_suffix("3a") is False  # commit reference like "3a"
    assert is_running_process_suffix("error message") is False


def test_is_running_process_suffix_empty_string() -> None:
    """Test that empty string is not a running process."""
    assert is_running_process_suffix("") is False


# Tests for is_plain_suffix
def test_is_plain_suffix_none() -> None:
    """Test that None suffix is not considered a plain suffix.

    Note: The removal condition uses 'suffix is None or is_plain_suffix(suffix)',
    so None is handled separately from plain suffixes.
    """
    assert is_plain_suffix(None) is False


def test_is_plain_suffix_commit_reference_single_digit() -> None:
    """Test that single digit commit references are plain suffixes."""
    assert is_plain_suffix("3") is True
    assert is_plain_suffix("1") is True


def test_is_plain_suffix_commit_reference_multi_digit() -> None:
    """Test that multi-digit commit references are plain suffixes."""
    assert is_plain_suffix("12") is True
    assert is_plain_suffix("123") is True


def test_is_plain_suffix_commit_reference_with_letter() -> None:
    """Test that commit references with letters are plain suffixes."""
    assert is_plain_suffix("3a") is True
    assert is_plain_suffix("7d") is True


def test_is_plain_suffix_pid_not_plain() -> None:
    """Test that PID suffixes are not plain (they're running processes)."""
    assert is_plain_suffix("1234") is False
    assert is_plain_suffix("12345") is False
