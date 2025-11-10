"""Tests for new_ez_feature_workflow module."""

import tempfile
from pathlib import Path

from new_ez_feature_workflow.prompts import build_editor_prompt
from new_ez_feature_workflow.state import NewEzFeatureState


def test_build_editor_prompt_basic() -> None:
    """Test that build_editor_prompt builds a valid prompt."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = Path(tmpdir) / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "cl_desc.txt").write_text("CL description")
        (artifacts_dir / "cl_changes.diff").write_text("diff content")

        design_docs_dir = Path(tmpdir) / "designs"
        design_docs_dir.mkdir()

        state: NewEzFeatureState = {
            "cl_name": "test_cl",
            "cl_description": "Test CL description",
            "design_docs_dir": str(design_docs_dir),
            "artifacts_dir": str(artifacts_dir),
            "context_file_directory": None,
            "project_name": "test_project",
            "changespec_text": "",
            "success": False,
            "failure_reason": None,
            "editor_response": "",
            "messages": [],
            "workflow_tag": "ABC",
            "workflow_instance": None,
        }

        prompt = build_editor_prompt(state)

        # Verify key elements
        assert "test_cl" in prompt
        assert "CONTEXT FILES" in prompt
        assert "cl_desc.txt" in prompt
        # CL description is accessed via @ file reference, not embedded
        assert "@" in prompt
        assert str(artifacts_dir) in prompt


def test_build_editor_prompt_with_design_docs() -> None:
    """Test build_editor_prompt with design documents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = Path(tmpdir) / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "cl_desc.txt").write_text("CL description")
        (artifacts_dir / "cl_changes.diff").write_text("diff content")

        design_docs_dir = Path(tmpdir) / "designs"
        design_docs_dir.mkdir()
        (design_docs_dir / "design1.md").write_text("# Design 1")
        (design_docs_dir / "design2.txt").write_text("Design 2 text")

        state: NewEzFeatureState = {
            "cl_name": "feature_cl",
            "cl_description": "Feature description",
            "design_docs_dir": str(design_docs_dir),
            "artifacts_dir": str(artifacts_dir),
            "context_file_directory": None,
            "project_name": "my_project",
            "changespec_text": "",
            "success": False,
            "failure_reason": None,
            "editor_response": "",
            "messages": [],
            "workflow_tag": "DEF",
            "workflow_instance": None,
        }

        prompt = build_editor_prompt(state)

        # Verify design docs are referenced
        assert "Design Documents" in prompt
        assert "design1.md" in prompt
        assert "design2.txt" in prompt


def test_build_editor_prompt_with_context_directory() -> None:
    """Test build_editor_prompt with additional context directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = Path(tmpdir) / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "cl_desc.txt").write_text("CL description")
        (artifacts_dir / "cl_changes.diff").write_text("diff content")

        design_docs_dir = Path(tmpdir) / "designs"
        design_docs_dir.mkdir()

        context_dir = Path(tmpdir) / "context"
        context_dir.mkdir()
        (context_dir / "context1.md").write_text("# Context 1")
        (context_dir / "context2.txt").write_text("Context 2 text")

        state: NewEzFeatureState = {
            "cl_name": "ctx_cl",
            "cl_description": "CL with context",
            "design_docs_dir": str(design_docs_dir),
            "artifacts_dir": str(artifacts_dir),
            "context_file_directory": str(context_dir),
            "project_name": "ctx_project",
            "changespec_text": "",
            "success": False,
            "failure_reason": None,
            "editor_response": "",
            "messages": [],
            "workflow_tag": "GHI",
            "workflow_instance": None,
        }

        prompt = build_editor_prompt(state)

        # Verify context files are referenced
        assert "Additional Context Files" in prompt
        assert "context1.md" in prompt
        assert "context2.txt" in prompt
