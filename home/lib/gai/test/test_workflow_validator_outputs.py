"""Tests for output detection and template refs in workflow_validator."""

import pytest
from xprompt.models import OutputSpec, XPrompt
from xprompt.workflow_models import (
    ParallelConfig,
    Workflow,
    WorkflowStep,
    WorkflowValidationError,
)
from xprompt.workflow_validator import (
    _detect_unused_outputs,
    _extract_template_refs,
)


def _make_output() -> OutputSpec:
    """Create a minimal OutputSpec for testing."""
    return OutputSpec(
        type="json_schema",
        schema={"properties": {"result": {"type": "string"}}},
    )


def test_detect_unused_outputs_finds_unused() -> None:
    """Step with output never referenced → error."""
    workflow = Workflow(
        name="test",
        steps=[
            WorkflowStep(name="producer", bash="echo hi", output=_make_output()),
            WorkflowStep(name="consumer", bash="echo done"),
        ],
    )
    errors = _detect_unused_outputs(workflow)
    assert len(errors) == 1
    assert "producer" in errors[0]


def test_detect_unused_outputs_used_no_error() -> None:
    """Step output referenced by next step → no error."""
    workflow = Workflow(
        name="test",
        steps=[
            WorkflowStep(name="producer", bash="echo hi", output=_make_output()),
            WorkflowStep(name="consumer", bash="echo {{ producer.result }}"),
        ],
    )
    errors = _detect_unused_outputs(workflow)
    assert errors == []


def test_detect_unused_outputs_last_step_exempt() -> None:
    """Last step's unused output → no error (exempt)."""
    workflow = Workflow(
        name="test",
        steps=[
            WorkflowStep(name="first", bash="echo hi"),
            WorkflowStep(name="last", bash="echo bye", output=_make_output()),
        ],
    )
    errors = _detect_unused_outputs(workflow)
    assert errors == []


def test_detect_unused_outputs_prompt_part_last_post_step_exempt() -> None:
    """prompt_part workflow, last post-step exempt."""
    workflow = Workflow(
        name="test",
        steps=[
            WorkflowStep(name="pre", bash="echo pre"),
            WorkflowStep(name="main", prompt_part="Do something"),
            WorkflowStep(name="post_last", bash="echo post", output=_make_output()),
        ],
    )
    errors = _detect_unused_outputs(workflow)
    assert errors == []


def test_detect_unused_outputs_parallel_nested_used() -> None:
    """{{ parent.nested.field }} ref → no error."""
    workflow = Workflow(
        name="test",
        steps=[
            WorkflowStep(
                name="research",
                parallel_config=ParallelConfig(
                    steps=[
                        WorkflowStep(
                            name="task_a",
                            bash="echo a",
                            output=_make_output(),
                        ),
                        WorkflowStep(
                            name="task_b",
                            bash="echo b",
                            output=_make_output(),
                        ),
                    ]
                ),
            ),
            WorkflowStep(
                name="verify",
                bash="echo {{ research.task_a.result }} {{ research.task_b.result }}",
            ),
        ],
    )
    errors = _detect_unused_outputs(workflow)
    assert errors == []


def test_detect_unused_outputs_parallel_nested_unused() -> None:
    """Nested step output never referenced → error."""
    workflow = Workflow(
        name="test",
        steps=[
            WorkflowStep(
                name="research",
                parallel_config=ParallelConfig(
                    steps=[
                        WorkflowStep(
                            name="task_a",
                            bash="echo a",
                            output=_make_output(),
                        ),
                        WorkflowStep(
                            name="task_b",
                            bash="echo b",
                            output=_make_output(),
                        ),
                    ]
                ),
            ),
            WorkflowStep(
                name="verify",
                bash="echo {{ research.task_a.result }}",
            ),
        ],
    )
    errors = _detect_unused_outputs(workflow)
    assert len(errors) == 1
    assert "research.task_b" in errors[0]


