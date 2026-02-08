"""Tests for _collect_embedded_post_step_outputs() in workflow_executor_steps_prompt."""

from xprompt.workflow_executor_steps_embedded import EmbeddedWorkflowInfo
from xprompt.workflow_executor_steps_prompt import _collect_embedded_post_step_outputs


def _make_info(ctx: dict[str, object]) -> EmbeddedWorkflowInfo:
    """Create an EmbeddedWorkflowInfo with the given context for testing."""
    return EmbeddedWorkflowInfo(
        pre_steps=[],
        post_steps=[],
        context=ctx,
        workflow_name="test",
    )


def test_empty_list_returns_none_and_empty_dict() -> None:
    """Empty list returns (None, {})."""
    diff_path, meta = _collect_embedded_post_step_outputs([])
    assert diff_path is None
    assert meta == {}


def test_extracts_diff_path_from_context() -> None:
    """Extracts diff_path from context values."""
    ctx: dict[str, object] = {
        "create_cl": {"diff_path": "/tmp/test.diff", "other_key": "val"}
    }
    diff_path, meta = _collect_embedded_post_step_outputs([_make_info(ctx)])
    assert diff_path == "/tmp/test.diff"


def test_extracts_meta_fields_from_context() -> None:
    """Extracts meta_* fields from context values."""
    ctx: dict[str, object] = {
        "report": {"meta_new_cl": "http://cl/123", "meta_status": "ok"}
    }
    diff_path, meta = _collect_embedded_post_step_outputs([_make_info(ctx)])
    assert diff_path is None
    assert meta == {"meta_new_cl": "http://cl/123", "meta_status": "ok"}


def test_last_diff_path_wins_across_workflows() -> None:
    """Last non-empty diff_path wins across multiple workflows."""
    ctx1: dict[str, object] = {"step": {"diff_path": "/tmp/first.diff"}}
    ctx2: dict[str, object] = {"step": {"diff_path": "/tmp/second.diff"}}
    diff_path, meta = _collect_embedded_post_step_outputs(
        [_make_info(ctx1), _make_info(ctx2)]
    )
    assert diff_path == "/tmp/second.diff"


def test_non_dict_values_ignored() -> None:
    """Non-dict context values are silently ignored."""
    ctx: dict[str, object] = {
        "some_string": "hello",
        "some_int": 42,
        "some_none": None,
    }
    diff_path, meta = _collect_embedded_post_step_outputs([_make_info(ctx)])
    assert diff_path is None
    assert meta == {}


def test_empty_falsy_meta_values_excluded() -> None:
    """Empty/falsy meta_* values are not included."""
    ctx: dict[str, object] = {
        "step": {"meta_empty": "", "meta_none": None, "meta_zero": 0}
    }
    diff_path, meta = _collect_embedded_post_step_outputs([_make_info(ctx)])
    assert diff_path is None
    assert meta == {}


def test_empty_diff_path_ignored() -> None:
    """Empty string diff_path is treated as absent."""
    ctx: dict[str, object] = {"step": {"diff_path": ""}}
    diff_path, meta = _collect_embedded_post_step_outputs([_make_info(ctx)])
    assert diff_path is None
