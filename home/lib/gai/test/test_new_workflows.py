"""Tests for the new simple workflows (crs)."""

import os
import tempfile

from crs_workflow import CrsWorkflow, _build_crs_prompt


class TestCrsWorkflow:
    """Tests for the CRS (change requests) workflow."""

    def test_workflow_name(self) -> None:
        """Test that the workflow has the correct name."""
        workflow = CrsWorkflow()
        assert workflow.name == "crs"

    def test_workflow_description(self) -> None:
        """Test that the workflow has a description."""
        workflow = CrsWorkflow()
        assert "Critique" in workflow.description
        assert "change request" in workflow.description

    def test_build_crs_prompt_basic(self) -> None:
        """Test building a CRS prompt."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"comments": []}\n')
            comments_file = f.name

        try:
            prompt = _build_crs_prompt(comments_file)
            # #cl is now provided by #propose (not inline in crs.md)
            # but the prompt should still have the core content
            assert f"@{comments_file}" in prompt
            assert "Critique" in prompt
            # #propose reference should be present for later workflow expansion
            assert "#propose" in prompt
        finally:
            os.unlink(comments_file)


class TestCrsWorkflowAdvanced:
    """Additional tests for the CRS workflow."""

    def test_workflow_init_with_project_name(self) -> None:
        """Test that workflow can be initialized with project name."""
        workflow = CrsWorkflow(project_name="my_project")
        assert workflow.project_name == "my_project"
        assert workflow.name == "crs"
