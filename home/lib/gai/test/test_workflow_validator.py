"""Tests for the workflow_validator module."""

import pytest
from xprompt.models import InputArg, InputType, OutputSpec, XPrompt
from xprompt.workflow_models import (
    ParallelConfig,
    Workflow,
    WorkflowStep,
    WorkflowValidationError,
)
from xprompt.workflow_validator import (
    _collect_used_variables,
    _detect_unused_inputs,
    _detect_unused_outputs,
    _detect_unused_xprompt_inputs,
    _detect_unused_xprompts,
    _extract_template_refs,
    _extract_xprompt_calls,
    _validate_xprompt_call,
    _validate_xprompt_names,
    _XPromptCall,
)


def test_extract_xprompt_calls_simple() -> None:
    """Test extracting a simple xprompt reference."""
    calls = _extract_xprompt_calls("#foo")
    assert len(calls) == 1
    assert calls[0].name == "foo"
    assert calls[0].positional_args == []
    assert calls[0].named_args == {}


def test_extract_xprompt_calls_with_args() -> None:
    """Test extracting xprompt with parenthesis args."""
    calls = _extract_xprompt_calls('#bar(arg1, name="value")')
    assert len(calls) == 1
    assert calls[0].name == "bar"
    assert calls[0].positional_args == ["arg1"]
    assert calls[0].named_args == {"name": "value"}


def test_extract_xprompt_calls_colon_syntax() -> None:
    """Test extracting xprompt with colon syntax."""
    calls = _extract_xprompt_calls("#foo:myvalue")
    assert len(calls) == 1
    assert calls[0].name == "foo"
    assert calls[0].positional_args == ["myvalue"]
    assert calls[0].named_args == {}


def test_extract_xprompt_calls_plus_syntax() -> None:
    """Test extracting xprompt with plus syntax."""
    calls = _extract_xprompt_calls("#foo+")
    assert len(calls) == 1
    assert calls[0].name == "foo"
    assert calls[0].positional_args == ["true"]
    assert calls[0].named_args == {}


def test_extract_xprompt_calls_namespaced() -> None:
    """Test extracting namespaced xprompt."""
    calls = _extract_xprompt_calls("#namespace/name(arg)")
    assert len(calls) == 1
    assert calls[0].name == "namespace/name"
    assert calls[0].positional_args == ["arg"]


def test_extract_xprompt_calls_multiple() -> None:
    """Test extracting multiple xprompts from content."""
    content = "Use #foo then #bar(x) and #baz:y"
    calls = _extract_xprompt_calls(content)
    assert len(calls) == 3
    assert calls[0].name == "foo"
    assert calls[1].name == "bar"
    assert calls[2].name == "baz"


def test_validate_xprompt_call_valid() -> None:
    """Test validation of a valid xprompt call."""
    xprompt = XPrompt(
        name="test",
        content="{{ arg1 }}",
        inputs=[InputArg(name="arg1", type=InputType.LINE)],
    )
    call = _XPromptCall(
        name="test",
        positional_args=["value"],
        named_args={},
        raw_match="#test(value)",
    )
    errors = _validate_xprompt_call(call, xprompt, "step1")
    assert errors == []


def test_validate_xprompt_call_missing_required_arg() -> None:
    """Test validation detects missing required argument."""
    xprompt = XPrompt(
        name="test",
        content="{{ required_arg }}",
        inputs=[InputArg(name="required_arg", type=InputType.LINE)],
    )
    call = _XPromptCall(
        name="test",
        positional_args=[],
        named_args={},
        raw_match="#test",
    )
    errors = _validate_xprompt_call(call, xprompt, "step1")
    assert len(errors) == 1
    assert "missing required args" in errors[0]
    assert "required_arg" in errors[0]


def test_validate_xprompt_call_unknown_named_arg() -> None:
    """Test validation detects unknown named argument."""
    xprompt = XPrompt(
        name="test",
        content="{{ known }}",
        inputs=[InputArg(name="known", type=InputType.LINE, default="default")],
    )
    call = _XPromptCall(
        name="test",
        positional_args=[],
        named_args={"unknown_arg": "value"},
        raw_match='#test(unknown_arg="value")',
    )
    errors = _validate_xprompt_call(call, xprompt, "step1")
    assert len(errors) == 1
    assert "has no input named 'unknown_arg'" in errors[0]
    assert "Available:" in errors[0]


def test_validate_xprompt_call_too_many_positional_args() -> None:
    """Test validation detects too many positional arguments."""
    xprompt = XPrompt(
        name="test",
        content="{{ one }}",
        inputs=[InputArg(name="one", type=InputType.LINE)],
    )
    call = _XPromptCall(
        name="test",
        positional_args=["first", "second", "third"],
        named_args={},
        raw_match="#test(first, second, third)",
    )
    errors = _validate_xprompt_call(call, xprompt, "step1")
    assert len(errors) >= 1
    assert "3 positional args but only 1 inputs defined" in errors[0]


