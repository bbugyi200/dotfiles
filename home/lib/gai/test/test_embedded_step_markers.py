"""Tests for embedded workflow step marker writing in axe_run_agent_runner."""

import json
from typing import Any

from axe_run_agent_runner import _write_embedded_step_markers, _write_step_marker
from main.query_handler._query import EmbeddedWorkflowResult
from xprompt.workflow_models import WorkflowStep


def _make_bash_step(name: str) -> WorkflowStep:
    """Create a simple bash WorkflowStep for testing."""
    return WorkflowStep(name=name, bash=f'echo "{name}=done"')


def _make_python_step(name: str) -> WorkflowStep:
    """Create a simple python WorkflowStep for testing."""
    return WorkflowStep(name=name, python=f'print("{name}=done")')


def _make_prompt_step(name: str) -> WorkflowStep:
    """Create a simple prompt WorkflowStep for testing."""
    return WorkflowStep(name=name, prompt=f"Do {name}")


def test_write_step_marker_creates_valid_json(tmp_path: Any) -> None:
    """Test that _write_step_marker creates a valid JSON file with expected fields."""
    step = _make_bash_step("check_files")
    artifacts_dir = str(tmp_path)

    _write_step_marker(
        artifacts_dir=artifacts_dir,
        workflow_name="propose",
        step=step,
        status="completed",
        step_index=2,
        total_steps=5,
        is_pre_prompt_step=False,
        output={"result": "ok"},
    )

    marker_path = tmp_path / "prompt_step_check_files.json"
    assert marker_path.exists()

    with open(marker_path, encoding="utf-8") as f:
        data = json.load(f)

    assert data["workflow_name"] == "propose"
    assert data["step_name"] == "check_files"
    assert data["status"] == "completed"
    assert data["output"] == {"result": "ok"}
    assert data["step_index"] == 2
    assert data["total_steps"] == 5
    assert data["is_pre_prompt_step"] is False
    assert data["step_type"] == "bash"
    assert data["step_source"] == 'echo "check_files=done"'
    assert data["error"] is None
    assert data["hidden"] is False
    assert data["embedded_workflow_name"] is None


def test_write_step_marker_python_step_type(tmp_path: Any) -> None:
    """Test that python steps get step_type='python'."""
    step = _make_python_step("validate")
    _write_step_marker(
        artifacts_dir=str(tmp_path),
        workflow_name="test_wf",
        step=step,
        status="completed",
        step_index=0,
        total_steps=1,
        is_pre_prompt_step=True,
    )

    marker_path = tmp_path / "prompt_step_validate.json"
    with open(marker_path, encoding="utf-8") as f:
        data = json.load(f)

    assert data["step_type"] == "python"
    assert data["step_source"] == 'print("validate=done")'


def test_write_step_marker_prompt_step_type(tmp_path: Any) -> None:
    """Test that prompt steps get step_type='prompt'."""
    step = _make_prompt_step("review")
    _write_step_marker(
        artifacts_dir=str(tmp_path),
        workflow_name="test_wf",
        step=step,
        status="completed",
        step_index=0,
        total_steps=1,
        is_pre_prompt_step=False,
    )

    marker_path = tmp_path / "prompt_step_review.json"
    with open(marker_path, encoding="utf-8") as f:
        data = json.load(f)

    assert data["step_type"] == "prompt"
    assert data["step_source"] is None


def test_write_step_marker_with_error(tmp_path: Any) -> None:
    """Test that error messages are written correctly."""
    step = _make_bash_step("deploy")
    _write_step_marker(
        artifacts_dir=str(tmp_path),
        workflow_name="deploy_wf",
        step=step,
        status="failed",
        step_index=1,
        total_steps=3,
        is_pre_prompt_step=False,
        error="Command exited with code 1",
    )

    marker_path = tmp_path / "prompt_step_deploy.json"
    with open(marker_path, encoding="utf-8") as f:
        data = json.load(f)

    assert data["status"] == "failed"
    assert data["error"] == "Command exited with code 1"


