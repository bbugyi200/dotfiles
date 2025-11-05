"""Tests for the new simple workflows (crs, fix-ez-tests, review)."""

from crs_workflow import CrsWorkflow
from fix_ez_tests_workflow import FixEzTestsWorkflow
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


class TestFixEzTestsWorkflow:
    """Tests for the fix-ez-tests workflow."""

    def test_workflow_name(self) -> None:
        """Test that the workflow has the correct name."""
        workflow = FixEzTestsWorkflow("test-project")
        assert workflow.name == "fix-ez-tests"

    def test_workflow_description(self) -> None:
        """Test that the workflow has a description."""
        workflow = FixEzTestsWorkflow("test-project")
        assert "fix" in workflow.description.lower()
        assert "test" in workflow.description.lower()

    def test_project_name_stored(self) -> None:
        """Test that the project name is stored correctly."""
        workflow = FixEzTestsWorkflow("my-project")
        assert workflow.project_name == "my-project"


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
