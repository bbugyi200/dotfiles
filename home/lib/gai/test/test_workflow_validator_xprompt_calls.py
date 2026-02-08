"""Tests for xprompt call extraction and validation in workflow_validator."""

import pytest
from xprompt.models import InputArg, InputType, XPrompt
from xprompt.workflow_models import (
    Workflow,
    WorkflowStep,
    WorkflowValidationError,
)
from xprompt.workflow_validator import (
    _detect_unused_xprompt_inputs,
    _detect_unused_xprompts,
    _extract_xprompt_calls,
    _validate_xprompt_call,
    _validate_xprompt_names,
    _XPromptCall,
)


def test_extract_xprompt_calls_simple() -> None:
    """Test extracting a simple xprompt reference."""
    calls = _extract_xprompt_calls("#foo")
    assert len(calls) == 1
    assert calls[0].name == "foo"
    assert calls[0].positional_args == []
    assert calls[0].named_args == {}


def test_extract_xprompt_calls_with_args() -> None:
    """Test extracting xprompt with parenthesis args."""
    calls = _extract_xprompt_calls('#bar(arg1, name="value")')
    assert len(calls) == 1
    assert calls[0].name == "bar"
    assert calls[0].positional_args == ["arg1"]
    assert calls[0].named_args == {"name": "value"}


def test_extract_xprompt_calls_colon_syntax() -> None:
    """Test extracting xprompt with colon syntax."""
    calls = _extract_xprompt_calls("#foo:myvalue")
    assert len(calls) == 1
    assert calls[0].name == "foo"
    assert calls[0].positional_args == ["myvalue"]
    assert calls[0].named_args == {}


def test_extract_xprompt_calls_plus_syntax() -> None:
    """Test extracting xprompt with plus syntax."""
    calls = _extract_xprompt_calls("#foo+")
    assert len(calls) == 1
    assert calls[0].name == "foo"
    assert calls[0].positional_args == ["true"]
    assert calls[0].named_args == {}


def test_extract_xprompt_calls_namespaced() -> None:
    """Test extracting namespaced xprompt."""
    calls = _extract_xprompt_calls("#namespace/name(arg)")
    assert len(calls) == 1
    assert calls[0].name == "namespace/name"
    assert calls[0].positional_args == ["arg"]


def test_extract_xprompt_calls_multiple() -> None:
    """Test extracting multiple xprompts from content."""
    content = "Use #foo then #bar(x) and #baz:y"
    calls = _extract_xprompt_calls(content)
    assert len(calls) == 3
    assert calls[0].name == "foo"
    assert calls[1].name == "bar"
    assert calls[2].name == "baz"


def test_validate_xprompt_call_valid() -> None:
    """Test validation of a valid xprompt call."""
    xprompt = XPrompt(
        name="test",
        content="{{ arg1 }}",
        inputs=[InputArg(name="arg1", type=InputType.LINE)],
    )
    call = _XPromptCall(
        name="test",
        positional_args=["value"],
        named_args={},
        raw_match="#test(value)",
    )
    errors = _validate_xprompt_call(call, xprompt, "step1")
    assert errors == []


def test_validate_xprompt_call_missing_required_arg() -> None:
    """Test validation detects missing required argument."""
    xprompt = XPrompt(
        name="test",
        content="{{ required_arg }}",
        inputs=[InputArg(name="required_arg", type=InputType.LINE)],
    )
    call = _XPromptCall(
        name="test",
        positional_args=[],
        named_args={},
        raw_match="#test",
    )
    errors = _validate_xprompt_call(call, xprompt, "step1")
    assert len(errors) == 1
    assert "missing required args" in errors[0]
    assert "required_arg" in errors[0]


def test_validate_xprompt_call_unknown_named_arg() -> None:
    """Test validation detects unknown named argument."""
    xprompt = XPrompt(
        name="test",
        content="{{ known }}",
        inputs=[InputArg(name="known", type=InputType.LINE, default="default")],
    )
    call = _XPromptCall(
        name="test",
        positional_args=[],
        named_args={"unknown_arg": "value"},
        raw_match='#test(unknown_arg="value")',
    )
    errors = _validate_xprompt_call(call, xprompt, "step1")
    assert len(errors) == 1
    assert "has no input named 'unknown_arg'" in errors[0]
    assert "Available:" in errors[0]


def test_validate_xprompt_call_too_many_positional_args() -> None:
    """Test validation detects too many positional arguments."""
    xprompt = XPrompt(
        name="test",
        content="{{ one }}",
        inputs=[InputArg(name="one", type=InputType.LINE)],
    )
    call = _XPromptCall(
        name="test",
        positional_args=["first", "second", "third"],
        named_args={},
        raw_match="#test(first, second, third)",
    )
    errors = _validate_xprompt_call(call, xprompt, "step1")
    assert len(errors) >= 1
    assert "3 positional args but only 1 inputs defined" in errors[0]


def test_validate_xprompt_call_with_default() -> None:
    """Test that args with defaults are not required."""
    xprompt = XPrompt(
        name="test",
        content="{{ optional }}",
        inputs=[
            InputArg(name="optional", type=InputType.LINE, default="default_value")
        ],
    )
    call = _XPromptCall(
        name="test",
        positional_args=[],
        named_args={},
        raw_match="#test",
    )
    errors = _validate_xprompt_call(call, xprompt, "step1")
    assert errors == []


