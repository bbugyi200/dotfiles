"""Tests for _load_embedded_workflows step-specific file resolution."""

import json
from pathlib import Path

from ace.tui.widgets.prompt_panel import _load_embedded_workflows


def _make_agent(artifacts_dir: str | None, step_name: str | None = None) -> object:
    """Create a minimal mock agent for testing _load_embedded_workflows."""

    class _MockAgent:
        def __init__(self, artifacts_dir: str | None, step_name: str | None) -> None:
            self.step_name = step_name
            self._artifacts_dir = artifacts_dir

        def get_artifacts_dir(self) -> str | None:
            return self._artifacts_dir

    return _MockAgent(artifacts_dir, step_name)


def test_step_specific_file_takes_priority(tmp_path: Path) -> None:
    """Step-specific file is preferred over the shared file."""
    shared_data = [{"name": "propose", "args": {}}]
    step_data = [{"name": "commit", "args": {"name": "add_foobar_field"}}]

    shared_file = tmp_path / "embedded_workflows.json"
    shared_file.write_text(json.dumps(shared_data))

    step_file = tmp_path / "embedded_workflows_create_commit.json"
    step_file.write_text(json.dumps(step_data))

    agent = _make_agent(str(tmp_path), step_name="create_commit")
    result = _load_embedded_workflows(agent)  # type: ignore[arg-type]
    assert result == step_data


def test_falls_back_to_shared_when_step_file_missing(tmp_path: Path) -> None:
    """Falls back to shared file when step-specific file doesn't exist."""
    shared_data = [{"name": "propose", "args": {}}]
    shared_file = tmp_path / "embedded_workflows.json"
    shared_file.write_text(json.dumps(shared_data))

    agent = _make_agent(str(tmp_path), step_name="create_commit")
    result = _load_embedded_workflows(agent)  # type: ignore[arg-type]
    assert result == shared_data


def test_falls_back_to_shared_when_step_name_is_none(tmp_path: Path) -> None:
    """Falls back to shared file when agent.step_name is None."""
    shared_data = [{"name": "propose", "args": {}}]
    shared_file = tmp_path / "embedded_workflows.json"
    shared_file.write_text(json.dumps(shared_data))

    agent = _make_agent(str(tmp_path), step_name=None)
    result = _load_embedded_workflows(agent)  # type: ignore[arg-type]
    assert result == shared_data


def test_returns_none_when_no_artifacts_dir() -> None:
    """Returns None when artifacts_dir is None."""
    agent = _make_agent(None, step_name="create_commit")
    result = _load_embedded_workflows(agent)  # type: ignore[arg-type]
    assert result is None
