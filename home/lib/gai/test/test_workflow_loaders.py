"""Tests for workflow state and step loaders."""

from unittest.mock import patch

from ace.tui.models._loaders._workflow_loaders import load_workflow_agents
from xprompt import StepState, StepStatus


def test_step_output_extracted_for_non_appears_as_agent() -> None:
    """Verify step_output is extracted even when appears_as_agent is False."""
    from ace.tui.models.workflow import WorkflowEntry

    entry = WorkflowEntry(
        workflow_name="test-workflow",
        cl_name="test_cl",
        project_file="/fake/path.gp",
        status="DONE",
        current_step=0,
        total_steps=1,
        steps=[
            StepState(
                name="run",
                status=StepStatus.COMPLETED,
                output={"meta_proposal_id": "xyz789", "result": "done"},
            )
        ],
        start_time=None,
        artifacts_dir="/tmp/fake",
        appears_as_agent=False,
        is_anonymous=False,
    )

    with patch(
        "ace.tui.models._loaders._workflow_loaders.load_workflow_states",
        return_value=[entry],
    ):
        agents = load_workflow_agents()

    assert len(agents) == 1
    assert agents[0].step_output == {"meta_proposal_id": "xyz789", "result": "done"}


def test_step_output_none_when_no_steps() -> None:
    """Verify step_output is None when workflow has no steps."""
    from ace.tui.models.workflow import WorkflowEntry

    entry = WorkflowEntry(
        workflow_name="test-workflow",
        cl_name="test_cl",
        project_file="/fake/path.gp",
        status="DONE",
        current_step=0,
        total_steps=0,
        steps=[],
        start_time=None,
        artifacts_dir="/tmp/fake",
        appears_as_agent=False,
        is_anonymous=False,
    )

    with patch(
        "ace.tui.models._loaders._workflow_loaders.load_workflow_states",
        return_value=[entry],
    ):
        agents = load_workflow_agents()

    assert len(agents) == 1
    assert agents[0].step_output is None