def test_detect_unused_xprompts_finds_unused() -> None:
    """Workflow-local xprompt never referenced → error."""
    workflow = Workflow(
        name="test",
        steps=[WorkflowStep(name="step1", bash="echo hi")],
        xprompts={
            "_unused": XPrompt(name="_unused", content="some content"),
        },
    )
    xprompts = dict(workflow.xprompts)
    errors = _detect_unused_xprompts(workflow, xprompts)
    assert len(errors) == 1
    assert "_unused" in errors[0]


def test_detect_unused_xprompts_used_in_step() -> None:
    """Xprompt referenced in step content → no error."""
    workflow = Workflow(
        name="test",
        steps=[WorkflowStep(name="step1", prompt="Use #_helper here")],
        xprompts={
            "_helper": XPrompt(name="_helper", content="I help"),
        },
    )
    xprompts = dict(workflow.xprompts)
    errors = _detect_unused_xprompts(workflow, xprompts)
    assert errors == []


def test_detect_unused_xprompts_used_by_other_xprompt() -> None:
    """Xprompt referenced by another xprompt → no error."""
    workflow = Workflow(
        name="test",
        steps=[WorkflowStep(name="step1", prompt="Use #_outer here")],
        xprompts={
            "_base": XPrompt(name="_base", content="base content"),
            "_outer": XPrompt(name="_outer", content="wraps #_base"),
        },
    )
    xprompts = dict(workflow.xprompts)
    errors = _detect_unused_xprompts(workflow, xprompts)
    assert errors == []


def test_detect_unused_xprompt_inputs_finds_unused() -> None:
    """Xprompt input not in content → error."""
    workflow = Workflow(
        name="test",
        steps=[],
        xprompts={
            "_helper": XPrompt(
                name="_helper",
                content="no vars here",
                inputs=[InputArg(name="unused_arg", type=InputType.LINE)],
            ),
        },
    )
    errors = _detect_unused_xprompt_inputs(workflow)
    assert len(errors) == 1
    assert "unused_arg" in errors[0]
    assert "_helper" in errors[0]


def test_detect_unused_xprompt_inputs_used() -> None:
    """Xprompt input referenced in content → no error."""
    workflow = Workflow(
        name="test",
        steps=[],
        xprompts={
            "_helper": XPrompt(
                name="_helper",
                content="Use {{ my_arg }} here",
                inputs=[InputArg(name="my_arg", type=InputType.LINE)],
            ),
        },
    )
    errors = _detect_unused_xprompt_inputs(workflow)
    assert errors == []


def test_validate_xprompt_names_missing_underscore() -> None:
    """Xprompt name without '_' prefix → error."""
    workflow = Workflow(
        name="test",
        steps=[WorkflowStep(name="step1", bash="echo hi")],
        xprompts={
            "foo": XPrompt(name="foo", content="some content"),
        },
    )
    errors = _validate_xprompt_names(workflow)
    assert len(errors) == 1
    assert "foo" in errors[0]
    assert "must start with '_'" in errors[0]
    assert "'_foo'" in errors[0]


def test_validate_xprompt_names_valid() -> None:
    """Xprompt name with '_' prefix → no error."""
    workflow = Workflow(
        name="test",
        steps=[WorkflowStep(name="step1", bash="echo hi")],
        xprompts={
            "_foo": XPrompt(name="_foo", content="some content"),
        },
    )
    errors = _validate_xprompt_names(workflow)
    assert errors == []


def test_workflow_local_xprompt_with_scope_resolves_step_outputs() -> None:
    """Workflow-local xprompts with Jinja2 refs resolve via scope."""
    from xprompt.processor import process_xprompt_references

    xprompts = {
        "_research_files": XPrompt(
            name="_research_files",
            content="Files: {{ research.api_research.file_path }}",
        ),
    }
    scope = {
        "research": {
            "api_research": {"file_path": "/tmp/test.py"},
        },
    }
    result = process_xprompt_references(
        "Analyze #_research_files",
        extra_xprompts=xprompts,
        scope=scope,
    )
    assert "Files: /tmp/test.py" in result
    assert "#_research_files" not in result


def test_validate_workflow_raises_on_unused_xprompt() -> None:
    """Integration: validate_workflow() raises on unused workflow-local xprompt."""
    workflow = Workflow(
        name="test",
        steps=[WorkflowStep(name="step1", bash="echo hi")],
        xprompts={
            "_orphan": XPrompt(name="_orphan", content="never used"),
        },
    )
    with pytest.raises(WorkflowValidationError, match="_orphan"):
        from xprompt.workflow_validator import validate_workflow

        validate_workflow(workflow)


def test_validate_workflow_raises_on_unused_xprompt_input() -> None:
    """Integration: validate_workflow() raises on unused xprompt input."""
    workflow = Workflow(
        name="test",
        steps=[WorkflowStep(name="step1", prompt="Use #_helper here")],
        xprompts={
            "_helper": XPrompt(
                name="_helper",
                content="no vars",
                inputs=[InputArg(name="dead_input", type=InputType.LINE)],
            ),
        },
    )
    with pytest.raises(WorkflowValidationError, match="dead_input"):
        from xprompt.workflow_validator import validate_workflow

        validate_workflow(workflow)


def test_validate_workflow_raises_on_xprompt_missing_underscore() -> None:
    """Integration: validate_workflow() raises on xprompt name missing '_' prefix."""
    workflow = Workflow(
        name="test",
        steps=[WorkflowStep(name="step1", bash="echo hi")],
        xprompts={
            "bad_name": XPrompt(name="bad_name", content="some content"),
        },
    )
    with pytest.raises(WorkflowValidationError, match="must start with '_'"):
        from xprompt.workflow_validator import validate_workflow

        validate_workflow(workflow)