def test_validate_xprompt_call_with_default() -> None:
    """Test that args with defaults are not required."""
    xprompt = XPrompt(
        name="test",
        content="{{ optional }}",
        inputs=[
            InputArg(name="optional", type=InputType.LINE, default="default_value")
        ],
    )
    call = _XPromptCall(
        name="test",
        positional_args=[],
        named_args={},
        raw_match="#test",
    )
    errors = _validate_xprompt_call(call, xprompt, "step1")
    assert errors == []


def test_collect_used_variables_simple() -> None:
    """Test collecting variables from simple workflow."""
    workflow = Workflow(
        name="test",
        inputs=[InputArg(name="my_input", type=InputType.LINE)],
        steps=[
            WorkflowStep(
                name="step1",
                bash="echo {{ my_input }}",
            )
        ],
    )
    used = _collect_used_variables(workflow)
    assert "my_input" in used


def test_collect_used_variables_multiple_sources() -> None:
    """Test collecting variables from multiple step types."""
    workflow = Workflow(
        name="test",
        inputs=[
            InputArg(name="bash_var", type=InputType.LINE),
            InputArg(name="prompt_var", type=InputType.LINE),
            InputArg(name="python_var", type=InputType.LINE),
        ],
        steps=[
            WorkflowStep(name="s1", bash="echo {{ bash_var }}"),
            WorkflowStep(name="s2", prompt="{{ prompt_var }}"),
            WorkflowStep(name="s3", python="print({{ python_var }})"),
        ],
    )
    used = _collect_used_variables(workflow)
    assert "bash_var" in used
    assert "prompt_var" in used
    assert "python_var" in used


def test_collect_used_variables_excludes_loop_vars() -> None:
    """Test that loop variables (item, loop) are not collected."""
    workflow = Workflow(
        name="test",
        inputs=[InputArg(name="items", type=InputType.LINE)],
        steps=[
            WorkflowStep(
                name="step1",
                bash="echo {{ item }} {{ loop.index }}",
                for_loop={"item": "items"},
            )
        ],
    )
    used = _collect_used_variables(workflow)
    assert "item" not in used
    assert "loop" not in used


def test_detect_unused_inputs_finds_unused() -> None:
    """Test detection of unused inputs."""
    workflow = Workflow(
        name="test",
        inputs=[
            InputArg(name="used_input", type=InputType.LINE),
            InputArg(name="unused_input", type=InputType.LINE),
        ],
        steps=[WorkflowStep(name="step1", bash="echo {{ used_input }}")],
    )
    used_vars = _collect_used_variables(workflow)
    unused = _detect_unused_inputs(workflow, used_vars)
    assert "unused_input" in unused
    assert "used_input" not in unused


def test_detect_unused_inputs_ignores_step_inputs() -> None:
    """Test that step inputs (auto-generated) are not flagged as unused."""
    workflow = Workflow(
        name="test",
        inputs=[
            InputArg(name="regular_input", type=InputType.LINE),
            InputArg(name="step_input", type=InputType.LINE, is_step_input=True),
        ],
        steps=[WorkflowStep(name="step1", bash="echo hi")],
    )
    used_vars = _collect_used_variables(workflow)
    unused = _detect_unused_inputs(workflow, used_vars)
    # step_input should not be in unused even though not referenced
    assert "step_input" not in unused
    # regular_input is unused and should be detected
    assert "regular_input" in unused


def test_collect_used_variables_from_condition() -> None:
    """Test that variables in if: conditions are collected."""
    workflow = Workflow(
        name="test",
        inputs=[InputArg(name="flag", type=InputType.BOOL)],
        steps=[
            WorkflowStep(
                name="step1",
                bash="echo hello",
                condition="{{ flag }}",
            )
        ],
    )
    used = _collect_used_variables(workflow)
    assert "flag" in used


def test_collect_used_variables_from_for_loop() -> None:
    """Test that variables in for: expressions are collected."""
    workflow = Workflow(
        name="test",
        inputs=[InputArg(name="items_list", type=InputType.LINE)],
        steps=[
            WorkflowStep(
                name="step1",
                bash="echo {{ item }}",
                for_loop={"item": "{{ items_list }}"},
            )
        ],
    )
    used = _collect_used_variables(workflow)
    assert "items_list" in used


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


def test_workflow_local_xprompt_with_scope_resolves_step_outputs() -> None:
    """Workflow-local xprompts with Jinja2 refs resolve via scope."""
    from xprompt.processor import process_xprompt_references

    xprompts = {
        "_research_files": XPrompt(
            name="_research_files",
            content="Files: {{ research.api_research.file_path }}",
        ),
    }
    scope = {
        "research": {
            "api_research": {"file_path": "/tmp/test.py"},
        },
    }
    result = process_xprompt_references(
        "Analyze #_research_files",
        extra_xprompts=xprompts,
        scope=scope,
    )
    assert "Files: /tmp/test.py" in result
    assert "#_research_files" not in result


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


