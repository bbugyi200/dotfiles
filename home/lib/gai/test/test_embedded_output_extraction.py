"""Tests for _extract_embedded_outputs() in axe_run_agent_runner."""

from axe_run_agent_runner import _extract_embedded_outputs


def test_empty_post_workflows() -> None:
    """Empty post_workflows returns (None, {})."""
    diff_path, meta = _extract_embedded_outputs([])
    assert diff_path is None
    assert meta == {}


def test_normal_propose_context() -> None:
    """Extracts diff_path and meta_proposal_id from a propose workflow context."""
    ctx: dict[str, object] = {
        "propose_step": {
            "diff_path": "/tmp/proposal.diff",
            "meta_proposal_id": "abc123",
        }
    }
    diff_path, meta = _extract_embedded_outputs([([], ctx)])
    assert diff_path == "/tmp/proposal.diff"
    assert meta == {"meta_proposal_id": "abc123"}


def test_skipped_steps_empty_dicts() -> None:
    """Steps with empty output dicts produce (None, {})."""
    ctx: dict[str, object] = {"step1": {}, "step2": {}}
    diff_path, meta = _extract_embedded_outputs([([], ctx)])
    assert diff_path is None
    assert meta == {}


def test_non_dict_values_ignored() -> None:
    """Non-dict context values are silently ignored."""
    ctx: dict[str, object] = {
        "some_string": "hello",
        "some_int": 42,
        "some_none": None,
    }
    diff_path, meta = _extract_embedded_outputs([([], ctx)])
    assert diff_path is None
    assert meta == {}


def test_empty_diff_path_ignored() -> None:
    """Empty string diff_path is treated as absent."""
    ctx: dict[str, object] = {"step": {"diff_path": ""}}
    diff_path, meta = _extract_embedded_outputs([([], ctx)])
    assert diff_path is None


def test_empty_meta_values_ignored() -> None:
    """Empty/falsy meta_* values are not included."""
    ctx: dict[str, object] = {
        "step": {"meta_empty": "", "meta_none": None, "meta_zero": 0}
    }
    diff_path, meta = _extract_embedded_outputs([([], ctx)])
    assert diff_path is None
    assert meta == {}


def test_multiple_embedded_workflows_last_diff_path_wins() -> None:
    """With multiple workflows, last non-empty diff_path wins and meta fields merge."""
    ctx1: dict[str, object] = {
        "step": {
            "diff_path": "/tmp/first.diff",
            "meta_proposal_id": "id1",
        }
    }
    ctx2: dict[str, object] = {
        "step": {
            "diff_path": "/tmp/second.diff",
            "meta_review_id": "rev1",
        }
    }
    diff_path, meta = _extract_embedded_outputs([([], ctx1), ([], ctx2)])
    assert diff_path == "/tmp/second.diff"
    assert meta == {"meta_proposal_id": "id1", "meta_review_id": "rev1"}


def test_partial_context_after_failure() -> None:
    """Extracts outputs from steps that completed before a later step failed.

    Simulates a post-step workflow where early steps populated the context
    (diff_path, meta_proposal_id) but a later step failed. The context dict
    still contains the values from completed steps, so _extract_embedded_outputs
    should find them.
    """
    # Early steps populated these values; later step failed before adding more
    ctx: dict[str, object] = {
        "save_response": {"saved": True},
        "create_proposal": {
            "diff_path": "/tmp/partial.diff",
            "meta_proposal_id": "partial-123",
        },
        # "report" step would have added meta_report_url but failed
    }
    diff_path, meta = _extract_embedded_outputs([([], ctx)])
    assert diff_path == "/tmp/partial.diff"
    assert meta == {"meta_proposal_id": "partial-123"}
