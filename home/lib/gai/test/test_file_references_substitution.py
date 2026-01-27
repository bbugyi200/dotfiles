"""Tests for command substitution and main API in the file_references module."""

import os
import tempfile

import pytest
from gemini_wrapper.file_references import (
    _find_command_substitutions,
    _find_matching_paren,
    process_command_substitution,
    process_file_references,
)

# Tests for process_command_substitution


def test_process_command_substitution_no_pattern() -> None:
    """Test that prompts without $() are returned unchanged."""
    prompt = "This is a regular prompt with no command substitution"
    result = process_command_substitution(prompt)
    assert result == prompt


def test_process_command_substitution_simple_command() -> None:
    """Test simple command substitution."""
    prompt = 'The output is $(echo "hello")'
    result = process_command_substitution(prompt)
    assert result == "The output is hello"


def test_process_command_substitution_nested_parens() -> None:
    """Test nested parentheses are handled correctly."""
    # Nested command substitution
    prompt = '$(echo $(echo "inner"))'
    result = process_command_substitution(prompt)
    assert result == "inner"


def test_process_command_substitution_parens_in_command() -> None:
    """Test parentheses within the command are handled."""
    # Subshell with parens
    prompt = '$(echo "(parens)")'
    result = process_command_substitution(prompt)
    assert result == "(parens)"


def test_process_command_substitution_multiple() -> None:
    """Test multiple substitutions in one prompt."""
    prompt = '$(echo "a") and $(echo "b")'
    result = process_command_substitution(prompt)
    assert result == "a and b"


def test_process_command_substitution_escaped() -> None:
    """Test that escaped \\$( is not substituted."""
    prompt = "Literal \\$(not a command) here"
    result = process_command_substitution(prompt)
    assert result == "Literal $(not a command) here"


def test_process_command_substitution_failed_command() -> None:
    """Test that failed commands result in empty string."""
    prompt = "Before $(nonexistent_command_xyz_12345) after"
    result = process_command_substitution(prompt)
    # Failed command should be replaced with empty string
    assert result == "Before  after"


def test_process_command_substitution_empty_output() -> None:
    """Test that commands with empty output result in empty string."""
    prompt = "Before $(true) after"
    result = process_command_substitution(prompt)
    assert result == "Before  after"


def test_process_command_substitution_unclosed_paren() -> None:
    """Test that unclosed $( is left unchanged."""
    prompt = "Unclosed $(echo hello"
    result = process_command_substitution(prompt)
    assert result == prompt


def test_process_command_substitution_preserves_surrounding() -> None:
    """Test that surrounding text is preserved."""
    prompt = 'Start $(echo "middle") end'
    result = process_command_substitution(prompt)
    assert result == "Start middle end"


def test_process_command_substitution_multiline_output() -> None:
    """Test that multiline output is stripped properly."""
    prompt = '$(printf "line1\\nline2")'
    result = process_command_substitution(prompt)
    assert result == "line1\nline2"


def test_process_command_substitution_deeply_nested() -> None:
    """Test deeply nested command substitutions."""
    prompt = '$(echo $(echo $(echo "deep")))'
    result = process_command_substitution(prompt)
    assert result == "deep"


# Tests for helper functions


def test_find_matching_paren_simple() -> None:
    """Test finding matching paren in simple case."""
    text = "abc)"
    result = _find_matching_paren(text, 0)
    assert result == 3


def test_find_matching_paren_nested() -> None:
    """Test finding matching paren with nested parens."""
    text = "a(b)c)"
    result = _find_matching_paren(text, 0)
    assert result == 5


def test_find_matching_paren_deeply_nested() -> None:
    """Test finding matching paren with deeply nested parens."""
    text = "a((b))c)"
    result = _find_matching_paren(text, 0)
    assert result == 7


def test_find_matching_paren_no_match() -> None:
    """Test when no matching paren exists."""
    text = "abc(def"
    result = _find_matching_paren(text, 0)
    assert result == -1


