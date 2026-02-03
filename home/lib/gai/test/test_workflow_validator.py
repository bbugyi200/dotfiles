"""Tests for the workflow_validator module."""

from xprompt.models import InputArg, InputType, XPrompt
from xprompt.workflow_models import Workflow, WorkflowStep
from xprompt.workflow_validator import (
    _collect_used_variables,
    _detect_unused_inputs,
    _extract_xprompt_calls,
    _validate_xprompt_call,
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


def test_collect_used_variables_simple() -> None:
    """Test collecting variables from simple workflow."""
    workflow = Workflow(
        name="test",
        inputs=[InputArg(name="my_input", type=InputType.LINE)],
        steps=[
            WorkflowStep(
                name="step1",
                bash="echo {{ my_input }}",
            )
        ],
    )
    used = _collect_used_variables(workflow)
    assert "my_input" in used


def test_collect_used_variables_multiple_sources() -> None:
    """Test collecting variables from multiple step types."""
    workflow = Workflow(
        name="test",
        inputs=[
            InputArg(name="bash_var", type=InputType.LINE),
            InputArg(name="agent_var", type=InputType.LINE),
            InputArg(name="python_var", type=InputType.LINE),
        ],
        steps=[
            WorkflowStep(name="s1", bash="echo {{ bash_var }}"),
            WorkflowStep(name="s2", agent="{{ agent_var }}"),
            WorkflowStep(name="s3", python="print({{ python_var }})"),
        ],
    )
    used = _collect_used_variables(workflow)
    assert "bash_var" in used
    assert "agent_var" in used
    assert "python_var" in used


def test_collect_used_variables_excludes_loop_vars() -> None:
    """Test that loop variables (item, loop) are not collected."""
    workflow = Workflow(
        name="test",
        inputs=[InputArg(name="items", type=InputType.LINE)],
        steps=[
            WorkflowStep(
                name="step1",
                bash="echo {{ item }} {{ loop.index }}",
                for_loop={"item": "items"},
            )
        ],
    )
    used = _collect_used_variables(workflow)
    assert "item" not in used
    assert "loop" not in used


def test_detect_unused_inputs_finds_unused() -> None:
    """Test detection of unused inputs."""
    workflow = Workflow(
        name="test",
        inputs=[
            InputArg(name="used_input", type=InputType.LINE),
            InputArg(name="unused_input", type=InputType.LINE),
        ],
        steps=[WorkflowStep(name="step1", bash="echo {{ used_input }}")],
    )
    used_vars = _collect_used_variables(workflow)
    unused = _detect_unused_inputs(workflow, used_vars)
    assert "unused_input" in unused
    assert "used_input" not in unused


def test_detect_unused_inputs_ignores_step_inputs() -> None:
    """Test that step inputs (auto-generated) are not flagged as unused."""
    workflow = Workflow(
        name="test",
        inputs=[
            InputArg(name="regular_input", type=InputType.LINE),
            InputArg(name="step_input", type=InputType.LINE, is_step_input=True),
        ],
        steps=[WorkflowStep(name="step1", bash="echo hi")],
    )
    used_vars = _collect_used_variables(workflow)
    unused = _detect_unused_inputs(workflow, used_vars)
    # step_input should not be in unused even though not referenced
    assert "step_input" not in unused
    # regular_input is unused and should be detected
    assert "regular_input" in unused


def test_collect_used_variables_from_condition() -> None:
    """Test that variables in if: conditions are collected."""
    workflow = Workflow(
        name="test",
        inputs=[InputArg(name="flag", type=InputType.BOOL)],
        steps=[
            WorkflowStep(
                name="step1",
                bash="echo hello",
                condition="{{ flag }}",
            )
        ],
    )
    used = _collect_used_variables(workflow)
    assert "flag" in used


def test_collect_used_variables_from_for_loop() -> None:
    """Test that variables in for: expressions are collected."""
    workflow = Workflow(
        name="test",
        inputs=[InputArg(name="items_list", type=InputType.LINE)],
        steps=[
            WorkflowStep(
                name="step1",
                bash="echo {{ item }}",
                for_loop={"item": "{{ items_list }}"},
            )
        ],
    )
    used = _collect_used_variables(workflow)
    assert "items_list" in used
