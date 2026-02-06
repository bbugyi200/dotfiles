"""Tests for parallel execution in workflow_executor."""

import os
import tempfile
import time
from typing import Any
from unittest.mock import patch

import pytest
from xprompt.models import InputArg, InputType
from xprompt.workflow_executor import WorkflowExecutor
from xprompt.workflow_models import (
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


# ============================================================================
# TestParallelExecution - parallel: step execution
# ============================================================================


def test_parallel_executes_all_steps() -> None:
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


def test_parallel_runs_concurrently() -> None:
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


def test_parallel_default_join_is_object() -> None:
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


def test_parallel_with_join_array() -> None:
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


def test_parallel_context_isolation() -> None:
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


def test_parallel_step_failure_raises() -> None:
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


def test_parallel_with_if_condition() -> None:
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


# ============================================================================
# TestForParallel - for: + parallel: combination
# ============================================================================


def test_for_parallel_basic() -> None:
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


def test_for_parallel_runs_iteration_parallel_steps_concurrently() -> None:
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


def test_for_parallel_with_join_object() -> None:
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


def test_for_parallel_empty_list() -> None:
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


# ============================================================================
# TestPreExpandParallelEmbeddedWorkflows
# ============================================================================


def test_pre_expand_parallel_no_embedded_workflows() -> None:
    """Test that steps without embedded workflows pass through unchanged."""
    nested_steps = [
        WorkflowStep(name="step_a", bash='echo "a=done"'),
        WorkflowStep(name="step_b", prompt="Plain prompt with no refs"),
    ]

    workflow = _create_workflow("test", [])
    executor = _create_executor(workflow)

    with patch("xprompt.loader.get_all_workflows") as mock_get:
        mock_get.return_value = {}
        modified, collected = executor._pre_expand_parallel_embedded_workflows(
            nested_steps
        )

    # Bash step passes through as-is
    assert modified[0] is nested_steps[0]
    # Prompt step without embedded refs also passes through as-is
    assert modified[1] is nested_steps[1]
    assert collected == []


def test_pre_expand_parallel_expands_prompt_part_inline() -> None:
    """Test that prompt_part content is expanded inline in the prompt."""
    # Create an embedded workflow with only a prompt_part (no pre/post steps)
    embedded_wf = Workflow(
        name="inject",
        steps=[
            WorkflowStep(
                name="inject_step",
                prompt_part="INJECTED CONTENT HERE",
            )
        ],
    )

    nested_steps = [
        WorkflowStep(name="step_a", prompt="Do something. #inject"),
    ]

    workflow = _create_workflow("test", [])
    executor = _create_executor(workflow)

    with patch("xprompt.loader.get_all_workflows") as mock_get:
        mock_get.return_value = {"inject": embedded_wf}
        modified, collected = executor._pre_expand_parallel_embedded_workflows(
            nested_steps
        )

    # prompt_part content should be expanded inline
    assert modified[0].prompt is not None
    assert "INJECTED CONTENT HERE" in modified[0].prompt
    assert "#inject" not in modified[0].prompt
    # No post-steps to collect (only prompt_part)
    assert collected == []


def test_pre_expand_parallel_collects_post_steps() -> None:
    """Test that post-steps are collected for execution after parallel."""
    # Create an embedded workflow with prompt_part + post-step (like #file)
    embedded_wf = Workflow(
        name="test_embed",
        inputs=[InputArg(name="name", type=InputType.WORD)],
        steps=[
            WorkflowStep(
                name="inject",
                prompt_part="Write output to file {{ name }}.md",
            ),
            WorkflowStep(
                name="verify",
                hidden=True,
                bash='echo "verified={{ name }}"',
            ),
        ],
    )

    nested_steps = [
        WorkflowStep(
            name="agent_a", prompt="Research topic A. #test_embed(name=topicA)"
        ),
        WorkflowStep(
            name="agent_b", prompt="Research topic B. #test_embed(name=topicB)"
        ),
    ]

    workflow = _create_workflow("test", [])
    executor = _create_executor(workflow)

    with patch("xprompt.loader.get_all_workflows") as mock_get:
        mock_get.return_value = {"test_embed": embedded_wf}
        modified, collected = executor._pre_expand_parallel_embedded_workflows(
            nested_steps
        )

    # Both prompts should have prompt_part expanded inline
    assert modified[0].prompt is not None
    assert modified[1].prompt is not None
    assert "Write output to file" in modified[0].prompt
    assert "#test_embed" not in modified[0].prompt
    assert "Write output to file" in modified[1].prompt
    assert "#test_embed" not in modified[1].prompt

    # Original steps should not be mutated
    assert nested_steps[0].prompt is not None
    assert nested_steps[1].prompt is not None
    assert "#test_embed" in nested_steps[0].prompt
    assert "#test_embed" in nested_steps[1].prompt

    # Should have collected 2 sets of post-steps (one per embedded ref)
    assert len(collected) == 2
    for _pre_steps, post_steps, ctx in collected:
        assert len(post_steps) == 1
        assert post_steps[0].name == "verify"
        assert "name" in ctx


def test_pre_expand_parallel_preserves_non_prompt_steps() -> None:
    """Test that non-prompt steps in parallel are not modified."""
    embedded_wf = Workflow(
        name="inject",
        steps=[
            WorkflowStep(name="inject_step", prompt_part="EXTRA"),
        ],
    )

    nested_steps = [
        WorkflowStep(name="bash_step", bash='echo "done=true"'),
        WorkflowStep(name="prompt_step", prompt="Hello #inject"),
    ]

    workflow = _create_workflow("test", [])
    executor = _create_executor(workflow)

    with patch("xprompt.loader.get_all_workflows") as mock_get:
        mock_get.return_value = {"inject": embedded_wf}
        modified, _ = executor._pre_expand_parallel_embedded_workflows(nested_steps)

    # Bash step should be the same object (not copied)
    assert modified[0] is nested_steps[0]
    # Prompt step should be a new copy with expanded content
    assert modified[1] is not nested_steps[1]
    assert modified[1].prompt is not None
    assert "EXTRA" in modified[1].prompt


# ============================================================================
# TestParallelStepNumbering - marker files with parent step info
# ============================================================================


def test_parallel_children_get_step_numbering_markers() -> None:
    """Test that parallel child steps get markers with parent step numbering."""
    import json

    nested_steps = [
        WorkflowStep(name="child_a", bash='echo "a=done"'),
        WorkflowStep(name="child_b", bash='echo "b=done"'),
    ]
    steps = [
        WorkflowStep(
            name="parallel_step",
            parallel_config=ParallelConfig(steps=nested_steps),
        ),
        WorkflowStep(name="final_step", bash='echo "final=done"'),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow)
    success = executor.execute()
    assert success

    # Check child marker files have correct parent step info
    for child_name, expected_idx in [("child_a", 0), ("child_b", 1)]:
        marker_path = os.path.join(
            executor.artifacts_dir, f"prompt_step_{child_name}.json"
        )
        with open(marker_path) as f:
            data = json.load(f)
        assert data["parent_step_index"] == 0  # parallel_step is step 0
        assert data["parent_total_steps"] == 2  # 2 top-level steps
        assert data["step_index"] == expected_idx


def test_running_step_marker_has_step_index() -> None:
    """Test that the initial 'running' marker includes the step index."""
    import json

    steps = [
        WorkflowStep(name="only_step", bash='echo "done=true"'),
    ]
    workflow = _create_workflow("test", steps)
    executor = _create_executor(workflow)
    success = executor.execute()
    assert success

    marker_path = os.path.join(executor.artifacts_dir, "prompt_step_only_step.json")
    with open(marker_path) as f:
        data = json.load(f)
    assert data["step_index"] == 0
    assert data["total_steps"] == 1