def test_write_embedded_step_markers_pre_and_post(tmp_path: Any) -> None:
    """Test that pre-steps and post-steps get correct markers."""
    pre_step = _make_bash_step("setup")
    post_step = _make_bash_step("cleanup")

    ewf = EmbeddedWorkflowResult(
        workflow_name="propose",
        pre_steps=[pre_step],
        post_steps=[post_step],
        context={
            "setup": {"status": "ok"},
            "cleanup": {"result": "done"},
        },
        prompt_part_index=1,
        total_workflow_steps=3,
    )

    _write_embedded_step_markers(str(tmp_path), [ewf])

    # Check pre-step marker (namespaced by embedded workflow name)
    pre_marker = tmp_path / "prompt_step_propose__setup.json"
    assert pre_marker.exists()
    with open(pre_marker, encoding="utf-8") as f:
        pre_data = json.load(f)
    assert pre_data["step_index"] == 0
    assert pre_data["is_pre_prompt_step"] is True
    assert pre_data["status"] == "completed"
    assert pre_data["total_steps"] == 3
    assert pre_data["embedded_workflow_name"] == "propose"

    # Check post-step marker (namespaced by embedded workflow name)
    post_marker = tmp_path / "prompt_step_propose__cleanup.json"
    assert post_marker.exists()
    with open(post_marker, encoding="utf-8") as f:
        post_data = json.load(f)
    assert post_data["step_index"] == 2  # prompt_part_index(1) + 1 + 0
    assert post_data["is_pre_prompt_step"] is False
    assert post_data["status"] == "completed"
    assert post_data["total_steps"] == 3
    assert post_data["embedded_workflow_name"] == "propose"


def test_step_numbering_uses_prompt_part_index_offset(tmp_path: Any) -> None:
    """Test that post-step indices use prompt_part_index as offset."""
    post_steps = [
        _make_bash_step("step_a"),
        _make_bash_step("step_b"),
        _make_bash_step("step_c"),
    ]

    ewf = EmbeddedWorkflowResult(
        workflow_name="multi_step",
        pre_steps=[],
        post_steps=post_steps,
        context={
            "step_a": {"done": True},
            "step_b": {"done": True},
            "step_c": {"done": True},
        },
        prompt_part_index=2,  # prompt_part is at index 2
        total_workflow_steps=6,
    )

    _write_embedded_step_markers(str(tmp_path), [ewf])

    # step_a should be at index 3 (prompt_part_index=2 + 1 + 0)
    with open(tmp_path / "prompt_step_multi_step__step_a.json", encoding="utf-8") as f:
        assert json.load(f)["step_index"] == 3

    # step_b should be at index 4 (prompt_part_index=2 + 1 + 1)
    with open(tmp_path / "prompt_step_multi_step__step_b.json", encoding="utf-8") as f:
        assert json.load(f)["step_index"] == 4

    # step_c should be at index 5 (prompt_part_index=2 + 1 + 2)
    with open(tmp_path / "prompt_step_multi_step__step_c.json", encoding="utf-8") as f:
        assert json.load(f)["step_index"] == 5


def test_failed_post_step_status(tmp_path: Any) -> None:
    """Test that missing context entries result in 'failed' status."""
    post_step = _make_bash_step("deploy")

    ewf = EmbeddedWorkflowResult(
        workflow_name="propose",
        pre_steps=[],
        post_steps=[post_step],
        context={},  # deploy not in context → failed
        prompt_part_index=0,
        total_workflow_steps=2,
    )

    _write_embedded_step_markers(str(tmp_path), [ewf])

    marker_path = tmp_path / "prompt_step_propose__deploy.json"
    with open(marker_path, encoding="utf-8") as f:
        data = json.load(f)

    assert data["status"] == "failed"
    assert data["output"] is None


