"""Tests for meta_* field helpers in prompt_panel."""

from typing import Any

from ace.tui.widgets.prompt_panel import (
    _aggregate_meta_fields,
    _extract_meta_fields,
    _format_meta_key,
)

# --- _format_meta_key tests ---


def test_format_meta_key_single_word() -> None:
    """Single word after prefix is title-cased."""
    assert _format_meta_key("meta_status") == "Status"


def test_format_meta_key_multi_word() -> None:
    """Multiple words are separated by spaces and title-cased."""
    assert _format_meta_key("meta_new_cl") == "New Cl"


def test_format_meta_key_multiple_underscores() -> None:
    """Several underscores are all replaced with spaces."""
    assert _format_meta_key("meta_a_b_c") == "A B C"


# --- _extract_meta_fields tests ---


def test_extract_meta_fields_basic() -> None:
    """Extracts a single meta field."""
    output = {"status": "ok", "meta_new_cl": "my_cl"}
    result = _extract_meta_fields(output)
    assert result == [("New Cl", "my_cl")]


def test_extract_meta_fields_no_meta() -> None:
    """Returns empty list when no meta fields present."""
    output = {"status": "ok", "message": "done"}
    result = _extract_meta_fields(output)
    assert result == []


def test_extract_meta_fields_multiple() -> None:
    """Extracts multiple meta fields in order."""
    output = {"meta_foo": "1", "other": "x", "meta_bar": "2"}
    result = _extract_meta_fields(output)
    assert result == [("Foo", "1"), ("Bar", "2")]


def test_extract_meta_fields_non_string_value() -> None:
    """Non-string values are converted to str."""
    output = {"meta_count": 42}
    result = _extract_meta_fields(output)
    assert result == [("Count", "42")]


# --- _aggregate_meta_fields tests ---


def test_aggregate_meta_fields_single_step() -> None:
    """Single step with meta field, no suffix needed."""
    steps = [{"output": {"meta_id": "abc"}}]
    result = _aggregate_meta_fields(steps)
    assert result == [("Id", "abc")]


def test_aggregate_meta_fields_no_duplicates() -> None:
    """Distinct keys across steps get no suffix."""
    steps = [
        {"output": {"meta_foo": "1"}},
        {"output": {"meta_bar": "2"}},
    ]
    result = _aggregate_meta_fields(steps)
    assert result == [("Foo", "1"), ("Bar", "2")]


def test_aggregate_meta_fields_duplicates() -> None:
    """Duplicate keys across steps get #N suffixes."""
    steps = [
        {"output": {"meta_id": "first"}},
        {"output": {"meta_id": "second"}},
    ]
    result = _aggregate_meta_fields(steps)
    assert result == [("Id #1", "first"), ("Id #2", "second")]


def test_aggregate_meta_fields_mixed() -> None:
    """Mix of unique and duplicate keys."""
    steps = [
        {"output": {"meta_cl": "cl1", "meta_unique": "u"}},
        {"output": {"meta_cl": "cl2"}},
    ]
    result = _aggregate_meta_fields(steps)
    assert result == [("Cl #1", "cl1"), ("Unique", "u"), ("Cl #2", "cl2")]


def test_aggregate_meta_fields_empty_output() -> None:
    """Steps with no output or non-dict output are skipped."""
    steps: list[dict[str, Any]] = [
        {"output": None},
        {},
        {"output": "raw string"},
        {"output": {"meta_ok": "yes"}},
    ]
    result = _aggregate_meta_fields(steps)
    assert result == [("Ok", "yes")]
