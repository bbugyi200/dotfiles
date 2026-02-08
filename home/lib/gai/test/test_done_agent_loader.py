"""Tests for load_done_agents reading step_output from done.json."""

import json
from pathlib import Path
from unittest.mock import patch

from ace.tui.models._loaders import load_done_agents


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

    with patch("ace.tui.models._loaders.Path.home", return_value=tmp_path):
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

    with patch("ace.tui.models._loaders.Path.home", return_value=tmp_path):
        agents = load_done_agents({}, {})

    assert len(agents) == 1
    agent = agents[0]
    assert agent.step_output is None
    assert agent.diff_path is None
