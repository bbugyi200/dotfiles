"""Tests for input/variable collection in workflow_validator."""

from xprompt.models import InputArg, InputType
from xprompt.workflow_models import Workflow, WorkflowStep
from xprompt.workflow_validator import (
    _collect_used_variables,
    _detect_unused_inputs,
)


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
            InputArg(name="prompt_var", type=InputType.LINE),
            InputArg(name="python_var", type=InputType.LINE),
        ],
        steps=[
            WorkflowStep(name="s1", bash="echo {{ bash_var }}"),
            WorkflowStep(name="s2", prompt="{{ prompt_var }}"),
            WorkflowStep(name="s3", python="print({{ python_var }})"),
        ],
    )
    used = _collect_used_variables(workflow)
    assert "bash_var" in used
    assert "prompt_var" in used
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
