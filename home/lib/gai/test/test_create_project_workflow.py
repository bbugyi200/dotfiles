"""Tests for create_project_workflow module."""

import tempfile
from pathlib import Path

from create_project_workflow.prompts import build_planner_prompt
from create_project_workflow.state import CreateProjectState


def test_build_planner_prompt_basic() -> None:
    """Test that build_planner_prompt builds a valid prompt."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test markdown file
        design_docs_dir = Path(tmpdir) / "designs"
        design_docs_dir.mkdir()
        (design_docs_dir / "test.md").write_text("# Test Design")

        state: CreateProjectState = {
            "design_docs_dir": str(design_docs_dir),
            "project_name": "test_project",
            "clsurf_output_file": None,
            "bug_id": "12345",
            "clquery": "test query",
            "filename": "test_project",
            "artifacts_dir": "",
            "workflow_tag": "ABC",
            "projects_file": "",
            "success": False,
            "failure_reason": None,
            "messages": [],
            "workflow_instance": None,
        }

        prompt = build_planner_prompt(state)

        # Verify key elements are in the prompt
        assert "test_project" in prompt
        assert "test.md" in prompt
        assert "ChangeSpec" in prompt
        assert "PROJECT NAME" in prompt


def test_build_planner_prompt_with_clsurf_file() -> None:
    """Test build_planner_prompt with clsurf output file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        design_docs_dir = Path(tmpdir) / "designs"
        design_docs_dir.mkdir()
        (design_docs_dir / "test.md").write_text("# Test Design")

        clsurf_file = Path(tmpdir) / "clsurf_output.txt"
        clsurf_file.write_text("CL output")

        state: CreateProjectState = {
            "design_docs_dir": str(design_docs_dir),
            "project_name": "my_project",
            "clsurf_output_file": str(clsurf_file),
            "bug_id": "12345",
            "clquery": "test query",
            "filename": "my_project",
            "artifacts_dir": "",
            "workflow_tag": "DEF",
            "projects_file": "",
            "success": False,
            "failure_reason": None,
            "messages": [],
            "workflow_instance": None,
        }

        prompt = build_planner_prompt(state)

        # Verify clsurf file is referenced
        assert str(clsurf_file) in prompt
        assert "Prior Work Analysis" in prompt


def test_build_planner_prompt_multiple_design_docs() -> None:
    """Test build_planner_prompt with multiple design documents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        design_docs_dir = Path(tmpdir) / "designs"
        design_docs_dir.mkdir()
        (design_docs_dir / "design1.md").write_text("# Design 1")
        (design_docs_dir / "design2.md").write_text("# Design 2")
        (design_docs_dir / "design3.md").write_text("# Design 3")

        state: CreateProjectState = {
            "design_docs_dir": str(design_docs_dir),
            "project_name": "multi_doc_project",
            "clsurf_output_file": None,
            "bug_id": "12345",
            "clquery": "test query",
            "filename": "multi_doc_project",
            "artifacts_dir": "",
            "workflow_tag": "GHI",
            "projects_file": "",
            "success": False,
            "failure_reason": None,
            "messages": [],
            "workflow_instance": None,
        }

        prompt = build_planner_prompt(state)

        # Verify all design docs are referenced
        assert "design1.md" in prompt
        assert "design2.md" in prompt
        assert "design3.md" in prompt
