"""Tests for embedded workflow output propagation."""

from typing import Any

from xprompt.models import OutputSpec
from xprompt.workflow_executor_steps_embedded import (
    EmbeddedWorkflowInfo,
    EmbeddedWorkflowMixin,
)
from xprompt.workflow_models import StepState, StepStatus, WorkflowStep


def _make_output_spec(keys: list[str]) -> OutputSpec:
    """Helper to create an OutputSpec with the given property keys."""
    return OutputSpec(
        type="json_schema",
        schema={"properties": {k: {"type": "string"} for k in keys}},
    )


def _make_step_state(name: str, output: dict[str, Any] | None = None) -> StepState:
    """Helper to create a StepState."""
    return StepState(name=name, status=StepStatus.COMPLETED, output=output)


class _FakeMixin(EmbeddedWorkflowMixin):
    """Minimal fake that provides the context dict and delegates to the real method."""

    def __init__(self, context: dict[str, Any]) -> None:
        self.context = context  # type: ignore[assignment]


def _call_propagate(
    context: dict[str, Any],
    embedded_workflows: list[EmbeddedWorkflowInfo],
    step: WorkflowStep,
    step_state: StepState,
) -> None:
    """Call _propagate_last_embedded_output via the fake mixin."""
    fake = _FakeMixin(context)
    fake._propagate_last_embedded_output(embedded_workflows, step, step_state)


# ============================================================================
# EmbeddedWorkflowInfo dataclass basics
# ============================================================================


def test_embedded_workflow_info_defaults() -> None:
    """Test EmbeddedWorkflowInfo default values."""
    info = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[],
        context={},
        workflow_name="test",
    )
    assert info.nested_step_name is None
    assert info.workflow_name == "test"
    assert info.pre_steps == []
    assert info.post_steps == []
    assert info.context == {}


def test_embedded_workflow_info_with_nested_step_name() -> None:
    """Test EmbeddedWorkflowInfo with nested_step_name set."""
    info = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[],
        context={"key": "val"},
        workflow_name="file",
        nested_step_name="prior_art",
    )
    assert info.nested_step_name == "prior_art"


# ============================================================================
# _propagate_last_embedded_output tests
# ============================================================================


def test_propagate_basic_matching_output() -> None:
    """Test basic propagation when parent and embedded outputs match."""
    post_step = WorkflowStep(
        name="verify_file",
        bash='echo "file_path=test.md"',
        output=_make_output_spec(["file_path"]),
    )
    embedded_context: dict[str, Any] = {
        "verify_file": {"file_path": "/tmp/test-240101_120000.md"},
    }
    info = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[post_step],
        context=embedded_context,
        workflow_name="file",
    )

    parent_step = WorkflowStep(
        name="plan",
        prompt="write a plan",
        output=_make_output_spec(["file_path"]),
    )
    step_state = _make_step_state("plan", output={"_raw": "some response"})
    context: dict[str, Any] = {"plan": {"_raw": "some response"}}

    _call_propagate(context, [info], parent_step, step_state)

    assert step_state.output == {"file_path": "/tmp/test-240101_120000.md"}
    assert context["plan"] == {"file_path": "/tmp/test-240101_120000.md"}


def test_propagate_noop_when_parent_has_no_output() -> None:
    """Test no propagation when parent step has no output spec."""
    post_step = WorkflowStep(
        name="verify",
        bash='echo "file_path=test.md"',
        output=_make_output_spec(["file_path"]),
    )
    info = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[post_step],
        context={"verify": {"file_path": "test.md"}},
        workflow_name="file",
    )

    parent_step = WorkflowStep(name="plan", prompt="write a plan")  # no output
    step_state = _make_step_state("plan", output={"_raw": "response"})
    context: dict[str, Any] = {"plan": {"_raw": "response"}}

    _call_propagate(context, [info], parent_step, step_state)

    assert step_state.output == {"_raw": "response"}
    assert context["plan"] == {"_raw": "response"}


def test_propagate_noop_when_embedded_post_step_has_no_output() -> None:
    """Test no propagation when embedded post-step has no output spec."""
    post_step = WorkflowStep(
        name="verify",
        bash='echo "done"',
        # no output spec
    )
    info = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[post_step],
        context={"verify": {"file_path": "test.md"}},
        workflow_name="file",
    )

    parent_step = WorkflowStep(
        name="plan",
        prompt="write a plan",
        output=_make_output_spec(["file_path"]),
    )
    step_state = _make_step_state("plan", output={"_raw": "response"})
    context: dict[str, Any] = {"plan": {"_raw": "response"}}

    _call_propagate(context, [info], parent_step, step_state)

    assert step_state.output == {"_raw": "response"}


