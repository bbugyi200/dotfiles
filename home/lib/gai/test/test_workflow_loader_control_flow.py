"""Tests for control flow parsing in workflow_loader."""

import pytest
from xprompt.workflow_loader import _parse_workflow_step
from xprompt.workflow_models import Workflow, WorkflowStep, WorkflowValidationError


def test_parse_if_condition() -> None:
    """Test parsing if: condition field."""
    step_data = {
        "name": "conditional_step",
        "bash": "echo hello",
        "if": "{{ some_var }}",
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.condition == "{{ some_var }}"


def test_parse_if_condition_with_expression() -> None:
    """Test parsing if: with a complex expression."""
    step_data = {
        "name": "check_step",
        "bash": "run_cleanup.sh",
        "if": "{{ setup.needs_cleanup }}",
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.condition == "{{ setup.needs_cleanup }}"


def test_parse_for_single_variable() -> None:
    """Test parsing for: with single variable."""
    step_data = {
        "name": "process_items",
        "bash": "process {{ item }}",
        "for": {"item": "{{ get_items.items }}"},
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.for_loop == {"item": "{{ get_items.items }}"}


def test_parse_for_multiple_variables() -> None:
    """Test parsing for: with multiple parallel variables."""
    step_data = {
        "name": "process_parallel",
        "bash": "process {{ item }} --id {{ id }}",
        "for": {
            "item": "{{ get_items.items }}",
            "id": "{{ get_items.ids }}",
        },
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.for_loop == {
        "item": "{{ get_items.items }}",
        "id": "{{ get_items.ids }}",
    }


def test_parse_for_invalid_not_dict() -> None:
    """Test that for: must be a dict."""
    step_data = {
        "name": "bad_step",
        "bash": "echo test",
        "for": ["item1", "item2"],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "'for' field must be a dict" in str(exc_info.value)


def test_parse_repeat_with_until() -> None:
    """Test parsing repeat: with until: condition."""
    step_data = {
        "name": "retry_step",
        "bash": "try_action.sh",
        "repeat": {
            "until": "{{ retry_step.success }}",
        },
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.repeat_config is not None
    assert step.repeat_config.condition == "{{ retry_step.success }}"
    assert step.repeat_config.max_iterations == 100  # Default


def test_parse_repeat_with_max() -> None:
    """Test parsing repeat: with custom max iterations."""
    step_data = {
        "name": "retry_step",
        "bash": "try_action.sh",
        "repeat": {
            "until": "{{ retry_step.success }}",
            "max": 5,
        },
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.repeat_config is not None
    assert step.repeat_config.max_iterations == 5


def test_parse_repeat_missing_until() -> None:
    """Test that repeat: requires until: field."""
    step_data = {
        "name": "bad_step",
        "bash": "echo test",
        "repeat": {"max": 5},
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "'repeat' field requires 'until' condition" in str(exc_info.value)


def test_parse_repeat_not_dict() -> None:
    """Test that repeat: must be a dict."""
    step_data = {
        "name": "bad_step",
        "bash": "echo test",
        "repeat": "{{ condition }}",
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "'repeat' field must be a dict" in str(exc_info.value)


def test_parse_while_short_form() -> None:
    """Test parsing while: in short form (string)."""
    step_data = {
        "name": "poll_step",
        "bash": "check_status.sh",
        "while": "{{ poll_step.pending }}",
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.while_config is not None
    assert step.while_config.condition == "{{ poll_step.pending }}"
    assert step.while_config.max_iterations == 100  # Default


def test_parse_while_long_form() -> None:
    """Test parsing while: in long form (dict)."""
    step_data = {
        "name": "poll_step",
        "bash": "check_status.sh",
        "while": {
            "condition": "{{ poll_step.pending }}",
            "max": 10,
        },
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.while_config is not None
    assert step.while_config.condition == "{{ poll_step.pending }}"
    assert step.while_config.max_iterations == 10


def test_parse_while_missing_condition() -> None:
    """Test that while: dict requires condition: field."""
    step_data = {
        "name": "bad_step",
        "bash": "echo test",
        "while": {"max": 10},
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "'while' field requires 'condition' key" in str(exc_info.value)


def test_parse_while_invalid_type() -> None:
    """Test that while: must be string or dict."""
    step_data = {
        "name": "bad_step",
        "bash": "echo test",
        "while": 123,
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "'while' field must be a string or dict" in str(exc_info.value)


def test_parse_join_array() -> None:
    """Test parsing join: array mode."""
    step_data = {
        "name": "process_step",
        "bash": "process {{ item }}",
        "for": {"item": "{{ items }}"},
        "join": "array",
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.join == "array"


def test_parse_join_text() -> None:
    """Test parsing join: text mode."""
    step_data = {
        "name": "process_step",
        "bash": "process {{ item }}",
        "for": {"item": "{{ items }}"},
        "join": "text",
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.join == "text"


def test_parse_join_object() -> None:
    """Test parsing join: object mode."""
    step_data = {
        "name": "process_step",
        "bash": "process {{ item }}",
        "for": {"item": "{{ items }}"},
        "join": "object",
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.join == "object"


def test_parse_join_lastOf() -> None:
    """Test parsing join: lastOf mode."""
    step_data = {
        "name": "process_step",
        "bash": "process {{ item }}",
        "for": {"item": "{{ items }}"},
        "join": "lastOf",
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.join == "lastOf"


def test_parse_join_invalid_mode() -> None:
    """Test that invalid join: mode is rejected."""
    step_data = {
        "name": "bad_step",
        "bash": "process {{ item }}",
        "for": {"item": "{{ items }}"},
        "join": "invalid_mode",
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "'join' must be one of" in str(exc_info.value)


def test_mutual_exclusivity_for_and_repeat() -> None:
    """Test that for: and repeat: are mutually exclusive."""
    step_data = {
        "name": "bad_step",
        "bash": "echo test",
        "for": {"item": "{{ items }}"},
        "repeat": {"until": "{{ done }}"},
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "can only have one of 'for', 'repeat', or 'while'" in str(exc_info.value)


def test_mutual_exclusivity_for_and_while() -> None:
    """Test that for: and while: are mutually exclusive."""
    step_data = {
        "name": "bad_step",
        "bash": "echo test",
        "for": {"item": "{{ items }}"},
        "while": "{{ condition }}",
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "can only have one of 'for', 'repeat', or 'while'" in str(exc_info.value)


def test_mutual_exclusivity_repeat_and_while() -> None:
    """Test that repeat: and while: are mutually exclusive."""
    step_data = {
        "name": "bad_step",
        "bash": "echo test",
        "repeat": {"until": "{{ done }}"},
        "while": "{{ condition }}",
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "can only have one of 'for', 'repeat', or 'while'" in str(exc_info.value)


def test_if_with_for_allowed() -> None:
    """Test that if: can be combined with for:."""
    step_data = {
        "name": "conditional_loop",
        "bash": "process {{ item }}",
        "if": "{{ should_process }}",
        "for": {"item": "{{ items }}"},
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.condition == "{{ should_process }}"
    assert step.for_loop == {"item": "{{ items }}"}


def test_if_with_repeat_allowed() -> None:
    """Test that if: can be combined with repeat:."""
    step_data = {
        "name": "conditional_retry",
        "bash": "try_action.sh",
        "if": "{{ needs_retry }}",
        "repeat": {"until": "{{ success }}"},
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.condition == "{{ needs_retry }}"
    assert step.repeat_config is not None


def test_step_without_control_flow() -> None:
    """Test that steps without control flow fields work normally."""
    step_data = {
        "name": "normal_step",
        "bash": "echo hello",
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.condition is None
    assert step.for_loop is None
    assert step.repeat_config is None
    assert step.while_config is None
    assert step.parallel_config is None
    assert step.join is None


# ============================================================================
# Parallel step parsing tests
# ============================================================================


def test_parse_parallel_basic() -> None:
    """Test parsing basic parallel: field with two steps."""
    step_data = {
        "name": "parallel_test",
        "parallel": [
            {"name": "step_a", "bash": "echo a"},
            {"name": "step_b", "bash": "echo b"},
        ],
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.parallel_config is not None
    assert len(step.parallel_config.steps) == 2
    assert step.parallel_config.steps[0].name == "step_a"
    assert step.parallel_config.steps[1].name == "step_b"


def test_parse_parallel_with_agent_steps() -> None:
    """Test parsing parallel: with agent steps."""
    step_data = {
        "name": "parallel_agents",
        "parallel": [
            {"name": "summarize", "prompt": "Summarize this: {{ doc }}"},
            {"name": "extract", "prompt": "Extract entities from: {{ doc }}"},
        ],
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.parallel_config is not None
    assert step.parallel_config.steps[0].is_prompt_step()
    assert step.parallel_config.steps[1].is_prompt_step()


def test_parse_parallel_mixed_step_types() -> None:
    """Test parsing parallel: with mixed step types."""
    step_data = {
        "name": "parallel_mixed",
        "parallel": [
            {"name": "fetch", "bash": "curl https://example.com"},
            {"name": "process", "python": "print('hello')"},
        ],
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.parallel_config is not None
    assert step.parallel_config.steps[0].is_bash_step()
    assert step.parallel_config.steps[1].is_python_step()


def test_parse_parallel_with_for_allowed() -> None:
    """Test that parallel: can be combined with for:."""
    step_data = {
        "name": "for_parallel",
        "for": {"file": "{{ files }}"},
        "parallel": [
            {"name": "lint", "bash": "lint {{ file }}"},
            {"name": "format", "bash": "format {{ file }}"},
        ],
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.for_loop is not None
    assert step.parallel_config is not None


def test_parse_parallel_with_if_allowed() -> None:
    """Test that parallel: can be combined with if:."""
    step_data = {
        "name": "conditional_parallel",
        "if": "{{ should_run }}",
        "parallel": [
            {"name": "step_a", "bash": "echo a"},
            {"name": "step_b", "bash": "echo b"},
        ],
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.condition == "{{ should_run }}"
    assert step.parallel_config is not None


def test_parse_parallel_with_join() -> None:
    """Test that parallel: can have join: mode."""
    step_data = {
        "name": "parallel_join",
        "parallel": [
            {"name": "step_a", "bash": "echo a"},
            {"name": "step_b", "bash": "echo b"},
        ],
        "join": "object",
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.parallel_config is not None
    assert step.join == "object"


def test_parse_parallel_not_list_raises() -> None:
    """Test that parallel: must be a list."""
    step_data = {
        "name": "bad_parallel",
        "parallel": {"step_a": "echo a"},
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "'parallel' field must be a list" in str(exc_info.value)


def test_parse_parallel_less_than_two_steps_raises() -> None:
    """Test that parallel: requires at least 2 steps."""
    step_data = {
        "name": "bad_parallel",
        "parallel": [
            {"name": "only_one", "bash": "echo one"},
        ],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "requires at least 2 steps" in str(exc_info.value)


def test_parse_parallel_duplicate_step_names_raises() -> None:
    """Test that nested steps must have unique names."""
    step_data = {
        "name": "bad_parallel",
        "parallel": [
            {"name": "duplicate", "bash": "echo a"},
            {"name": "duplicate", "bash": "echo b"},
        ],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "duplicate nested step name" in str(exc_info.value)


def test_parse_parallel_nested_with_for_raises() -> None:
    """Test that nested steps cannot have for: loops."""
    step_data = {
        "name": "bad_parallel",
        "parallel": [
            {"name": "step_a", "bash": "echo a"},
            {"name": "step_b", "bash": "echo b", "for": {"item": "{{ items }}"}},
        ],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "cannot have 'for'" in str(exc_info.value)


def test_parse_parallel_nested_with_repeat_raises() -> None:
    """Test that nested steps cannot have repeat: loops."""
    step_data = {
        "name": "bad_parallel",
        "parallel": [
            {"name": "step_a", "bash": "echo a"},
            {"name": "step_b", "bash": "echo b", "repeat": {"until": "{{ done }}"}},
        ],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "cannot have" in str(exc_info.value)
    assert "'repeat'" in str(exc_info.value)


def test_parse_parallel_nested_with_while_raises() -> None:
    """Test that nested steps cannot have while: loops."""
    step_data = {
        "name": "bad_parallel",
        "parallel": [
            {"name": "step_a", "bash": "echo a"},
            {"name": "step_b", "bash": "echo b", "while": "{{ pending }}"},
        ],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "cannot have" in str(exc_info.value)
    assert "'while'" in str(exc_info.value)


def test_parse_parallel_nested_with_parallel_raises() -> None:
    """Test that nested steps cannot have parallel: (no nested parallelism)."""
    step_data = {
        "name": "bad_parallel",
        "parallel": [
            {"name": "step_a", "bash": "echo a"},
            {
                "name": "step_b",
                "parallel": [
                    {"name": "inner_a", "bash": "echo inner"},
                    {"name": "inner_b", "bash": "echo inner2"},
                ],
            },
        ],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "cannot have" in str(exc_info.value)
    assert "'parallel'" in str(exc_info.value)


def test_parse_parallel_nested_with_hitl_raises() -> None:
    """Test that nested steps cannot have hitl: true."""
    step_data = {
        "name": "bad_parallel",
        "parallel": [
            {"name": "step_a", "bash": "echo a"},
            {"name": "step_b", "bash": "echo b", "hitl": True},
        ],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "cannot have 'hitl: true'" in str(exc_info.value)


def test_parse_parallel_with_repeat_raises() -> None:
    """Test that parallel: cannot combine with repeat:."""
    step_data = {
        "name": "bad_parallel",
        "parallel": [
            {"name": "step_a", "bash": "echo a"},
            {"name": "step_b", "bash": "echo b"},
        ],
        "repeat": {"until": "{{ done }}"},
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "cannot combine 'parallel' with 'repeat'" in str(exc_info.value)


def test_parse_parallel_with_while_raises() -> None:
    """Test that parallel: cannot combine with while:."""
    step_data = {
        "name": "bad_parallel",
        "parallel": [
            {"name": "step_a", "bash": "echo a"},
            {"name": "step_b", "bash": "echo b"},
        ],
        "while": "{{ pending }}",
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "cannot combine 'parallel' with" in str(exc_info.value)
    assert "'while'" in str(exc_info.value)


def test_parse_parallel_mutually_exclusive_with_agent() -> None:
    """Test that parallel: is mutually exclusive with agent:."""
    step_data = {
        "name": "bad_step",
        "prompt": "Do something",
        "parallel": [
            {"name": "step_a", "bash": "echo a"},
            {"name": "step_b", "bash": "echo b"},
        ],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "can only have one of" in str(exc_info.value)


def test_parse_parallel_mutually_exclusive_with_bash() -> None:
    """Test that parallel: is mutually exclusive with bash:."""
    step_data = {
        "name": "bad_step",
        "bash": "echo hello",
        "parallel": [
            {"name": "step_a", "bash": "echo a"},
            {"name": "step_b", "bash": "echo b"},
        ],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        _parse_workflow_step(step_data, 0)
    assert "can only have one of" in str(exc_info.value)


# ============================================================================
# Hidden step field tests
# ============================================================================


def test_parse_hidden_field_true() -> None:
    """Test parsing hidden: true field."""
    step_data = {
        "name": "hidden_step",
        "bash": "echo setup",
        "hidden": True,
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.hidden is True


def test_parse_hidden_field_false() -> None:
    """Test parsing hidden: false field."""
    step_data = {
        "name": "visible_step",
        "bash": "echo visible",
        "hidden": False,
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.hidden is False


def test_parse_hidden_field_default() -> None:
    """Test that hidden defaults to False when not specified."""
    step_data = {
        "name": "normal_step",
        "bash": "echo hello",
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.hidden is False


def test_parse_hidden_with_prompt_part() -> None:
    """Test that hidden can be combined with prompt_part."""
    step_data = {
        "name": "inject",
        "prompt_part": "Some content to inject",
        "hidden": False,  # prompt_part steps are typically visible
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.hidden is False
    assert step.is_prompt_part_step()


def test_parse_hidden_with_control_flow() -> None:
    """Test that hidden can be combined with control flow."""
    step_data = {
        "name": "hidden_loop",
        "bash": "process {{ item }}",
        "for": {"item": "{{ items }}"},
        "hidden": True,
    }
    step = _parse_workflow_step(step_data, 0)
    assert step.hidden is True
    assert step.for_loop is not None


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
    from xprompt.models import InputArg, InputType

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
