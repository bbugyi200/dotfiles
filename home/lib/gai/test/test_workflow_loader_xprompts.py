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
xprompts:
  _shared_context: "Always be thorough."
steps:
  - name: analyze
    prompt: "#_shared_context\\nAnalyze the code."
"""
        path = Path(tmp_dir) / "test.yml"
        path.write_text(workflow_content)

        workflow = _load_workflow_from_file(path)

        assert workflow is not None
        assert workflow.name == "test"
        assert "_shared_context" in workflow.xprompts
        assert workflow.xprompts["_shared_context"].content == "Always be thorough."


def test_load_workflow_from_file_with_structured_xprompts() -> None:
    """Test loading a workflow YAML that has structured xprompts."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workflow_content = """\
xprompts:
  _greet:
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
        assert "_greet" in workflow.xprompts
        assert workflow.xprompts["_greet"].content == "Hello {{ name }}!"
        assert len(workflow.xprompts["_greet"].inputs) == 1
        assert workflow.xprompts["_greet"].inputs[0].name == "name"


def test_load_workflow_from_file_no_xprompts() -> None:
    """Test loading a workflow without xprompts field works fine."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workflow_content = """\
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
xprompts:
  _my_prompt:
    input:
      target: word
    content: "Review {{ target }} carefully."
steps:
  - name: review
    prompt: "#_my_prompt(code)"
"""
        path = Path(tmp_dir) / "test.yml"
        path.write_text(workflow_content)

        workflow = _load_workflow_from_file(path)
        assert workflow is not None

        # Validate should pass because workflow-local xprompt is found
        with patch("xprompt.workflow_validator.get_all_xprompts", return_value={}):
            # No global xprompts, but workflow-local "_my_prompt" should be used
            validate_workflow(workflow)


def test_workflow_local_xprompts_take_priority_over_globals() -> None:
    """Test that workflow-local xprompts take priority over global ones."""
    global_xprompt = XPrompt(
        name="_shared",
        content="Global content requiring {{ missing_arg }}.",
        inputs=[],
        source_path="config",
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        workflow_content = """\
xprompts:
  _shared: "Local content with no args."
steps:
  - name: use_it
    prompt: "#_shared"
"""
        path = Path(tmp_dir) / "test.yml"
        path.write_text(workflow_content)

        workflow = _load_workflow_from_file(path)
        assert workflow is not None

        # Validate with global "_shared" that has issues, but local overrides it
        with patch(
            "xprompt.workflow_validator.get_all_xprompts",
            return_value={"_shared": global_xprompt},
        ):
            # Should succeed because local xprompt (no args) overrides global
            validate_workflow(workflow)


def test_workflow_local_xprompts_auto_prefix_underscore() -> None:
    """Test that xprompt names without '_' prefix are auto-prefixed."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workflow_content = """\
xprompts:
  desc: "A description prompt."
steps:
  - name: step1
    prompt: "#_desc"
"""
        path = Path(tmp_dir) / "test.yml"
        path.write_text(workflow_content)

        workflow = _load_workflow_from_file(path)
        assert workflow is not None
        assert "_desc" in workflow.xprompts
        assert "desc" not in workflow.xprompts
        assert workflow.xprompts["_desc"].name == "_desc"
        assert workflow.xprompts["_desc"].content == "A description prompt."


def test_workflow_local_xprompts_no_double_prefix() -> None:
    """Test that xprompt names already starting with '_' are not double-prefixed."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workflow_content = """\
xprompts:
  _desc: "A description prompt."
steps:
  - name: step1
    prompt: "#_desc"
"""
        path = Path(tmp_dir) / "test.yml"
        path.write_text(workflow_content)

        workflow = _load_workflow_from_file(path)
        assert workflow is not None
        assert "_desc" in workflow.xprompts
        assert "__desc" not in workflow.xprompts
        assert workflow.xprompts["_desc"].name == "_desc"