def test_find_command_substitutions_simple() -> None:
    """Test finding a simple command substitution."""
    text = "$(echo hi)"
    result = _find_command_substitutions(text)
    assert len(result) == 1
    assert result[0] == (0, 10, "echo hi")


def test_find_command_substitutions_escaped() -> None:
    """Test that escaped $( is skipped."""
    text = "\\$(not a command)"
    result = _find_command_substitutions(text)
    assert len(result) == 0


def test_find_command_substitutions_multiple() -> None:
    """Test finding multiple command substitutions."""
    text = "$(cmd1) and $(cmd2)"
    result = _find_command_substitutions(text)
    assert len(result) == 2
    assert result[0] == (0, 7, "cmd1")
    assert result[1] == (12, 19, "cmd2")


# Tests for process_file_references with is_home_mode


def test_process_file_references_home_mode_expands_tilde() -> None:
    """Test that home mode expands tilde paths without copying."""
    home = os.path.expanduser("~")

    # Create a temp file in home directory
    with tempfile.NamedTemporaryFile(
        suffix=".txt", dir=home, delete=False, prefix="test_home_mode_"
    ) as f:
        temp_path = f.name
        temp_basename = os.path.basename(temp_path)

    try:
        prompt = f"Check @~/{temp_basename}"
        result = process_file_references(prompt, is_home_mode=True)

        # Should expand tilde to full path
        assert f"@{home}/{temp_basename}" in result
        # Original tilde reference should be gone
        assert f"@~/{temp_basename}" not in result
    finally:
        os.unlink(temp_path)


def test_process_file_references_home_mode_no_copy(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that home mode does NOT create bb/gai/context directory."""
    monkeypatch.chdir(tmp_path)

    # Create a temp file with absolute path
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        temp_path = f.name
        f.write(b"test content")

    try:
        prompt = f"Check @{temp_path}"
        result = process_file_references(prompt, is_home_mode=True)

        # bb/gai/context should NOT be created in home mode
        context_dir = os.path.join(tmp_path, "bb/gai/context")
        assert not os.path.exists(context_dir)

        # Prompt should be unchanged for non-tilde absolute paths
        assert f"@{temp_path}" in result
    finally:
        os.unlink(temp_path)


def test_process_file_references_home_mode_absolute_path_unchanged() -> None:
    """Test that absolute paths without tilde are left unchanged in home mode."""
    # Create a temp file with absolute path
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        temp_path = f.name
        f.write(b"test content")

    try:
        prompt = f"Check @{temp_path}"
        result = process_file_references(prompt, is_home_mode=True)

        # Absolute path without tilde should remain unchanged
        assert f"@{temp_path}" in result
    finally:
        os.unlink(temp_path)


def test_process_file_references_home_mode_relative_path_unchanged(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that relative paths are left unchanged in home mode."""
    monkeypatch.chdir(tmp_path)

    # Create a temp file in cwd
    test_file = os.path.join(tmp_path, "test_relative.txt")
    with open(test_file, "w") as f:
        f.write("test content")

    prompt = "Check @test_relative.txt"
    result = process_file_references(prompt, is_home_mode=True)

    # Relative path should remain unchanged
    assert "@test_relative.txt" in result


def test_process_file_references_normal_mode_copies_files(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that normal mode (is_home_mode=False) still copies files."""
    monkeypatch.chdir(tmp_path)

    # Create a temp file with absolute path
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        temp_path = f.name
        f.write(b"test content")
        temp_basename = os.path.basename(temp_path)

    try:
        prompt = f"Check @{temp_path}"
        result = process_file_references(prompt, is_home_mode=False)

        # bb/gai/context should be created in normal mode
        # Note: uses PID-based subdirectory
        pid = os.getpid()
        context_dir = os.path.join(tmp_path, f"bb/gai/context/{pid}")
        assert os.path.exists(context_dir)

        # File should be copied
        copied_file = os.path.join(context_dir, temp_basename)
        assert os.path.exists(copied_file)

        # Prompt should reference the copied file
        assert f"@bb/gai/context/{pid}/{temp_basename}" in result
    finally:
        os.unlink(temp_path)
