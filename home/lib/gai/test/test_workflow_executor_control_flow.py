"""Tests for control flow execution in workflow_executor."""

import os
import tempfile
import time
from typing import Any
from unittest.mock import patch

import pytest
from xprompt.workflow_executor import WorkflowExecutor
from xprompt.workflow_models import (
    LoopConfig,
    ParallelConfig,
    StepStatus,
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


class TestIfCondition:
    """Tests for if: condition evaluation."""

    def test_if_true_executes_step(self) -> None:
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

    def test_if_false_skips_step(self) -> None:
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

    def test_if_evaluates_step_output_reference(self) -> None:
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

    def test_if_false_string_skips(self) -> None:
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

    def test_if_empty_string_skips(self) -> None:
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


class TestEvaluateCondition:
    """Tests for _evaluate_condition method."""

    def test_truthy_string(self) -> None:
        """Test that non-empty string is truthy."""
        workflow = _create_workflow("test", [])
        executor = _create_executor(workflow, {"val": "hello"})
        assert executor._evaluate_condition("{{ val }}") is True

    def test_falsy_values(self) -> None:
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


class TestForLoop:
    """Tests for for: loop execution."""

    def test_for_single_list_iteration(self) -> None:
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

    def test_for_empty_list(self) -> None:
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

    def test_for_parallel_iteration(self) -> None:
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

    def test_for_unequal_lists_raises_error(self) -> None:
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


class TestJoinModes:
    """Tests for join: modes in for: loops."""

    def test_join_array_default(self) -> None:
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

    def test_join_lastOf(self) -> None:
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

    def test_join_object_merges_dicts(self) -> None:
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


class TestCollectResults:
    """Tests for _collect_results method."""

    def test_collect_empty_array(self) -> None:
        """Test collecting empty results as array."""
        workflow = _create_workflow("test", [])
        executor = _create_executor(workflow)
        result = executor._collect_results([], "array")
        assert result == []

    def test_collect_empty_object(self) -> None:
        """Test collecting empty results as object."""
        workflow = _create_workflow("test", [])
        executor = _create_executor(workflow)
        result = executor._collect_results([], "object")
        assert result == {}

    def test_collect_lastOf(self) -> None:
        """Test lastOf returns last item."""
        workflow = _create_workflow("test", [])
        executor = _create_executor(workflow)
        results = [{"a": 1}, {"b": 2}, {"c": 3}]
        result = executor._collect_results(results, "lastOf")
        assert result == {"c": 3}

    def test_collect_object_merges(self) -> None:
        """Test object mode merges all dicts."""
        workflow = _create_workflow("test", [])
        executor = _create_executor(workflow)
        results = [{"a": 1}, {"b": 2}]
        result = executor._collect_results(results, "object")
        assert result == {"a": 1, "b": 2}

    def test_collect_text_concatenates(self) -> None:
        """Test text mode concatenates outputs."""
        workflow = _create_workflow("test", [])
        executor = _create_executor(workflow)
        results = [{"_raw": "line1"}, {"_raw": "line2"}]
        result = executor._collect_results(results, "text")
        assert result == "line1\nline2"


class TestRepeatLoop:
    """Tests for repeat:/until: loop execution."""

    def test_repeat_stops_when_condition_true(self) -> None:
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

    def test_repeat_raises_at_max_iterations(self) -> None:
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


class TestWhileLoop:
    """Tests for while: loop execution."""

    def test_while_stops_when_condition_false(self) -> None:
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

    def test_while_raises_at_max_iterations(self) -> None:
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

    def test_while_executes_at_least_once(self) -> None:
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


class TestResolveForLists:
    """Tests for _resolve_for_lists method."""

    def test_resolve_list_from_context(self) -> None:
        """Test resolving list directly from context."""
        workflow = _create_workflow("test", [])
        executor = _create_executor(workflow, {"items": ["a", "b", "c"]})

        var_names, resolved_lists = executor._resolve_for_lists({"item": "{{ items }}"})

        assert var_names == ["item"]
        assert resolved_lists == [["a", "b", "c"]]

    def test_resolve_json_list_string(self) -> None:
        """Test resolving JSON list from string."""
        workflow = _create_workflow("test", [])
        executor = _create_executor(workflow, {"json_items": '["x", "y"]'})

        _, resolved_lists = executor._resolve_for_lists({"item": "{{ json_items }}"})

        assert resolved_lists == [["x", "y"]]

    def test_resolve_single_value_as_list(self) -> None:
        """Test that non-list values become single-item lists."""
        workflow = _create_workflow("test", [])
        executor = _create_executor(workflow, {"single": "value"})

        _, resolved_lists = executor._resolve_for_lists({"item": "{{ single }}"})

        assert resolved_lists == [["value"]]


class TestCombinedControlFlow:
    """Tests for combinations of control flow constructs."""

    def test_if_with_for_conditional_iteration(self) -> None:
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

    def test_if_false_skips_for_loop(self) -> None:
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
        executor = _create_executor(
            workflow, {"should_run": False, "items": ["a", "b"]}
        )

        success = executor.execute()

        assert success
        assert executor.state.steps[0].status == StepStatus.SKIPPED


# ============================================================================
# Parallel step execution tests
# ============================================================================


class TestParallelExecution:
    """Tests for parallel: step execution."""

    def test_parallel_executes_all_steps(self) -> None:
        """Test parallel: executes all nested steps."""
        nested_steps = [
            WorkflowStep(name="step_a", bash='echo "a=done"'),
            WorkflowStep(name="step_b", bash='echo "b=done"'),
        ]
        steps = [
            WorkflowStep(
                name="parallel_test",
                parallel_config=ParallelConfig(steps=nested_steps),
            ),
        ]
        workflow = _create_workflow("test", steps)
        executor = _create_executor(workflow)

        success = executor.execute()

        assert success
        assert executor.state.steps[0].status == StepStatus.COMPLETED
        output = executor.context["parallel_test"]
        assert "step_a" in output
        assert "step_b" in output

    def test_parallel_runs_concurrently(self) -> None:
        """Test that parallel steps actually run concurrently (timing-based)."""
        # Each step sleeps for 0.5 seconds
        # If sequential, total time would be ~1 second
        # If parallel, total time should be ~0.5 seconds
        nested_steps = [
            WorkflowStep(name="step_a", bash='sleep 0.3 && echo "a=done"'),
            WorkflowStep(name="step_b", bash='sleep 0.3 && echo "b=done"'),
        ]
        steps = [
            WorkflowStep(
                name="parallel_test",
                parallel_config=ParallelConfig(steps=nested_steps),
            ),
        ]
        workflow = _create_workflow("test", steps)
        executor = _create_executor(workflow)

        start_time = time.time()
        success = executor.execute()
        elapsed = time.time() - start_time

        assert success
        # Should complete in less than 0.6s if truly parallel (allow some overhead)
        # Would be ~0.6s or more if sequential
        assert elapsed < 0.55, f"Expected parallel execution but took {elapsed:.2f}s"

    def test_parallel_default_join_is_object(self) -> None:
        """Test that default join mode for parallel is 'object'."""
        nested_steps = [
            WorkflowStep(name="step_a", bash='echo "value_a=1"'),
            WorkflowStep(name="step_b", bash='echo "value_b=2"'),
        ]
        steps = [
            WorkflowStep(
                name="parallel_test",
                parallel_config=ParallelConfig(steps=nested_steps),
                # No join specified - should default to object
            ),
        ]
        workflow = _create_workflow("test", steps)
        executor = _create_executor(workflow)

        executor.execute()

        output = executor.context["parallel_test"]
        # Output should be nested under step names
        assert isinstance(output, dict)
        assert "step_a" in output
        assert "step_b" in output

    def test_parallel_with_join_array(self) -> None:
        """Test parallel with join: array."""
        nested_steps = [
            WorkflowStep(name="step_a", bash='echo "val=1"'),
            WorkflowStep(name="step_b", bash='echo "val=2"'),
        ]
        steps = [
            WorkflowStep(
                name="parallel_test",
                parallel_config=ParallelConfig(steps=nested_steps),
                join="array",
            ),
        ]
        workflow = _create_workflow("test", steps)
        executor = _create_executor(workflow)

        executor.execute()

        output = executor.context["parallel_test"]
        assert isinstance(output, list)
        assert len(output) == 2

    def test_parallel_context_isolation(self) -> None:
        """Test that parallel steps have isolated context."""
        # Each step tries to modify a shared variable
        # If context is properly isolated, they shouldn't interfere
        nested_steps = [
            WorkflowStep(
                name="step_a",
                bash='echo "result={{ shared_var }}_a"',
            ),
            WorkflowStep(
                name="step_b",
                bash='echo "result={{ shared_var }}_b"',
            ),
        ]
        steps = [
            WorkflowStep(
                name="parallel_test",
                parallel_config=ParallelConfig(steps=nested_steps),
            ),
        ]
        workflow = _create_workflow("test", steps)
        executor = _create_executor(workflow, {"shared_var": "original"})

        success = executor.execute()

        assert success
        output = executor.context["parallel_test"]
        # Both should have seen the original value
        assert output["step_a"]["result"] == "original_a"
        assert output["step_b"]["result"] == "original_b"

    def test_parallel_step_failure_raises(self) -> None:
        """Test that failure in parallel step raises error."""
        nested_steps = [
            WorkflowStep(name="step_a", bash='echo "a=done"'),
            WorkflowStep(name="step_b", bash="exit 1"),  # This will fail
        ]
        steps = [
            WorkflowStep(
                name="parallel_test",
                parallel_config=ParallelConfig(steps=nested_steps),
            ),
        ]
        workflow = _create_workflow("test", steps)
        executor = _create_executor(workflow)

        with pytest.raises(WorkflowExecutionError) as exc_info:
            executor.execute()

        assert "parallel_test" in str(exc_info.value)

    def test_parallel_with_if_condition(self) -> None:
        """Test parallel step with if: condition."""
        nested_steps = [
            WorkflowStep(name="step_a", bash='echo "a=done"'),
            WorkflowStep(name="step_b", bash='echo "b=done"'),
        ]
        steps = [
            WorkflowStep(
                name="parallel_test",
                condition="{{ should_run }}",
                parallel_config=ParallelConfig(steps=nested_steps),
            ),
        ]
        workflow = _create_workflow("test", steps)
        executor = _create_executor(workflow, {"should_run": False})

        success = executor.execute()

        assert success
        assert executor.state.steps[0].status == StepStatus.SKIPPED


class TestForParallel:
    """Tests for for: + parallel: combination."""

    def test_for_parallel_basic(self) -> None:
        """Test basic for: + parallel: combination."""
        nested_steps = [
            WorkflowStep(name="lint", bash='echo "lint_{{ file }}=ok"'),
            WorkflowStep(name="format", bash='echo "format_{{ file }}=ok"'),
        ]
        steps = [
            WorkflowStep(
                name="process_files",
                for_loop={"file": "{{ files }}"},
                parallel_config=ParallelConfig(steps=nested_steps),
            ),
        ]
        workflow = _create_workflow("test", steps)
        executor = _create_executor(workflow, {"files": ["a.py", "b.py"]})

        success = executor.execute()

        assert success
        output = executor.context["process_files"]
        # Default join is array, so we get a list of results per iteration
        assert isinstance(output, list)
        assert len(output) == 2

    def test_for_parallel_runs_iteration_parallel_steps_concurrently(self) -> None:
        """Test that within each for iteration, parallel steps run concurrently."""
        nested_steps = [
            WorkflowStep(name="step_a", bash='sleep 0.2 && echo "a={{ item }}"'),
            WorkflowStep(name="step_b", bash='sleep 0.2 && echo "b={{ item }}"'),
        ]
        steps = [
            WorkflowStep(
                name="process",
                for_loop={"item": "{{ items }}"},
                parallel_config=ParallelConfig(steps=nested_steps),
            ),
        ]
        workflow = _create_workflow("test", steps)
        executor = _create_executor(workflow, {"items": ["x", "y"]})

        start_time = time.time()
        success = executor.execute()
        elapsed = time.time() - start_time

        assert success
        # 2 iterations, each with 2 parallel steps sleeping 0.2s
        # If parallel within iteration: 2 * 0.2 = 0.4s
        # If fully sequential: 4 * 0.2 = 0.8s
        # Should complete in under 0.6s if truly parallel
        assert elapsed < 0.6

    def test_for_parallel_with_join_object(self) -> None:
        """Test for: + parallel: with join: object."""
        nested_steps = [
            WorkflowStep(name="lint", bash='echo "result=lint_{{ file }}"'),
            WorkflowStep(name="format", bash='echo "result=format_{{ file }}"'),
        ]
        steps = [
            WorkflowStep(
                name="process_files",
                for_loop={"file": "{{ files }}"},
                parallel_config=ParallelConfig(steps=nested_steps),
                join="object",
            ),
        ]
        workflow = _create_workflow("test", steps)
        executor = _create_executor(workflow, {"files": ["a.py", "b.py"]})

        success = executor.execute()

        assert success
        output = executor.context["process_files"]
        # join: object merges all results
        assert isinstance(output, dict)

    def test_for_parallel_empty_list(self) -> None:
        """Test for: + parallel: with empty iteration list."""
        nested_steps = [
            WorkflowStep(name="step_a", bash='echo "a={{ item }}"'),
            WorkflowStep(name="step_b", bash='echo "b={{ item }}"'),
        ]
        steps = [
            WorkflowStep(
                name="process",
                for_loop={"item": "{{ items }}"},
                parallel_config=ParallelConfig(steps=nested_steps),
            ),
        ]
        workflow = _create_workflow("test", steps)
        executor = _create_executor(workflow, {"items": []})

        success = executor.execute()

        assert success
        output = executor.context["process"]
        assert output == []
