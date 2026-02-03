"""Tests for loop execution in workflow_executor."""

import os
import tempfile
from typing import Any
from unittest.mock import patch

import pytest
from xprompt.workflow_executor import WorkflowExecutor
from xprompt.workflow_models import (
    LoopConfig,
    Workflow,
    WorkflowExecutionError,
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
# TestForLoop - for: loop execution
# ============================================================================


def test_for_loop_single_list_iteration() -> None:
    """Test for: iterates over single list."""
    steps = [
        WorkflowStep(
            name="process",
            bash='echo "result={{ item }}"',
            for_loop={"item": "{{ items }}"},
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow, {"items": ["a", "b", "c"]})

    success = executor.execute()

    assert success
    # Results should be collected as array by default
    assert executor.context["process"] is not None
    assert isinstance(executor.context["process"], list)


def test_for_loop_empty_list() -> None:
    """Test for: with empty list produces empty result."""
    steps = [
        WorkflowStep(
            name="process",
            bash="echo result={{ item }}",
            for_loop={"item": "{{ items }}"},
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow, {"items": []})

    success = executor.execute()

    assert success
    assert executor.context["process"] == []


def test_for_loop_parallel_iteration() -> None:
    """Test for: with multiple parallel lists."""
    steps = [
        WorkflowStep(
            name="process",
            bash='echo "name={{ name }},id={{ id }}"',
            for_loop={
                "name": "{{ names }}",
                "id": "{{ ids }}",
            },
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(
        workflow,
        {"names": ["alice", "bob"], "ids": [1, 2]},
    )

    success = executor.execute()

    assert success
    assert len(executor.context["process"]) == 2


def test_for_loop_unequal_lists_raises_error() -> None:
    """Test for: raises error when lists have unequal lengths."""
    steps = [
        WorkflowStep(
            name="process",
            bash="echo {{ name }} {{ id }}",
            for_loop={
                "name": "{{ names }}",
                "id": "{{ ids }}",
            },
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(
        workflow,
        {"names": ["alice", "bob", "charlie"], "ids": [1, 2]},
    )

    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.execute()

    assert "unequal lengths" in str(exc_info.value)


# ============================================================================
# TestJoinModes - join: modes in for: loops
# ============================================================================


def test_join_modes_array_default() -> None:
    """Test that array is the default join mode."""
    steps = [
        WorkflowStep(
            name="process",
            bash='echo "result={{ item }}"',
            for_loop={"item": "{{ items }}"},
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow, {"items": ["a", "b"]})

    executor.execute()

    assert isinstance(executor.context["process"], list)


def test_join_modes_lastOf() -> None:
    """Test join: lastOf keeps only last result."""
    steps = [
        WorkflowStep(
            name="process",
            bash='echo "result={{ item }}"',
            for_loop={"item": "{{ items }}"},
            join="lastOf",
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow, {"items": ["a", "b", "c"]})

    executor.execute()

    # Should be dict, not list
    result = executor.context["process"]
    assert isinstance(result, dict)


def test_join_modes_object_merges_dicts() -> None:
    """Test join: object merges all results."""
    steps = [
        WorkflowStep(
            name="process",
            bash='echo "key_{{ item }}=value_{{ item }}"',
            for_loop={"item": "{{ items }}"},
            join="object",
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow, {"items": ["a", "b"]})

    executor.execute()

    result = executor.context["process"]
    assert isinstance(result, dict)


# ============================================================================
# TestCollectResults - _collect_results method
# ============================================================================


def test_collect_results_empty_array() -> None:
    """Test collecting empty results as array."""
    workflow = _create_workflow("test", [])
    executor = _create_executor(workflow)
    result = executor._collect_results([], "array")
    assert result == []


def test_collect_results_empty_object() -> None:
    """Test collecting empty results as object."""
    workflow = _create_workflow("test", [])
    executor = _create_executor(workflow)
    result = executor._collect_results([], "object")
    assert result == {}


def test_collect_results_lastOf() -> None:
    """Test lastOf returns last item."""
    workflow = _create_workflow("test", [])
    executor = _create_executor(workflow)
    results = [{"a": 1}, {"b": 2}, {"c": 3}]
    result = executor._collect_results(results, "lastOf")
    assert result == {"c": 3}


def test_collect_results_object_merges() -> None:
    """Test object mode merges all dicts."""
    workflow = _create_workflow("test", [])
    executor = _create_executor(workflow)
    results = [{"a": 1}, {"b": 2}]
    result = executor._collect_results(results, "object")
    assert result == {"a": 1, "b": 2}


def test_collect_results_text_concatenates() -> None:
    """Test text mode concatenates outputs."""
    workflow = _create_workflow("test", [])
    executor = _create_executor(workflow)
    results = [{"_raw": "line1"}, {"_raw": "line2"}]
    result = executor._collect_results(results, "text")
    assert result == "line1\nline2"


# ============================================================================
# TestRepeatLoop - repeat:/until: loop execution
# ============================================================================


def test_repeat_loop_stops_when_condition_true() -> None:
    """Test repeat: stops when until: becomes true."""
    # We'll mock the bash execution to simulate changing state
    call_count = [0]

    def mock_execute_bash(
        self: WorkflowExecutor,
        step: WorkflowStep,
        step_state: Any,
    ) -> bool:
        call_count[0] += 1
        # Simulate success on 3rd attempt
        step_state.output = {"success": call_count[0] >= 3}
        self.context[step.name] = step_state.output
        self.state.context = dict(self.context)
        return True

    steps = [
        WorkflowStep(
            name="retry",
            bash="try_action.sh",
            repeat_config=LoopConfig(
                condition="{{ retry.success }}",
                max_iterations=5,
            ),
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow)

    with patch.object(WorkflowExecutor, "_execute_bash_step", mock_execute_bash):
        success = executor.execute()

    assert success
    assert call_count[0] == 3  # Should have run 3 times


def test_repeat_loop_raises_at_max_iterations() -> None:
    """Test repeat: raises error at max iterations."""

    def mock_execute_bash(
        self: WorkflowExecutor,
        step: WorkflowStep,
        step_state: Any,
    ) -> bool:
        # Never succeed
        step_state.output = {"success": False}
        self.context[step.name] = step_state.output
        self.state.context = dict(self.context)
        return True

    steps = [
        WorkflowStep(
            name="retry",
            bash="try_action.sh",
            repeat_config=LoopConfig(
                condition="{{ retry.success }}",
                max_iterations=3,
            ),
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow)

    with patch.object(WorkflowExecutor, "_execute_bash_step", mock_execute_bash):
        with pytest.raises(WorkflowExecutionError) as exc_info:
            executor.execute()

    assert "exceeded max iterations" in str(exc_info.value)
    assert "3" in str(exc_info.value)


# ============================================================================
# TestWhileLoop - while: loop execution
# ============================================================================


def test_while_loop_stops_when_condition_false() -> None:
    """Test while: stops when condition becomes false."""
    call_count = [0]

    def mock_execute_bash(
        self: WorkflowExecutor,
        step: WorkflowStep,
        step_state: Any,
    ) -> bool:
        call_count[0] += 1
        # Stop after 3 iterations
        step_state.output = {"pending": call_count[0] < 3}
        self.context[step.name] = step_state.output
        self.state.context = dict(self.context)
        return True

    steps = [
        WorkflowStep(
            name="poll",
            bash="check_status.sh",
            while_config=LoopConfig(
                condition="{{ poll.pending }}",
                max_iterations=10,
            ),
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow)

    with patch.object(WorkflowExecutor, "_execute_bash_step", mock_execute_bash):
        success = executor.execute()

    assert success
    assert call_count[0] == 3  # Ran 3 times (pending=True, True, False)


def test_while_loop_raises_at_max_iterations() -> None:
    """Test while: raises error at max iterations."""

    def mock_execute_bash(
        self: WorkflowExecutor,
        step: WorkflowStep,
        step_state: Any,
    ) -> bool:
        # Always pending
        step_state.output = {"pending": True}
        self.context[step.name] = step_state.output
        self.state.context = dict(self.context)
        return True

    steps = [
        WorkflowStep(
            name="poll",
            bash="check_status.sh",
            while_config=LoopConfig(
                condition="{{ poll.pending }}",
                max_iterations=5,
            ),
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow)

    with patch.object(WorkflowExecutor, "_execute_bash_step", mock_execute_bash):
        with pytest.raises(WorkflowExecutionError) as exc_info:
            executor.execute()

    assert "exceeded max iterations" in str(exc_info.value)
    assert "condition still true" in str(exc_info.value)


def test_while_loop_executes_at_least_once() -> None:
    """Test while: executes at least once even if condition is immediately false."""
    call_count = [0]

    def mock_execute_bash(
        self: WorkflowExecutor,
        step: WorkflowStep,
        step_state: Any,
    ) -> bool:
        call_count[0] += 1
        # Immediately false
        step_state.output = {"pending": False}
        self.context[step.name] = step_state.output
        self.state.context = dict(self.context)
        return True

    steps = [
        WorkflowStep(
            name="poll",
            bash="check_status.sh",
            while_config=LoopConfig(
                condition="{{ poll.pending }}",
                max_iterations=10,
            ),
        ),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow)

    with patch.object(WorkflowExecutor, "_execute_bash_step", mock_execute_bash):
        success = executor.execute()

    assert success
    assert call_count[0] == 1  # Should execute exactly once


# ============================================================================
# TestResolveForLists - _resolve_for_lists method
# ============================================================================


def test_resolve_for_lists_from_context() -> None:
    """Test resolving list directly from context."""
    workflow = _create_workflow("test", [])
    executor = _create_executor(workflow, {"items": ["a", "b", "c"]})

    var_names, resolved_lists = executor._resolve_for_lists({"item": "{{ items }}"})

    assert var_names == ["item"]
    assert resolved_lists == [["a", "b", "c"]]


def test_resolve_for_lists_json_string() -> None:
    """Test resolving JSON list from string."""
    workflow = _create_workflow("test", [])
    executor = _create_executor(workflow, {"json_items": '["x", "y"]'})

    _, resolved_lists = executor._resolve_for_lists({"item": "{{ json_items }}"})

    assert resolved_lists == [["x", "y"]]


def test_resolve_for_lists_single_value_as_list() -> None:
    """Test that non-list values become single-item lists."""
    workflow = _create_workflow("test", [])
    executor = _create_executor(workflow, {"single": "value"})

    _, resolved_lists = executor._resolve_for_lists({"item": "{{ single }}"})

    assert resolved_lists == [["value"]]
