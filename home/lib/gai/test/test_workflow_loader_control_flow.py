"""Tests for control flow parsing in workflow_loader."""

import pytest
from xprompt.workflow_loader import _parse_workflow_step
from xprompt.workflow_models import WorkflowValidationError


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
