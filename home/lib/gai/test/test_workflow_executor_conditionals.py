"""Tests for conditional execution in workflow_executor."""

import os
import tempfile
from typing import Any

from xprompt.workflow_executor import WorkflowExecutor
from xprompt.workflow_models import (
    StepStatus,
    Workflow,
    WorkflowStep,
)


def _create_workflow(
    name: str,
    steps: list[WorkflowStep],
) -> Workflow:
    """Helper to create a workflow for testing."""
    return Workflow(name=name, steps=steps)


def _create_executor(
    workflow: Workflow,
    args: dict[str, Any] | None = None,
) -> WorkflowExecutor:
    """Helper to create an executor with a temp artifacts dir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = os.path.join(tmpdir, "artifacts")
        os.makedirs(artifacts_dir, exist_ok=True)
        executor = WorkflowExecutor(
            workflow=workflow,
            args=args or {},
            artifacts_dir=artifacts_dir,
        )
        # Store tmpdir reference to keep it alive during test
        executor._test_tmpdir = tmpdir  # type: ignore[attr-defined]
        return executor


# ============================================================================
# TestIfCondition - if: condition evaluation
# ============================================================================


def test_if_condition_true_executes_step() -> None:
    """Test that if: true executes the step."""
    steps = [
        WorkflowStep(
            name="conditional",
            bash="echo success",
            condition="{{ do_run }}",
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow, {"do_run": True})

    success = executor.execute()

    assert success
    assert executor.state.steps[0].status == StepStatus.COMPLETED


def test_if_condition_false_skips_step() -> None:
    """Test that if: false skips the step."""
    steps = [
        WorkflowStep(
            name="conditional",
            bash="echo should_not_run",
            condition="{{ do_run }}",
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow, {"do_run": False})

    success = executor.execute()

    assert success
    assert executor.state.steps[0].status == StepStatus.SKIPPED


def test_if_condition_evaluates_step_output_reference() -> None:
    """Test that if: can reference previous step output."""
    steps = [
        WorkflowStep(
            name="setup",
            bash="echo needs_cleanup=true",
        ),
        WorkflowStep(
            name="cleanup",
            bash="echo cleaned",
            condition="{{ setup.needs_cleanup }}",
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow)

    success = executor.execute()

    assert success
    assert executor.state.steps[1].status == StepStatus.COMPLETED


def test_if_condition_false_string_skips() -> None:
    """Test that string 'false' evaluates to false."""
    steps = [
        WorkflowStep(
            name="conditional",
            bash="echo should_skip",
            condition="{{ value }}",
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow, {"value": "false"})

    success = executor.execute()

    assert success
    assert executor.state.steps[0].status == StepStatus.SKIPPED


def test_if_condition_empty_string_skips() -> None:
    """Test that empty string evaluates to false."""
    steps = [
        WorkflowStep(
            name="conditional",
            bash="echo should_skip",
            condition="{{ value }}",
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow, {"value": ""})

    success = executor.execute()

    assert success
    assert executor.state.steps[0].status == StepStatus.SKIPPED


# ============================================================================
# TestEvaluateCondition - _evaluate_condition method
# ============================================================================


def test_evaluate_condition_truthy_string() -> None:
    """Test that non-empty string is truthy."""
    workflow = _create_workflow("test", [])
    executor = _create_executor(workflow, {"val": "hello"})
    assert executor._evaluate_condition("{{ val }}") is True


def test_evaluate_condition_falsy_values() -> None:
    """Test various falsy values."""
    workflow = _create_workflow("test", [])
    executor = _create_executor(workflow, {})

    # Test different falsy values
    assert executor._evaluate_condition("") is False
    assert executor._evaluate_condition("False") is False
    assert executor._evaluate_condition("false") is False
    assert executor._evaluate_condition("None") is False
    assert executor._evaluate_condition("0") is False
    assert executor._evaluate_condition("[]") is False
    assert executor._evaluate_condition("{}") is False


# ============================================================================
# TestCombinedControlFlow - combinations of if: with for:
# ============================================================================


def test_combined_if_with_for_conditional_iteration() -> None:
    """Test if: combined with for: - conditional iteration."""
    steps = [
        WorkflowStep(
            name="setup",
            bash='echo "should_run=true"',
        ),
        WorkflowStep(
            name="process",
            bash='echo "result={{ item }}"',
            condition="{{ setup.should_run }}",
            for_loop={"item": "{{ items }}"},
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow, {"items": ["a", "b"]})

    success = executor.execute()

    assert success
    assert executor.state.steps[1].status == StepStatus.COMPLETED


def test_combined_if_false_skips_for_loop() -> None:
    """Test if: false skips the entire for: loop."""
    steps = [
        WorkflowStep(
            name="process",
            bash='echo "result={{ item }}"',
            condition="{{ should_run }}",
            for_loop={"item": "{{ items }}"},
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow, {"should_run": False, "items": ["a", "b"]})

    success = executor.execute()

    assert success
    assert executor.state.steps[0].status == StepStatus.SKIPPED
