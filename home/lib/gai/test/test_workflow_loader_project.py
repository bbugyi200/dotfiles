"""Tests for project-based workflow loading in workflow_loader."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from xprompt.workflow_loader import (
    _load_workflow_from_file,
    get_all_workflows,
)
from xprompt.workflow_models import Workflow


def _load_workflows_from_project_with_base(
    project: str, base_config_dir: Path
) -> dict[str, Workflow]:
    """Helper to test project loading with a custom base directory.

    This replicates the logic of _load_workflows_from_project but allows
    specifying a custom base directory for testing.
    """
    project_dir = base_config_dir / ".config" / "gai" / "xprompts" / project
    if not project_dir.is_dir():
        return {}

    workflows: dict[str, Workflow] = {}
    for yml_file in project_dir.glob("*.yml"):
        if yml_file.is_file():
            workflow = _load_workflow_from_file(yml_file)
            if workflow:
                namespaced_name = f"{project}/{workflow.name}"
                workflows[namespaced_name] = Workflow(
                    name=namespaced_name,
                    inputs=workflow.inputs,
                    steps=workflow.steps,
                    source_path=workflow.source_path,
                )

    for yaml_file in project_dir.glob("*.yaml"):
        if yaml_file.is_file():
            workflow = _load_workflow_from_file(yaml_file)
            if workflow:
                namespaced_name = f"{project}/{workflow.name}"
                if namespaced_name not in workflows:  # .yml takes precedence
                    workflows[namespaced_name] = Workflow(
                        name=namespaced_name,
                        inputs=workflow.inputs,
                        steps=workflow.steps,
                        source_path=workflow.source_path,
                    )
    return workflows


def test_load_workflows_from_project_basic() -> None:
    """Test loading workflows from a project-specific directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_dir = Path(tmp_dir) / ".config" / "gai" / "xprompts" / "testproj"
        project_dir.mkdir(parents=True)

        # Create a workflow file
        workflow_content = """
steps:
  - name: step1
    bash: echo "Hello from project workflow"
"""
        (project_dir / "my_workflow.yml").write_text(workflow_content)

        workflows = _load_workflows_from_project_with_base("testproj", Path(tmp_dir))

        assert len(workflows) == 1
        assert "testproj/my_workflow" in workflows
        assert workflows["testproj/my_workflow"].name == "testproj/my_workflow"
        assert len(workflows["testproj/my_workflow"].steps) == 1
        assert (
            workflows["testproj/my_workflow"].steps[0].bash
            == 'echo "Hello from project workflow"'
        )


def test_load_workflows_from_project_nonexistent_dir() -> None:
    """Test that nonexistent project directory returns empty dict."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workflows = _load_workflows_from_project_with_base(
            "nonexistent_project", Path(tmp_dir)
        )
        assert workflows == {}


def test_load_workflows_from_project_yml_precedence_over_yaml() -> None:
    """Test that .yml files take precedence over .yaml files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_dir = Path(tmp_dir) / ".config" / "gai" / "xprompts" / "testproj"
        project_dir.mkdir(parents=True)

        # Create both .yml and .yaml with same name
        yml_content = """
steps:
  - name: step1
    bash: echo "From .yml"
"""
        yaml_content = """
steps:
  - name: step1
    bash: echo "From .yaml"
"""
        (project_dir / "duplicate.yml").write_text(yml_content)
        (project_dir / "duplicate.yaml").write_text(yaml_content)

        workflows = _load_workflows_from_project_with_base("testproj", Path(tmp_dir))

        assert len(workflows) == 1
        assert "testproj/duplicate" in workflows
        # .yml should win
        assert workflows["testproj/duplicate"].steps[0].bash == 'echo "From .yml"'


def test_load_workflows_from_project_with_inputs() -> None:
    """Test that project workflows preserve inputs."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_dir = Path(tmp_dir) / ".config" / "gai" / "xprompts" / "myproj"
        project_dir.mkdir(parents=True)

        content = """
input:
  target: word
steps:
  - name: greet
    bash: echo "Hello {{ target }}"
"""
        (project_dir / "greet_workflow.yml").write_text(content)

        workflows = _load_workflows_from_project_with_base("myproj", Path(tmp_dir))

        assert len(workflows) == 1
        assert "myproj/greet_workflow" in workflows
        wf = workflows["myproj/greet_workflow"]
        assert wf.name == "myproj/greet_workflow"
        assert len(wf.inputs) == 1
        assert wf.inputs[0].name == "target"


def test_get_all_workflows_with_project_includes_project_workflows() -> None:
    """Test that get_all_workflows with project param includes project workflows."""
    mock_workflow = Workflow(
        name="testproj/proj_workflow",
        inputs=[],
        steps=[],
        source_path="/test/path.yml",
    )

    with (
        patch("xprompt.workflow_loader._load_workflows_from_files", return_value={}),
        patch("xprompt.workflow_loader._load_workflows_from_internal", return_value={}),
        patch(
            "xprompt.workflow_loader._load_workflows_from_project",
            return_value={"testproj/proj_workflow": mock_workflow},
        ),
    ):
        workflows = get_all_workflows(project="testproj")

    assert "testproj/proj_workflow" in workflows


def test_get_all_workflows_without_project_excludes_project_workflows() -> None:
    """Test that get_all_workflows without project param doesn't load project workflows."""
    with (
        patch("xprompt.workflow_loader._load_workflows_from_files", return_value={}),
        patch("xprompt.workflow_loader._load_workflows_from_internal", return_value={}),
        patch(
            "xprompt.workflow_loader._load_workflows_from_project"
        ) as mock_load_project,
    ):
        get_all_workflows()  # No project param

    # Should not have called _load_workflows_from_project
    mock_load_project.assert_not_called()


def test_get_all_workflows_file_overrides_project() -> None:
    """Test that file-based workflows override project workflows."""
    project_workflow = Workflow(
        name="test",
        inputs=[],
        steps=[],
        source_path="/project/test.yml",
    )
    file_workflow = Workflow(
        name="test",
        inputs=[],
        steps=[],
        source_path="/file/test.yml",
    )

    with (
        patch(
            "xprompt.workflow_loader._load_workflows_from_files",
            return_value={"test": file_workflow},
        ),
        patch("xprompt.workflow_loader._load_workflows_from_internal", return_value={}),
        patch(
            "xprompt.workflow_loader._load_workflows_from_project",
            return_value={"test": project_workflow},
        ),
    ):
        workflows = get_all_workflows(project="testproj")

    # File-based should win
    assert workflows["test"].source_path == "/file/test.yml"


def test_get_all_workflows_project_overrides_internal() -> None:
    """Test that project workflows override internal workflows."""
    internal_workflow = Workflow(
        name="test",
        inputs=[],
        steps=[],
        source_path="/internal/test.yml",
    )
    project_workflow = Workflow(
        name="test",
        inputs=[],
        steps=[],
        source_path="/project/test.yml",
    )

    with (
        patch("xprompt.workflow_loader._load_workflows_from_files", return_value={}),
        patch(
            "xprompt.workflow_loader._load_workflows_from_internal",
            return_value={"test": internal_workflow},
        ),
        patch(
            "xprompt.workflow_loader._load_workflows_from_project",
            return_value={"test": project_workflow},
        ),
    ):
        workflows = get_all_workflows(project="testproj")

    # Project should win over internal
    assert workflows["test"].source_path == "/project/test.yml"