def test_multiple_embedded_workflows(tmp_path: Any) -> None:
    """Test markers for multiple embedded workflows in one query."""
    ewf1 = EmbeddedWorkflowResult(
        workflow_name="propose",
        pre_steps=[_make_bash_step("gather_info")],
        post_steps=[_make_bash_step("apply_changes")],
        context={
            "gather_info": {"info": "collected"},
            "apply_changes": {"diff_path": "/tmp/diff"},
        },
        prompt_part_index=1,
        total_workflow_steps=3,
    )
    ewf2 = EmbeddedWorkflowResult(
        workflow_name="review",
        pre_steps=[],
        post_steps=[_make_bash_step("send_review")],
        context={"send_review": {"status": "sent"}},
        prompt_part_index=0,
        total_workflow_steps=2,
    )

    _write_embedded_step_markers(str(tmp_path), [ewf1, ewf2])

    # All 3 marker files should exist (namespaced by embedded workflow name)
    assert (tmp_path / "prompt_step_propose__gather_info.json").exists()
    assert (tmp_path / "prompt_step_propose__apply_changes.json").exists()
    assert (tmp_path / "prompt_step_review__send_review.json").exists()


def test_pre_step_numbering_with_multiple_pre_steps(tmp_path: Any) -> None:
    """Test that multiple pre-steps get sequential indices starting from 0."""
    pre_steps = [
        _make_bash_step("init"),
        _make_bash_step("validate"),
    ]

    ewf = EmbeddedWorkflowResult(
        workflow_name="propose",
        pre_steps=pre_steps,
        post_steps=[],
        context={
            "init": {"ok": True},
            "validate": {"ok": True},
        },
        prompt_part_index=2,
        total_workflow_steps=3,
    )

    _write_embedded_step_markers(str(tmp_path), [ewf])

    with open(tmp_path / "prompt_step_propose__init.json", encoding="utf-8") as f:
        assert json.load(f)["step_index"] == 0

    with open(tmp_path / "prompt_step_propose__validate.json", encoding="utf-8") as f:
        assert json.load(f)["step_index"] == 1


def test_multiple_embedded_workflows_no_name_collision(tmp_path: Any) -> None:
    """Test that two workflows with same-named steps don't overwrite each other."""
    ewf_commit = EmbeddedWorkflowResult(
        workflow_name="commit",
        pre_steps=[_make_bash_step("check_changes")],
        post_steps=[_make_bash_step("save_response"), _make_bash_step("report")],
        context={
            "check_changes": {"has_changes": True},
            "save_response": {"path": "/tmp/commit_resp"},
            "report": {"status": "ok"},
        },
        prompt_part_index=1,
        total_workflow_steps=4,
    )
    ewf_propose = EmbeddedWorkflowResult(
        workflow_name="propose",
        pre_steps=[_make_bash_step("check_changes")],
        post_steps=[_make_bash_step("save_response"), _make_bash_step("report")],
        context={
            "check_changes": {"has_changes": False},
            "save_response": {"path": "/tmp/propose_resp"},
            "report": {"status": "skipped"},
        },
        prompt_part_index=1,
        total_workflow_steps=4,
    )

    _write_embedded_step_markers(str(tmp_path), [ewf_commit, ewf_propose])

    # Both workflows' markers should exist (no overwrites)
    assert (tmp_path / "prompt_step_commit__check_changes.json").exists()
    assert (tmp_path / "prompt_step_commit__save_response.json").exists()
    assert (tmp_path / "prompt_step_commit__report.json").exists()
    assert (tmp_path / "prompt_step_propose__check_changes.json").exists()
    assert (tmp_path / "prompt_step_propose__save_response.json").exists()
    assert (tmp_path / "prompt_step_propose__report.json").exists()

    # Verify content is distinct (not overwritten)
    with open(
        tmp_path / "prompt_step_commit__check_changes.json", encoding="utf-8"
    ) as f:
        commit_data = json.load(f)
    with open(
        tmp_path / "prompt_step_propose__check_changes.json", encoding="utf-8"
    ) as f:
        propose_data = json.load(f)

    assert commit_data["output"]["has_changes"] is True
    assert propose_data["output"]["has_changes"] is False
    assert commit_data["embedded_workflow_name"] == "commit"
    assert propose_data["embedded_workflow_name"] == "propose"
