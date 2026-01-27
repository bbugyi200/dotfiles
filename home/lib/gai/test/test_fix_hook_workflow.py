"""Tests for fix_hook_workflow module."""

from pathlib import Path

from fix_hook_workflow import FixHookWorkflow, _build_fix_hook_prompt


# Tests for _build_fix_hook_prompt
def test_build_fix_hook_prompt_basic(tmp_path: Path) -> None:
    """Test basic prompt construction."""
    output_file = tmp_path / "output.txt"
    output_file.write_text("test output")
    prompt = _build_fix_hook_prompt("make test", str(output_file))
    assert 'The command "make test" is failing' in prompt
    assert f"@{output_file}" in prompt
    assert "re-running that command" in prompt
    assert "IMPORTANT" in prompt
    assert "Do NOT commit" in prompt


def test_build_fix_hook_prompt_with_complex_command(tmp_path: Path) -> None:
    """Test prompt construction with a complex command."""
    output_file = tmp_path / "test_output.txt"
    output_file.write_text("test output")
    prompt = _build_fix_hook_prompt(
        "python -m pytest tests/ -v --cov=src", str(output_file)
    )
    assert 'The command "python -m pytest tests/ -v --cov=src" is failing' in prompt
    assert f"@{output_file}" in prompt


def test_build_fix_hook_prompt_contains_instructions(tmp_path: Path) -> None:
    """Test that prompt contains proper instructions."""
    output_file = tmp_path / "lint.log"
    output_file.write_text("lint output")
    prompt = _build_fix_hook_prompt("npm run lint", str(output_file))
    # Should ask to make file changes
    assert "making the appropriate file changes" in prompt
    # Should instruct to verify fix
    assert "Verify that your fix worked" in prompt
    # Should not commit
    assert "leave them uncommitted" in prompt


# Tests for FixHookWorkflow class
def test_workflow_name() -> None:
    """Test workflow name property."""
    workflow = FixHookWorkflow("/path/to/output.txt", "make test")
    assert workflow.name == "fix-hook"


def test_workflow_description() -> None:
    """Test workflow description property."""
    workflow = FixHookWorkflow("/path/to/output.txt", "make test")
    assert "hook" in workflow.description.lower()
    assert "AI" in workflow.description or "assistance" in workflow.description.lower()


def test_workflow_stores_arguments() -> None:
    """Test that workflow stores the provided arguments."""
    workflow = FixHookWorkflow(
        hook_output_file="/path/to/output.txt",
        hook_command="make test",
    )
    assert workflow.hook_output_file == "/path/to/output.txt"
    assert workflow.hook_command == "make test"


def test_workflow_has_console() -> None:
    """Test that workflow initializes with a Console."""
    workflow = FixHookWorkflow("/path/to/output.txt", "make test")
    assert workflow.console is not None
