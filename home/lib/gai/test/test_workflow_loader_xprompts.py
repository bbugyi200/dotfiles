"""Tests for workflow-local xprompts in workflow_loader."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from xprompt.loader import parse_xprompt_entries
from xprompt.models import XPrompt
from xprompt.workflow_loader import _load_workflow_from_file
from xprompt.workflow_validator import validate_workflow


def test_parse_xprompt_entries_simple_string() -> None:
    """Test parsing simple string xprompt entries."""
    entries = {"greeting": "Hello, world!"}
    result = parse_xprompt_entries(entries, "test")

    assert "greeting" in result
    assert result["greeting"].name == "greeting"
    assert result["greeting"].content == "Hello, world!"
    assert result["greeting"].inputs == []
    assert result["greeting"].source_path == "test"


def test_parse_xprompt_entries_structured() -> None:
    """Test parsing structured xprompt entries with input/content."""
    entries = {
        "greet": {
            "input": {"name": "word"},
            "content": "Hello {{ name }}!",
        }
    }
    result = parse_xprompt_entries(entries, "test")

    assert "greet" in result
    assert result["greet"].content == "Hello {{ name }}!"
    assert len(result["greet"].inputs) == 1
    assert result["greet"].inputs[0].name == "name"


def test_parse_xprompt_entries_multiple() -> None:
    """Test parsing multiple xprompt entries of mixed types."""
    entries = {
        "simple": "Just text.",
        "complex": {
            "input": {"x": "int"},
            "content": "Value: {{ x }}",
        },
    }
    result = parse_xprompt_entries(entries, "workflow.yml")

    assert len(result) == 2
    assert result["simple"].content == "Just text."
    assert result["complex"].content == "Value: {{ x }}"


def test_parse_xprompt_entries_empty() -> None:
    """Test parsing empty entries dict returns empty."""
    result = parse_xprompt_entries({}, "test")
    assert result == {}


def test_parse_xprompt_entries_skips_invalid_values() -> None:
    """Test that non-string, non-dict values are skipped."""
    entries = {"good": "valid", "bad": 42, "also_bad": ["list"]}
    result = parse_xprompt_entries(entries, "test")

    assert len(result) == 1
    assert "good" in result


def test_load_workflow_from_file_with_simple_xprompts() -> None:
    """Test loading a workflow YAML that has simple string xprompts."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workflow_content = """\
name: test_wf
xprompts:
  shared_context: "Always be thorough."
steps:
  - name: analyze
    prompt: "#shared_context\\nAnalyze the code."
"""
        path = Path(tmp_dir) / "test.yml"
        path.write_text(workflow_content)

        workflow = _load_workflow_from_file(path)

        assert workflow is not None
        assert workflow.name == "test_wf"
        assert "shared_context" in workflow.xprompts
        assert workflow.xprompts["shared_context"].content == "Always be thorough."


def test_load_workflow_from_file_with_structured_xprompts() -> None:
    """Test loading a workflow YAML that has structured xprompts."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workflow_content = """\
name: test_wf
xprompts:
  greet:
    input:
      name: word
    content: "Hello {{ name }}!"
steps:
  - name: step1
    prompt: "Do something."
"""
        path = Path(tmp_dir) / "test.yml"
        path.write_text(workflow_content)

        workflow = _load_workflow_from_file(path)

        assert workflow is not None
        assert "greet" in workflow.xprompts
        assert workflow.xprompts["greet"].content == "Hello {{ name }}!"
        assert len(workflow.xprompts["greet"].inputs) == 1
        assert workflow.xprompts["greet"].inputs[0].name == "name"


def test_load_workflow_from_file_no_xprompts() -> None:
    """Test loading a workflow without xprompts field works fine."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workflow_content = """\
name: no_xprompts_wf
steps:
  - name: step1
    bash: echo hello
"""
        path = Path(tmp_dir) / "test.yml"
        path.write_text(workflow_content)

        workflow = _load_workflow_from_file(path)

        assert workflow is not None
        assert workflow.xprompts == {}


def test_workflow_local_xprompts_override_globals_in_validator() -> None:
    """Test that workflow-local xprompts override globals during validation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workflow_content = """\
name: override_test
xprompts:
  my_prompt:
    input:
      target: word
    content: "Review {{ target }} carefully."
steps:
  - name: review
    prompt: "#my_prompt(code)"
"""
        path = Path(tmp_dir) / "test.yml"
        path.write_text(workflow_content)

        workflow = _load_workflow_from_file(path)
        assert workflow is not None

        # Validate should pass because workflow-local xprompt is found
        with patch("xprompt.workflow_validator.get_all_xprompts", return_value={}):
            # No global xprompts, but workflow-local "my_prompt" should be used
            validate_workflow(workflow)


def test_workflow_local_xprompts_take_priority_over_globals() -> None:
    """Test that workflow-local xprompts take priority over global ones."""
    global_xprompt = XPrompt(
        name="shared",
        content="Global content requiring {{ missing_arg }}.",
        inputs=[],
        source_path="config",
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        workflow_content = """\
name: priority_test
xprompts:
  shared: "Local content with no args."
steps:
  - name: use_it
    prompt: "#shared"
"""
        path = Path(tmp_dir) / "test.yml"
        path.write_text(workflow_content)

        workflow = _load_workflow_from_file(path)
        assert workflow is not None

        # Validate with global "shared" that has issues, but local overrides it
        with patch(
            "xprompt.workflow_validator.get_all_xprompts",
            return_value={"shared": global_xprompt},
        ):
            # Should succeed because local xprompt (no args) overrides global
            validate_workflow(workflow)