def test_detect_unused_xprompts_finds_unused() -> None:
    """Workflow-local xprompt never referenced → error."""
    workflow = Workflow(
        name="test",
        steps=[WorkflowStep(name="step1", bash="echo hi")],
        xprompts={
            "_unused": XPrompt(name="_unused", content="some content"),
        },
    )
    xprompts = dict(workflow.xprompts)
    errors = _detect_unused_xprompts(workflow, xprompts)
    assert len(errors) == 1
    assert "_unused" in errors[0]


def test_detect_unused_xprompts_used_in_step() -> None:
    """Xprompt referenced in step content → no error."""
    workflow = Workflow(
        name="test",
        steps=[WorkflowStep(name="step1", prompt="Use #_helper here")],
        xprompts={
            "_helper": XPrompt(name="_helper", content="I help"),
        },
    )
    xprompts = dict(workflow.xprompts)
    errors = _detect_unused_xprompts(workflow, xprompts)
    assert errors == []


def test_detect_unused_xprompts_used_by_other_xprompt() -> None:
    """Xprompt referenced by another xprompt → no error."""
    workflow = Workflow(
        name="test",
        steps=[WorkflowStep(name="step1", prompt="Use #_outer here")],
        xprompts={
            "_base": XPrompt(name="_base", content="base content"),
            "_outer": XPrompt(name="_outer", content="wraps #_base"),
        },
    )
    xprompts = dict(workflow.xprompts)
    errors = _detect_unused_xprompts(workflow, xprompts)
    assert errors == []


def test_detect_unused_xprompt_inputs_finds_unused() -> None:
    """Xprompt input not in content → error."""
    workflow = Workflow(
        name="test",
        steps=[],
        xprompts={
            "_helper": XPrompt(
                name="_helper",
                content="no vars here",
                inputs=[InputArg(name="unused_arg", type=InputType.LINE)],
            ),
        },
    )
    errors = _detect_unused_xprompt_inputs(workflow)
    assert len(errors) == 1
    assert "unused_arg" in errors[0]
    assert "_helper" in errors[0]


def test_detect_unused_xprompt_inputs_used() -> None:
    """Xprompt input referenced in content → no error."""
    workflow = Workflow(
        name="test",
        steps=[],
        xprompts={
            "_helper": XPrompt(
                name="_helper",
                content="Use {{ my_arg }} here",
                inputs=[InputArg(name="my_arg", type=InputType.LINE)],
            ),
        },
    )
    errors = _detect_unused_xprompt_inputs(workflow)
    assert errors == []


def test_validate_workflow_raises_on_unused_xprompt() -> None:
    """Integration: validate_workflow() raises on unused workflow-local xprompt."""
    workflow = Workflow(
        name="test",
        steps=[WorkflowStep(name="step1", bash="echo hi")],
        xprompts={
            "_orphan": XPrompt(name="_orphan", content="never used"),
        },
    )
    with pytest.raises(WorkflowValidationError, match="_orphan"):
        from xprompt.workflow_validator import validate_workflow

        validate_workflow(workflow)


def test_validate_workflow_raises_on_unused_xprompt_input() -> None:
    """Integration: validate_workflow() raises on unused xprompt input."""
    workflow = Workflow(
        name="test",
        steps=[WorkflowStep(name="step1", prompt="Use #_helper here")],
        xprompts={
            "_helper": XPrompt(
                name="_helper",
                content="no vars",
                inputs=[InputArg(name="dead_input", type=InputType.LINE)],
            ),
        },
    )
    with pytest.raises(WorkflowValidationError, match="dead_input"):
        from xprompt.workflow_validator import validate_workflow

        validate_workflow(workflow)


def test_validate_xprompt_names_missing_underscore() -> None:
    """Xprompt name without '_' prefix → error."""
    workflow = Workflow(
        name="test",
        steps=[WorkflowStep(name="step1", bash="echo hi")],
        xprompts={
            "foo": XPrompt(name="foo", content="some content"),
        },
    )
    errors = _validate_xprompt_names(workflow)
    assert len(errors) == 1
    assert "foo" in errors[0]
    assert "must start with '_'" in errors[0]
    assert "'_foo'" in errors[0]


def test_validate_xprompt_names_valid() -> None:
    """Xprompt name with '_' prefix → no error."""
    workflow = Workflow(
        name="test",
        steps=[WorkflowStep(name="step1", bash="echo hi")],
        xprompts={
            "_foo": XPrompt(name="_foo", content="some content"),
        },
    )
    errors = _validate_xprompt_names(workflow)
    assert errors == []


def test_validate_workflow_raises_on_xprompt_missing_underscore() -> None:
    """Integration: validate_workflow() raises on xprompt name missing '_' prefix."""
    workflow = Workflow(
        name="test",
        steps=[WorkflowStep(name="step1", bash="echo hi")],
        xprompts={
            "bad_name": XPrompt(name="bad_name", content="some content"),
        },
    )
    with pytest.raises(WorkflowValidationError, match="must start with '_'"):
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