def test_detect_unused_outputs_parallel_join_array_skips_nested() -> None:
    """join: array → nested outputs not tracked individually."""
    workflow = Workflow(
        name="test",
        steps=[
            WorkflowStep(
                name="parallel_step",
                join="array",
                parallel_config=ParallelConfig(
                    steps=[
                        WorkflowStep(
                            name="first",
                            bash="echo 1",
                            output=_make_output(),
                        ),
                        WorkflowStep(
                            name="second",
                            bash="echo 2",
                            output=_make_output(),
                        ),
                    ]
                ),
            ),
            WorkflowStep(
                name="verify",
                bash="echo {{ parallel_step | length }}",
            ),
        ],
    )
    errors = _detect_unused_outputs(workflow)
    assert errors == []


def test_detect_unused_outputs_whole_step_ref() -> None:
    """{{ step | tojson }} (no dot) → marks step used."""
    workflow = Workflow(
        name="test",
        steps=[
            WorkflowStep(name="data", bash="echo hi", output=_make_output()),
            WorkflowStep(name="use_it", bash="echo {{ data | tojson }}"),
        ],
    )
    errors = _detect_unused_outputs(workflow)
    assert errors == []


def test_detect_unused_outputs_xprompt_content_scanned() -> None:
    """Ref inside workflow-local xprompt → marks output used."""
    workflow = Workflow(
        name="test",
        steps=[
            WorkflowStep(name="producer", bash="echo hi", output=_make_output()),
            WorkflowStep(name="consumer", bash="echo done"),
        ],
        xprompts={
            "helper": XPrompt(
                name="helper",
                content="Use {{ producer.result }}",
            ),
        },
    )
    errors = _detect_unused_outputs(workflow)
    assert errors == []


def test_detect_unused_outputs_compound_condition_ref() -> None:
    """Compound if: condition {{ a.x and b.y }} marks both steps used."""
    output_a = OutputSpec(
        type="json_schema",
        schema={"properties": {"x": {"type": "boolean"}}},
    )
    output_b = OutputSpec(
        type="json_schema",
        schema={"properties": {"y": {"type": "boolean"}}},
    )
    workflow = Workflow(
        name="test",
        steps=[
            WorkflowStep(name="a", bash="echo a", output=output_a),
            WorkflowStep(name="b", bash="echo b", output=output_b),
            WorkflowStep(
                name="final",
                bash="echo done",
                condition="{{ a.x and b.y }}",
            ),
        ],
    )
    errors = _detect_unused_outputs(workflow)
    assert errors == []


def test_detect_unused_outputs_error_includes_field_names() -> None:
    """Error message includes output field names."""
    output = OutputSpec(
        type="json_schema",
        schema={"properties": {"valid": {"type": "boolean"}}},
    )
    workflow = Workflow(
        name="test",
        steps=[
            WorkflowStep(name="check", bash="echo hi", output=output),
            WorkflowStep(name="final", bash="echo done"),
        ],
    )
    errors = _detect_unused_outputs(workflow)
    assert len(errors) == 1
    assert "'valid'" in errors[0]
    assert "check" in errors[0]


def test_validate_workflow_raises_on_unused_output() -> None:
    """Integration: validate_workflow() raises error for unused output."""
    workflow = Workflow(
        name="test",
        steps=[
            WorkflowStep(name="unused_out", bash="echo hi", output=_make_output()),
            WorkflowStep(name="final", bash="echo done"),
        ],
    )
    with pytest.raises(WorkflowValidationError, match="unused_out"):
        from xprompt.workflow_validator import validate_workflow

        validate_workflow(workflow)


def test_extract_template_refs_compound_expression() -> None:
    """Compound expression {{ a.valid and b.valid }} extracts both refs."""
    refs = _extract_template_refs("{{ a.valid and b.valid }}")
    dotted_refs = [r for r in refs if "." in r]
    assert "a.valid" in dotted_refs
    assert "b.valid" in dotted_refs


def test_extract_template_refs_single() -> None:
    """Single variable {{ foo }} extracts one ref."""
    refs = _extract_template_refs("{{ foo }}")
    assert "foo" in refs


def test_extract_template_refs_dotted() -> None:
    """Dotted path {{ step.field }} extracts one dotted ref."""
    refs = _extract_template_refs("{{ step.field }}")
    assert "step.field" in refs