def test_propagate_noop_when_output_keys_dont_match() -> None:
    """Test no propagation when output keys don't match."""
    post_step = WorkflowStep(
        name="verify",
        bash='echo "url=http://example.com"',
        output=_make_output_spec(["url"]),
    )
    info = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[post_step],
        context={"verify": {"url": "http://example.com"}},
        workflow_name="file",
    )

    parent_step = WorkflowStep(
        name="plan",
        prompt="write a plan",
        output=_make_output_spec(["file_path"]),  # wants file_path, not url
    )
    step_state = _make_step_state("plan", output={"_raw": "response"})
    context: dict[str, Any] = {"plan": {"_raw": "response"}}

    _call_propagate(context, [info], parent_step, step_state)

    assert step_state.output == {"_raw": "response"}


def test_propagate_noop_when_no_embedded_workflows() -> None:
    """Test no propagation when embedded_workflows is empty."""
    parent_step = WorkflowStep(
        name="plan",
        prompt="write a plan",
        output=_make_output_spec(["file_path"]),
    )
    step_state = _make_step_state("plan", output={"_raw": "response"})
    context: dict[str, Any] = {"plan": {"_raw": "response"}}

    _call_propagate(context, [], parent_step, step_state)

    assert step_state.output == {"_raw": "response"}


def test_propagate_noop_when_no_post_steps() -> None:
    """Test no propagation when embedded workflow has no post-steps."""
    info = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[],
        context={},
        workflow_name="file",
    )

    parent_step = WorkflowStep(
        name="plan",
        prompt="write a plan",
        output=_make_output_spec(["file_path"]),
    )
    step_state = _make_step_state("plan", output={"_raw": "response"})
    context: dict[str, Any] = {"plan": {"_raw": "response"}}

    _call_propagate(context, [info], parent_step, step_state)

    assert step_state.output == {"_raw": "response"}


def test_propagate_uses_last_embedded_workflow() -> None:
    """Test that propagation uses the last embedded workflow, not the first."""
    post_step_first = WorkflowStep(
        name="verify_first",
        bash='echo "file_path=first.md"',
        output=_make_output_spec(["file_path"]),
    )
    post_step_last = WorkflowStep(
        name="verify_last",
        bash='echo "file_path=last.md"',
        output=_make_output_spec(["file_path"]),
    )
    info_first = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[post_step_first],
        context={"verify_first": {"file_path": "first.md"}},
        workflow_name="file",
    )
    info_last = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[post_step_last],
        context={"verify_last": {"file_path": "last.md"}},
        workflow_name="file",
    )

    parent_step = WorkflowStep(
        name="plan",
        prompt="write a plan",
        output=_make_output_spec(["file_path"]),
    )
    step_state = _make_step_state("plan", output={"_raw": "response"})
    context: dict[str, Any] = {"plan": {"_raw": "response"}}

    _call_propagate(context, [info_first, info_last], parent_step, step_state)

    # Should use the last embedded workflow
    assert step_state.output == {"file_path": "last.md"}
    assert context["plan"] == {"file_path": "last.md"}


def test_propagate_parent_keys_subset_of_embedded() -> None:
    """Test propagation works when parent keys are a subset of embedded keys."""
    post_step = WorkflowStep(
        name="verify",
        bash='echo "file_path=test.md"',
        output=_make_output_spec(["file_path", "extra_key"]),
    )
    info = EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[post_step],
        context={"verify": {"file_path": "test.md", "extra_key": "extra_val"}},
        workflow_name="file",
    )

    # Parent only wants file_path (subset of embedded's keys)
    parent_step = WorkflowStep(
        name="plan",
        prompt="write a plan",
        output=_make_output_spec(["file_path"]),
    )
    step_state = _make_step_state("plan", output={"_raw": "response"})
    context: dict[str, Any] = {"plan": {"_raw": "response"}}

    _call_propagate(context, [info], parent_step, step_state)

    # Should propagate the entire embedded output
    assert step_state.output == {"file_path": "test.md", "extra_key": "extra_val"}
