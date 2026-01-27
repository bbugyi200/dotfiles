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
            # #cl xprompt is expanded to context files section
            assert "Context Files Related to this CL" in prompt
            assert f"@{comments_file}" in prompt
            assert "Critique" in prompt
        finally:
            os.unlink(comments_file)


class TestCrsWorkflowAdvanced:
    """Additional tests for the CRS workflow."""

    def test_workflow_init_with_context_file(self) -> None:
        """Test that workflow can be initialized with context file directory."""
        workflow = CrsWorkflow(context_file_directory="/path/to/context")
        assert workflow.context_file_directory == "/path/to/context"
        assert workflow.name == "crs"

    def test_build_crs_prompt_with_context_directory(self) -> None:
        """Test building CRS prompt with context directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test markdown file for context
            test_file = os.path.join(tmpdir, "context.md")
            with open(test_file, "w") as f:
                f.write("# Test Context\n")

            # Create a comments file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                f.write('{"comments": []}\n')
                comments_file = f.name

            try:
                prompt = _build_crs_prompt(comments_file, tmpdir)
                # #cl xprompt is expanded to context files section
                assert "Context Files Related to this CL" in prompt
                assert "context.md" in prompt
            finally:
                os.unlink(comments_file)
