"""Tests for hint extraction and parsing functions."""

from ace.hints import (
    build_editor_args,
    is_rerun_input,
    parse_edit_hooks_input,
    parse_test_targets,
    parse_view_input,
)

# --- Tests for is_rerun_input ---


def test_is_rerun_input_empty() -> None:
    """Empty input is not a rerun input."""
    assert is_rerun_input("") is False


def test_is_rerun_input_single_number() -> None:
    """Single number is a valid rerun input."""
    assert is_rerun_input("1") is True


def test_is_rerun_input_multiple_numbers() -> None:
    """Multiple numbers separated by spaces are valid."""
    assert is_rerun_input("1 2 3") is True


def test_is_rerun_input_with_at_suffix() -> None:
    """Numbers with @ suffix (delete) are valid."""
    assert is_rerun_input("1@") is True
    assert is_rerun_input("1@ 2 3@") is True


def test_is_rerun_input_rejects_double_at() -> None:
    """Double @@ suffix is rejected."""
    assert is_rerun_input("1@@") is False


def test_is_rerun_input_rejects_non_numbers() -> None:
    """Non-numeric input is rejected."""
    assert is_rerun_input("abc") is False
    assert is_rerun_input("1 abc 2") is False


def test_is_rerun_input_rejects_test_targets() -> None:
    """Test targets (starting with //) are rejected."""
    assert is_rerun_input("//foo:bar") is False


# --- Tests for parse_view_input ---


def test_parse_view_input_empty() -> None:
    """Empty input returns empty results."""
    files, open_in_editor, invalid = parse_view_input("", {0: "/path/to/file"})
    assert files == []
    assert open_in_editor is False
    assert invalid == []


def test_parse_view_input_single_hint() -> None:
    """Single valid hint returns the file path."""
    hint_mappings = {0: "/path/to/project", 1: "/path/to/chat"}
    files, open_in_editor, invalid = parse_view_input("1", hint_mappings)
    assert files == ["/path/to/chat"]
    assert open_in_editor is False
    assert invalid == []


def test_parse_view_input_multiple_hints() -> None:
    """Multiple hints return multiple file paths."""
    hint_mappings = {0: "/path/a", 1: "/path/b", 2: "/path/c"}
    files, open_in_editor, invalid = parse_view_input("0 2", hint_mappings)
    assert files == ["/path/a", "/path/c"]
    assert open_in_editor is False
    assert invalid == []


def test_parse_view_input_with_at_suffix() -> None:
    """@ suffix sets open_in_editor to True."""
    hint_mappings = {0: "/path/a", 1: "/path/b"}
    files, open_in_editor, invalid = parse_view_input("1@", hint_mappings)
    assert files == ["/path/b"]
    assert open_in_editor is True
    assert invalid == []


def test_parse_view_input_standalone_at() -> None:
    """Standalone @ is skipped (no longer supported as shorthand)."""
    hint_mappings = {0: "/path/project", 1: "/path/file"}
    files, open_in_editor, invalid = parse_view_input("@", hint_mappings)
    # Standalone @ is skipped, so no files are selected
    assert files == []
    # But open_in_editor is still set because @ suffix was detected
    assert open_in_editor is True


def test_parse_view_input_invalid_hint() -> None:
    """Invalid hints are reported."""
    hint_mappings = {0: "/path/a", 1: "/path/b"}
    files, open_in_editor, invalid = parse_view_input("1 5", hint_mappings)
    assert files == ["/path/b"]
    assert invalid == [5]


def test_parse_view_input_expands_tilde() -> None:
    """Tilde paths are expanded."""
    hint_mappings = {0: "~/path/to/file"}
    files, _, _ = parse_view_input("0", hint_mappings)
    assert not files[0].startswith("~")


# --- Tests for parse_edit_hooks_input ---


def test_parse_edit_hooks_input_rerun() -> None:
    """Numbers without suffix are marked for rerun."""
    hint_mappings = {1: "/path/a", 2: "/path/b"}
    rerun, delete, invalid = parse_edit_hooks_input("1 2", hint_mappings)
    assert rerun == [1, 2]
    assert delete == []
    assert invalid == []


def test_parse_edit_hooks_input_delete() -> None:
    """Numbers with @ suffix are marked for delete."""
    hint_mappings = {1: "/path/a", 2: "/path/b"}
    rerun, delete, invalid = parse_edit_hooks_input("1@ 2@", hint_mappings)
    assert rerun == []
    assert delete == [1, 2]
    assert invalid == []


def test_parse_edit_hooks_input_mixed() -> None:
    """Mix of rerun and delete operations."""
    hint_mappings = {1: "/path/a", 2: "/path/b", 3: "/path/c"}
    rerun, delete, invalid = parse_edit_hooks_input("1 2@ 3", hint_mappings)
    assert rerun == [1, 3]
    assert delete == [2]
    assert invalid == []


def test_parse_edit_hooks_input_invalid() -> None:
    """Invalid hints are reported."""
    hint_mappings = {1: "/path/a"}
    rerun, delete, invalid = parse_edit_hooks_input("1 5@", hint_mappings)
    assert rerun == [1]
    assert delete == []
    assert invalid == [5]


# --- Tests for parse_test_targets ---


def test_parse_test_targets_single() -> None:
    """Single test target is parsed."""
    targets = parse_test_targets("//foo:bar")
    assert targets == ["//foo:bar"]


def test_parse_test_targets_multiple() -> None:
    """Multiple test targets are parsed."""
    targets = parse_test_targets("//foo:bar //baz:qux")
    assert targets == ["//foo:bar", "//baz:qux"]


def test_parse_test_targets_adds_prefix() -> None:
    """Missing // prefix is added."""
    targets = parse_test_targets("//foo:bar baz:qux")
    assert targets == ["//foo:bar", "//baz:qux"]


def test_parse_test_targets_empty() -> None:
    """Empty input returns empty list."""
    targets = parse_test_targets("")
    assert targets == []


# --- Tests for build_editor_args ---


def test_build_editor_args_basic() -> None:
    """Basic editor args."""
    args = build_editor_args("vim", ["/path/to/file"])
    assert args == ["vim", "/path/to/file"]


def test_build_editor_args_multiple_files() -> None:
    """Multiple files are appended."""
    args = build_editor_args("vim", ["/path/a", "/path/b"])
    assert args == ["vim", "/path/a", "/path/b"]


def test_build_editor_args_nvim() -> None:
    """nvim editor is passed through without special handling."""
    args = build_editor_args("/usr/bin/nvim", ["/path/project"])
    assert args == ["/usr/bin/nvim", "/path/project"]
