"""Tests for Workflow model methods."""

from xprompt.models import InputArg, InputType
from xprompt.workflow_models import Workflow, WorkflowStep

# ============================================================================
# Workflow.appears_as_agent() tests
# ============================================================================


def test_workflow_appears_as_agent_with_hidden_steps() -> None:
    """Test that workflow appears as agent when all non-prompt steps are hidden."""
    workflow = Workflow(
        name="json",
        steps=[
            WorkflowStep(name="setup", bash="setup.sh", hidden=True),
            WorkflowStep(name="inject", prompt="Do the thing"),
            WorkflowStep(name="validate", bash="validate.sh", hidden=True),
        ],
    )
    assert workflow.appears_as_agent() is True


def test_workflow_appears_as_agent_single_visible_prompt() -> None:
    """Test that workflow with only a visible prompt step appears as agent."""
    workflow = Workflow(
        name="simple",
        steps=[
            WorkflowStep(name="main", prompt="Do something"),
        ],
    )
    assert workflow.appears_as_agent() is True


def test_workflow_not_appears_as_agent_with_visible_non_prompt() -> None:
    """Test that workflow with visible non-prompt step doesn't appear as agent."""
    workflow = Workflow(
        name="workflow_with_setup",
        steps=[
            WorkflowStep(name="setup", bash="setup.sh", hidden=False),
            WorkflowStep(name="main", prompt="Do something"),
        ],
    )
    assert workflow.appears_as_agent() is False


def test_workflow_not_appears_as_agent_multiple_visible() -> None:
    """Test that workflow with multiple visible steps doesn't appear as agent."""
    workflow = Workflow(
        name="multi_step",
        steps=[
            WorkflowStep(name="step1", prompt="Step 1"),
            WorkflowStep(name="step2", prompt="Step 2"),
        ],
    )
    assert workflow.appears_as_agent() is False


def test_workflow_not_appears_as_agent_no_prompt_visible() -> None:
    """Test that workflow with only visible non-prompt steps doesn't appear as agent."""
    workflow = Workflow(
        name="bash_only",
        steps=[
            WorkflowStep(name="step1", bash="echo hello"),
        ],
    )
    assert workflow.appears_as_agent() is False


def test_workflow_not_appears_as_agent_all_hidden() -> None:
    """Test that workflow with all hidden steps doesn't appear as agent."""
    workflow = Workflow(
        name="all_hidden",
        steps=[
            WorkflowStep(name="setup", bash="setup.sh", hidden=True),
            WorkflowStep(name="cleanup", bash="cleanup.sh", hidden=True),
        ],
    )
    # No visible steps, so it shouldn't appear as agent
    assert workflow.appears_as_agent() is False


# ============================================================================
# Workflow.is_simple_xprompt() tests
# ============================================================================


def test_workflow_is_simple_xprompt_single_prompt_part() -> None:
    """Test that single prompt_part step workflow is a simple xprompt."""
    workflow = Workflow(
        name="explain",
        steps=[
            WorkflowStep(name="main", prompt_part="Explain this code"),
        ],
    )
    assert workflow.is_simple_xprompt() is True


def test_workflow_is_simple_xprompt_with_inputs() -> None:
    """Test that single prompt_part with inputs is still simple xprompt."""
    workflow = Workflow(
        name="review",
        inputs=[InputArg(name="code", type=InputType.TEXT)],
        steps=[
            WorkflowStep(name="main", prompt_part="Review: {{ code }}"),
        ],
    )
    assert workflow.is_simple_xprompt() is True


def test_workflow_not_simple_xprompt_prompt_step() -> None:
    """Test that workflow with prompt step (not prompt_part) is not simple."""
    workflow = Workflow(
        name="adhoc",
        steps=[
            WorkflowStep(name="main", prompt="Do something"),
        ],
    )
    assert workflow.is_simple_xprompt() is False


def test_workflow_not_simple_xprompt_bash_step() -> None:
    """Test that workflow with bash step is not simple xprompt."""
    workflow = Workflow(
        name="runner",
        steps=[
            WorkflowStep(name="main", bash="echo hello"),
        ],
    )
    assert workflow.is_simple_xprompt() is False


def test_workflow_not_simple_xprompt_multiple_steps() -> None:
    """Test that workflow with multiple steps is not simple xprompt."""
    workflow = Workflow(
        name="complex",
        steps=[
            WorkflowStep(name="setup", bash="setup.sh"),
            WorkflowStep(name="main", prompt_part="Do the thing"),
        ],
    )
    assert workflow.is_simple_xprompt() is False


def test_workflow_not_simple_xprompt_prompt_part_with_post_steps() -> None:
    """Test that prompt_part with post-steps is not simple xprompt."""
    workflow = Workflow(
        name="with_validation",
        steps=[
            WorkflowStep(name="inject", prompt_part="Generate JSON"),
            WorkflowStep(name="validate", bash="validate.sh"),
        ],
    )
    assert workflow.is_simple_xprompt() is False


def test_workflow_not_simple_xprompt_empty_steps() -> None:
    """Test that workflow with no steps is not simple xprompt."""
    workflow = Workflow(
        name="empty",
        steps=[],
    )
    assert workflow.is_simple_xprompt() is False
