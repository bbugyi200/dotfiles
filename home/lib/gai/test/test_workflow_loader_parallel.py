"""Tests for parallel step parsing and hidden field parsing in workflow_loader."""

import pytest
from xprompt.workflow_loader import _parse_workflow_step
from xprompt.workflow_models import WorkflowValidationError

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
