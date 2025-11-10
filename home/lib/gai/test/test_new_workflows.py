"""Tests for the new simple workflows (crs, qa)."""

from crs_workflow import CrsWorkflow
from qa_workflow import QaWorkflow


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


class TestQaWorkflow:
    """Tests for the QA workflow."""

    def test_workflow_name(self) -> None:
        """Test that the workflow has the correct name."""
        workflow = QaWorkflow()
        assert workflow.name == "qa"

    def test_workflow_description(self) -> None:
        """Test that the workflow has a description."""
        workflow = QaWorkflow()
        assert "qa" in workflow.description.lower()
        assert "CL" in workflow.description
