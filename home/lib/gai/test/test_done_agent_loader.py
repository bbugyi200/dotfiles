"""Tests for load_done_agents reading step_output from done.json."""

import json
from pathlib import Path
from unittest.mock import patch

from ace.tui.models._loaders import load_done_agents
from axe_run_agent_runner import _extract_step_output_and_diff_path


def test_load_done_agents_reads_step_output(tmp_path: Path) -> None:
    """Verify load_done_agents populates step_output from done.json."""
    # Create project structure: <tmp>/testproj/artifacts/ace-run/20260101120000/
    project_dir = tmp_path / "testproj"
    artifact_dir = project_dir / "artifacts" / "ace-run" / "20260101120000"
    artifact_dir.mkdir(parents=True)

    done_data = {
        "cl_name": "my_cl",
        "project_file": "/fake/path.gp",
        "timestamp": "20260101_120000",
        "artifacts_timestamp": "20260101120000",
        "response_path": "/tmp/response.md",
        "outcome": "completed",
        "workspace_num": 1,
        "diff_path": "/tmp/proposal.diff",
        "step_output": {"meta_proposal_id": "abc123"},
    }
    with open(artifact_dir / "done.json", "w", encoding="utf-8") as f:
        json.dump(done_data, f)

    # Set up the directory structure under .gai/projects/
    gai_dir = tmp_path / ".gai" / "projects" / "testproj"
    gai_dir.mkdir(parents=True)
    # Symlink artifacts into the expected location
    (gai_dir / "artifacts").symlink_to(project_dir / "artifacts")

    with patch(
        "ace.tui.models._loaders._artifact_loaders.Path.home", return_value=tmp_path
    ):
        agents = load_done_agents({}, {})

    assert len(agents) == 1
    agent = agents[0]
    assert agent.diff_path == "/tmp/proposal.diff"
    assert agent.step_output == {"meta_proposal_id": "abc123"}
    assert agent.cl_name == "my_cl"


def test_load_done_agents_without_step_output(tmp_path: Path) -> None:
    """Verify load_done_agents works when step_output is absent from done.json."""
    gai_dir = tmp_path / ".gai" / "projects" / "testproj"
    artifact_dir = gai_dir / "artifacts" / "ace-run" / "20260101120000"
    artifact_dir.mkdir(parents=True)

    done_data = {
        "cl_name": "my_cl",
        "project_file": "/fake/path.gp",
        "timestamp": "20260101_120000",
        "artifacts_timestamp": "20260101120000",
        "response_path": "/tmp/response.md",
        "outcome": "completed",
        "workspace_num": 1,
    }
    with open(artifact_dir / "done.json", "w", encoding="utf-8") as f:
        json.dump(done_data, f)

    with patch(
        "ace.tui.models._loaders._artifact_loaders.Path.home", return_value=tmp_path
    ):
        agents = load_done_agents({}, {})

    assert len(agents) == 1
    agent = agents[0]
    assert agent.step_output is None
    assert agent.diff_path is None


def test_extract_step_output_from_workflow_state(tmp_path: Path) -> None:
    """Verify _extract_step_output_and_diff_path reads workflow_state.json."""
    state_data = {
        "workflow_name": "test",
        "status": "completed",
        "steps": [
            {
                "name": "step1",
                "status": "completed",
                "output": {"meta_id": "abc123", "result": "ok"},
                "output_types": {"meta_id": "text", "result": "text"},
            }
        ],
    }
    state_path = tmp_path / "workflow_state.json"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state_data, f)

    step_output, diff_path = _extract_step_output_and_diff_path(str(tmp_path))

    assert step_output == {"meta_id": "abc123", "result": "ok"}
    assert diff_path is None


def test_extract_diff_path_from_output_types(tmp_path: Path) -> None:
    """Verify diff_path is extracted from path-typed output in last step only."""
    state_data = {
        "workflow_name": "test",
        "status": "completed",
        "steps": [
            {
                "name": "step1",
                "status": "completed",
                "output": {"ignored_path": "/tmp/early.patch"},
                "output_types": {"ignored_path": "path"},
            },
            {
                "name": "step2",
                "status": "completed",
                "output": {"proposal_path": "/tmp/diff.patch"},
                "output_types": {"proposal_path": "path"},
            },
        ],
    }
    state_path = tmp_path / "workflow_state.json"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state_data, f)

    step_output, diff_path = _extract_step_output_and_diff_path(str(tmp_path))

    assert step_output == {"proposal_path": "/tmp/diff.patch"}
    assert diff_path == "/tmp/diff.patch"


def test_extract_diff_path_last_step_multiple_paths_first_wins(
    tmp_path: Path,
) -> None:
    """Verify first path-typed output wins when last step has multiple."""
    state_data = {
        "workflow_name": "test",
        "status": "completed",
        "steps": [
            {
                "name": "step1",
                "status": "completed",
                "output": {
                    "first_path": "/tmp/first.patch",
                    "second_path": "/tmp/second.patch",
                },
                "output_types": {"first_path": "path", "second_path": "path"},
            }
        ],
    }
    state_path = tmp_path / "workflow_state.json"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state_data, f)

    _step_output, diff_path = _extract_step_output_and_diff_path(str(tmp_path))

    assert diff_path == "/tmp/first.patch"


def test_extract_diff_path_not_from_non_last_step(tmp_path: Path) -> None:
    """Verify path output in non-last step is NOT extracted."""
    state_data = {
        "workflow_name": "test",
        "status": "completed",
        "steps": [
            {
                "name": "step1",
                "status": "completed",
                "output": {"proposal_path": "/tmp/diff.patch"},
                "output_types": {"proposal_path": "path"},
            },
            {
                "name": "step2",
                "status": "completed",
                "output": {"result": "ok"},
                "output_types": {"result": "text"},
            },
        ],
    }
    state_path = tmp_path / "workflow_state.json"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state_data, f)

    step_output, diff_path = _extract_step_output_and_diff_path(str(tmp_path))

    assert step_output == {"result": "ok"}
    assert diff_path is None


def test_extract_diff_path_fallback_to_direct_key(tmp_path: Path) -> None:
    """Verify diff_path fallback reads direct diff_path key from last step output."""
    state_data = {
        "workflow_name": "test",
        "status": "completed",
        "steps": [
            {
                "name": "step1",
                "status": "completed",
                "output": {"diff_path": "/tmp/changes.diff"},
            }
        ],
    }
    state_path = tmp_path / "workflow_state.json"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state_data, f)

    _step_output, diff_path = _extract_step_output_and_diff_path(str(tmp_path))

    assert diff_path == "/tmp/changes.diff"


def test_extract_diff_path_fallback_ignores_non_last_step(tmp_path: Path) -> None:
    """Verify diff_path fallback only checks the last step."""
    state_data = {
        "workflow_name": "test",
        "status": "completed",
        "steps": [
            {
                "name": "step1",
                "status": "completed",
                "output": {"diff_path": "/tmp/early.diff"},
            },
            {
                "name": "step2",
                "status": "completed",
                "output": {"result": "ok"},
            },
        ],
    }
    state_path = tmp_path / "workflow_state.json"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state_data, f)

    _step_output, diff_path = _extract_step_output_and_diff_path(str(tmp_path))

    assert diff_path is None


def test_extract_returns_none_without_workflow_state(tmp_path: Path) -> None:
    """Verify graceful handling when workflow_state.json doesn't exist."""
    step_output, diff_path = _extract_step_output_and_diff_path(str(tmp_path))

    assert step_output is None
    assert diff_path is None
