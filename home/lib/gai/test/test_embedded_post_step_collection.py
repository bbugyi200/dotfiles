"""Tests for _collect_embedded_post_step_outputs() in workflow_executor_steps_prompt."""

from xprompt.models import OutputSpec
from xprompt.workflow_executor_steps_embedded import EmbeddedWorkflowInfo
from xprompt.workflow_executor_steps_prompt import _collect_embedded_post_step_outputs
from xprompt.workflow_models import WorkflowStep


def _make_info(
    ctx: dict[str, object],
    post_steps: list[WorkflowStep] | None = None,
) -> EmbeddedWorkflowInfo:
    """Create an EmbeddedWorkflowInfo with the given context for testing."""
    return EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=post_steps or [],
        context=ctx,
        workflow_name="test",
    )


def _make_step(
    name: str,
    output_properties: dict[str, dict[str, str]] | None = None,
) -> WorkflowStep:
    """Create a WorkflowStep with an optional OutputSpec."""
    output = None
    if output_properties is not None:
        output = OutputSpec(
            type="json_schema",
            schema={"properties": output_properties},
        )
    return WorkflowStep(name=name, output=output)


def test_empty_list_returns_none_and_empty_dict() -> None:
    """Empty list returns (None, {})."""
    diff_path, meta = _collect_embedded_post_step_outputs([])
    assert diff_path is None
    assert meta == {}


def test_extracts_diff_path_from_output_spec() -> None:
    """Extracts diff_path from path-typed field via OutputSpec."""
    step = _make_step("create_cl", {"diff_path": {"type": "path"}})
    ctx: dict[str, object] = {
        "create_cl": {"diff_path": "/tmp/test.diff", "other_key": "val"}
    }
    diff_path, meta = _collect_embedded_post_step_outputs(
        [_make_info(ctx, post_steps=[step])]
    )
    assert diff_path == "/tmp/test.diff"


def test_extracts_generic_path_field_from_output_spec() -> None:
    """Extracts a generic path-typed field (not named diff_path) via OutputSpec."""
    step = _make_step("create_cl", {"proposal_path": {"type": "path"}})
    ctx: dict[str, object] = {"create_cl": {"proposal_path": "/tmp/proposal.diff"}}
    diff_path, meta = _collect_embedded_post_step_outputs(
        [_make_info(ctx, post_steps=[step])]
    )
    assert diff_path == "/tmp/proposal.diff"


def test_extracts_meta_fields_from_context() -> None:
    """Extracts meta_* fields from post-step context values."""
    step = _make_step("report")
    ctx: dict[str, object] = {
        "report": {"meta_new_cl": "http://cl/123", "meta_status": "ok"}
    }
    diff_path, meta = _collect_embedded_post_step_outputs(
        [_make_info(ctx, post_steps=[step])]
    )
    assert diff_path is None
    assert meta == {"meta_new_cl": "http://cl/123", "meta_status": "ok"}


def test_first_diff_path_wins_across_workflows() -> None:
    """First non-empty path-typed field wins across multiple workflows."""
    step1 = _make_step("step", {"diff_path": {"type": "path"}})
    step2 = _make_step("step", {"diff_path": {"type": "path"}})
    ctx1: dict[str, object] = {"step": {"diff_path": "/tmp/first.diff"}}
    ctx2: dict[str, object] = {"step": {"diff_path": "/tmp/second.diff"}}
    diff_path, meta = _collect_embedded_post_step_outputs(
        [_make_info(ctx1, post_steps=[step1]), _make_info(ctx2, post_steps=[step2])]
    )
    assert diff_path == "/tmp/first.diff"


def test_non_dict_values_ignored() -> None:
    """Non-dict context values are silently ignored."""
    step1 = _make_step("some_string")
    step2 = _make_step("some_int")
    step3 = _make_step("some_none")
    ctx: dict[str, object] = {
        "some_string": "hello",
        "some_int": 42,
        "some_none": None,
    }
    diff_path, meta = _collect_embedded_post_step_outputs(
        [_make_info(ctx, post_steps=[step1, step2, step3])]
    )
    assert diff_path is None
    assert meta == {}


def test_empty_falsy_meta_values_excluded() -> None:
    """Empty/falsy meta_* values are not included."""
    step = _make_step("step")
    ctx: dict[str, object] = {
        "step": {"meta_empty": "", "meta_none": None, "meta_zero": 0}
    }
    diff_path, meta = _collect_embedded_post_step_outputs(
        [_make_info(ctx, post_steps=[step])]
    )
    assert diff_path is None
    assert meta == {}


def test_empty_diff_path_ignored() -> None:
    """Empty string path value is treated as absent."""
    step = _make_step("step", {"diff_path": {"type": "path"}})
    ctx: dict[str, object] = {"step": {"diff_path": ""}}
    diff_path, meta = _collect_embedded_post_step_outputs(
        [_make_info(ctx, post_steps=[step])]
    )
    assert diff_path is None


def test_no_output_spec_skips_path_extraction() -> None:
    """Steps without OutputSpec skip path extraction but still collect meta."""
    step = _make_step("step")  # No output spec
    ctx: dict[str, object] = {"step": {"diff_path": "/tmp/test.diff", "meta_id": "abc"}}
    diff_path, meta = _collect_embedded_post_step_outputs(
        [_make_info(ctx, post_steps=[step])]
    )
    assert diff_path is None
    assert meta == {"meta_id": "abc"}


def test_step_not_in_context_skipped() -> None:
    """Steps whose name isn't in context are silently skipped."""
    step = _make_step("missing_step", {"path_field": {"type": "path"}})
    ctx: dict[str, object] = {}
    diff_path, meta = _collect_embedded_post_step_outputs(
        [_make_info(ctx, post_steps=[step])]
    )
    assert diff_path is None
    assert meta == {}
