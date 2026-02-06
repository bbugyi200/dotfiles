"""Tests for the workflow exports feature."""

import tempfile
from pathlib import Path
from typing import Any

from xprompt.workflow_executor_steps_embedded import EmbeddedWorkflowInfo
from xprompt.workflow_loader import _load_workflow_from_file
from xprompt.workflow_models import WorkflowStep

# --- Loader tests ---


def test_exports_parsed_from_yaml() -> None:
    """Test that exports field is parsed from workflow YAML."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        content = """\
exports:
  file_path: verify_file.file_path
steps:
  - name: verify_file
    bash: echo "file_path=/tmp/test.md"
    output: { file_path: path }
"""
        path = Path(tmp_dir) / "test.yml"
        path.write_text(content)

        workflow = _load_workflow_from_file(path)

        assert workflow is not None
        assert workflow.exports == {"file_path": "verify_file.file_path"}


def test_exports_empty_when_not_specified() -> None:
    """Test that exports defaults to empty dict when not in YAML."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        content = """\
steps:
  - name: step1
    bash: echo hello
"""
        path = Path(tmp_dir) / "test.yml"
        path.write_text(content)

        workflow = _load_workflow_from_file(path)

        assert workflow is not None
        assert workflow.exports == {}


def test_exports_multiple_keys() -> None:
    """Test that multiple export keys are parsed correctly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        content = """\
exports:
  file_path: verify.file_path
  summary: analyze.summary
steps:
  - name: verify
    bash: echo "file_path=/tmp/test.md"
    output: { file_path: path }
  - name: analyze
    bash: echo "summary=done"
    output: { summary: text }
"""
        path = Path(tmp_dir) / "test.yml"
        path.write_text(content)

        workflow = _load_workflow_from_file(path)

        assert workflow is not None
        assert workflow.exports == {
            "file_path": "verify.file_path",
            "summary": "analyze.summary",
        }


def test_exports_preserved_in_project_workflows() -> None:
    """Test that exports are preserved when loading project workflows."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        content = """\
exports:
  result: step1.output_val
steps:
  - name: step1
    bash: echo "output_val=42"
    output: { output_val: line }
"""
        path = Path(tmp_dir) / "test.yml"
        path.write_text(content)

        workflow = _load_workflow_from_file(path)

        assert workflow is not None
        assert workflow.exports == {"result": "step1.output_val"}


# --- EmbeddedWorkflowInfo tests ---


def test_embedded_workflow_info_defaults() -> None:
    """Test that EmbeddedWorkflowInfo has correct defaults."""
    info = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[],
        context={},
        workflow_name="test",
    )

    assert info.exports == {}
    assert info.first_input_value is None


def test_embedded_workflow_info_with_values() -> None:
    """Test EmbeddedWorkflowInfo with all fields populated."""
    step = WorkflowStep(name="s1", bash="echo hi")
    info = EmbeddedWorkflowInfo(
        pre_steps=[step],
        post_steps=[step],
        context={"name": "foo"},
        workflow_name="file",
        exports={"file_path": "verify.file_path"},
        first_input_value="foo",
    )

    assert info.workflow_name == "file"
    assert info.exports == {"file_path": "verify.file_path"}
    assert info.first_input_value == "foo"


# --- Export propagation tests ---


class _FakeMixin:
    """Minimal fake to test _propagate_embedded_exports."""

    def __init__(self) -> None:
        self.context: dict[str, Any] = {}


def _make_propagate(
    mixin: _FakeMixin,
) -> Any:
    """Bind the mixin method to a fake instance for testing."""
    from xprompt.workflow_executor_steps_embedded import EmbeddedWorkflowMixin

    return EmbeddedWorkflowMixin._propagate_embedded_exports.__get__(mixin, _FakeMixin)


def test_propagate_exports_basic() -> None:
    """Test basic export propagation resolves dotted paths."""
    mixin = _FakeMixin()
    propagate = _make_propagate(mixin)

    info = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[],
        context={"verify_file": {"file_path": "/tmp/test.md"}},
        workflow_name="file",
        exports={"file_path": "verify_file.file_path"},
        first_input_value="prior_art",
    )

    propagate([info])

    assert "_file_prior_art" in mixin.context
    assert mixin.context["_file_prior_art"] == {"file_path": "/tmp/test.md"}


def test_propagate_exports_no_first_input() -> None:
    """Test export propagation when no first input value exists."""
    mixin = _FakeMixin()
    propagate = _make_propagate(mixin)

    info = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[],
        context={"step1": {"val": "42"}},
        workflow_name="compute",
        exports={"val": "step1.val"},
        first_input_value=None,
    )

    propagate([info])

    assert "_compute" in mixin.context
    assert mixin.context["_compute"] == {"val": "42"}


def test_propagate_exports_missing_step_output() -> None:
    """Test export propagation when step output is missing."""
    mixin = _FakeMixin()
    propagate = _make_propagate(mixin)

    info = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[],
        context={},
        workflow_name="file",
        exports={"file_path": "nonexistent.file_path"},
        first_input_value="test",
    )

    propagate([info])

    assert "_file_test" in mixin.context
    assert mixin.context["_file_test"] == {"file_path": None}


def test_propagate_exports_no_exports_skipped() -> None:
    """Test that workflows without exports are skipped."""
    mixin = _FakeMixin()
    propagate = _make_propagate(mixin)

    info = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[],
        context={"step1": {"val": "42"}},
        workflow_name="noop",
        exports={},
        first_input_value="test",
    )

    propagate([info])

    assert mixin.context == {}


def test_propagate_exports_multiple_workflows() -> None:
    """Test propagation from multiple embedded workflows."""
    mixin = _FakeMixin()
    propagate = _make_propagate(mixin)

    info1 = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[],
        context={"verify": {"path": "/a.md"}},
        workflow_name="file",
        exports={"file_path": "verify.path"},
        first_input_value="alpha",
    )
    info2 = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[],
        context={"verify": {"path": "/b.md"}},
        workflow_name="file",
        exports={"file_path": "verify.path"},
        first_input_value="beta",
    )

    propagate([info1, info2])

    assert mixin.context["_file_alpha"] == {"file_path": "/a.md"}
    assert mixin.context["_file_beta"] == {"file_path": "/b.md"}


def test_propagate_exports_non_dict_step_output() -> None:
    """Test export propagation when step output is not a dict."""
    mixin = _FakeMixin()
    propagate = _make_propagate(mixin)

    info = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[],
        context={"step1": "just_a_string"},
        workflow_name="file",
        exports={"val": "step1.field"},
        first_input_value="test",
    )

    propagate([info])

    assert mixin.context["_file_test"] == {"val": None}


def test_propagate_exports_undotted_path() -> None:
    """Test export propagation with a simple (non-dotted) path."""
    mixin = _FakeMixin()
    propagate = _make_propagate(mixin)

    info = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[],
        context={"simple_val": "hello"},
        workflow_name="greet",
        exports={"msg": "simple_val"},
        first_input_value=None,
    )

    propagate([info])

    assert mixin.context["_greet"] == {"msg": "hello"}
