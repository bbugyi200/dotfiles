"""Tests for the new simple workflows (crs, review)."""

from crs_workflow import CrsWorkflow
from review_workflow import ReviewWorkflow


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


class TestReviewWorkflow:
    """Tests for the review workflow."""

    def test_workflow_name(self) -> None:
        """Test that the workflow has the correct name."""
        workflow = ReviewWorkflow()
        assert workflow.name == "review"

    def test_workflow_description(self) -> None:
        """Test that the workflow has a description."""
        workflow = ReviewWorkflow()
        assert "review" in workflow.description.lower()
        assert "CL" in workflow.description
