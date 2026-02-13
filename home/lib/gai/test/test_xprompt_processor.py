"""Tests for the xprompt.processor module."""

import re
from unittest.mock import MagicMock, patch

from xprompt._jinja import validate_and_convert_args
from xprompt._parsing import (
    DOUBLE_COLON_SHORTHAND_PATTERN,
    SHORTHAND_PATTERN,
    _find_shorthand_text_end,
    preprocess_shorthand_syntax,
)
from xprompt.models import UNSET, InputArg, InputType, XPrompt
from xprompt.processor import (
    _XPROMPT_PATTERN,
    WorkflowResult,
    _flatten_anonymous_workflow,
)
from xprompt.workflow_executor_utils import render_template
from xprompt.workflow_models import Workflow, WorkflowStep


def test_xprompt_pattern_simple_name() -> None:
    """Test that simple xprompt names match."""
    match = re.search(_XPROMPT_PATTERN, "#foo")
    assert match is not None
    assert match.group(1) == "foo"


def test_xprompt_pattern_with_underscore() -> None:
    """Test that xprompt names with underscores match."""
    match = re.search(_XPROMPT_PATTERN, "#foo_bar")
    assert match is not None
    assert match.group(1) == "foo_bar"


def test_xprompt_pattern_with_numbers() -> None:
    """Test that xprompt names with numbers match."""
    match = re.search(_XPROMPT_PATTERN, "#foo123")
    assert match is not None
    assert match.group(1) == "foo123"


def test_xprompt_pattern_namespaced_single() -> None:
    """Test that single-level namespaced xprompts match."""
    match = re.search(_XPROMPT_PATTERN, "#mentor/aaa")
    assert match is not None
    assert match.group(1) == "mentor/aaa"


def test_xprompt_pattern_namespaced_multi() -> None:
    """Test that multi-level namespaced xprompts match."""
    match = re.search(_XPROMPT_PATTERN, "#foo/bar/baz")
    assert match is not None
    assert match.group(1) == "foo/bar/baz"


def test_xprompt_pattern_namespaced_with_underscore() -> None:
    """Test that namespaced xprompts with underscores match."""
    match = re.search(_XPROMPT_PATTERN, "#my_namespace/my_xprompt")
    assert match is not None
    assert match.group(1) == "my_namespace/my_xprompt"


def test_xprompt_pattern_namespaced_with_numbers() -> None:
    """Test that namespaced xprompts with numbers match."""
    match = re.search(_XPROMPT_PATTERN, "#ns1/prompt2")
    assert match is not None
    assert match.group(1) == "ns1/prompt2"


def test_xprompt_pattern_namespaced_with_args() -> None:
    """Test that namespaced xprompts with parentheses match."""
    match = re.search(_XPROMPT_PATTERN, "#mentor/aaa(arg1)")
    assert match is not None
    assert match.group(1) == "mentor/aaa"
    assert match.group(2) == "("  # Open paren captured


def test_xprompt_pattern_namespaced_with_colon_arg() -> None:
    """Test that namespaced xprompts with colon args match."""
    match = re.search(_XPROMPT_PATTERN, "#foo/bar:value")
    assert match is not None
    assert match.group(1) == "foo/bar"
    assert match.group(3) == "value"


def test_xprompt_pattern_namespaced_with_plus() -> None:
    """Test that namespaced xprompts with plus suffix match."""
    match = re.search(_XPROMPT_PATTERN, "#foo/bar+")
    assert match is not None
    assert match.group(1) == "foo/bar"
    assert match.group(4) == "+"


def test_xprompt_pattern_after_whitespace() -> None:
    """Test that xprompts match after whitespace."""
    match = re.search(_XPROMPT_PATTERN, "text #mentor/aaa")
    assert match is not None
    assert match.group(1) == "mentor/aaa"


def test_xprompt_pattern_at_start() -> None:
    """Test that xprompts match at start of string."""
    match = re.search(_XPROMPT_PATTERN, "#mentor/aaa text")
    assert match is not None
    assert match.group(1) == "mentor/aaa"


def test_xprompt_pattern_after_open_paren() -> None:
    """Test that xprompts match after open parenthesis."""
    match = re.search(_XPROMPT_PATTERN, "(#mentor/aaa)")
    assert match is not None
    assert match.group(1) == "mentor/aaa"


def test_xprompt_pattern_after_quote() -> None:
    """Test that xprompts match after quote."""
    match = re.search(_XPROMPT_PATTERN, '"#mentor/aaa"')
    assert match is not None
    assert match.group(1) == "mentor/aaa"


def test_xprompt_pattern_colon_arg_strips_trailing_period() -> None:
    """Test that trailing period is not captured in colon arg."""
    match = re.search(_XPROMPT_PATTERN, "#clr:832098883.")
    assert match is not None
    assert match.group(1) == "clr"
    assert match.group(3) == "832098883"


def test_xprompt_pattern_not_after_letter() -> None:
    """Test that xprompts don't match after letter (e.g., C#)."""
    match = re.search(_XPROMPT_PATTERN, "C#mentor")
    assert match is None


def test_xprompt_pattern_not_double_slash() -> None:
    """Test that double slashes don't match (invalid namespace)."""
    match = re.search(_XPROMPT_PATTERN, "#foo//bar")
    assert match is not None
    # Should only match #foo, not #foo//bar
    assert match.group(1) == "foo"


def test_xprompt_pattern_not_leading_slash() -> None:
    """Test that leading slash doesn't match."""
    match = re.search(_XPROMPT_PATTERN, "#/foo")
    assert match is None


def test_xprompt_pattern_not_trailing_slash() -> None:
    """Test that trailing slash is not part of the match."""
    match = re.search(_XPROMPT_PATTERN, "#foo/")
    assert match is not None
    # Should only match #foo, the trailing slash is not valid namespace
    assert match.group(1) == "foo"


def testvalidate_and_convert_args_positional_to_named() -> None:
    """Test that positional args are mapped to named args using input definitions.

    When an xprompt has YAML frontmatter with input definitions like:
        input:
          - name: prompt
            type: text

    And a positional argument is passed like #xprompt([[text]]), the text
    should be accessible both as _1 (positional) and as the named variable
    'prompt' defined in the input specification.
    """
    xprompt = XPrompt(
        name="mentor",
        content="{{ prompt }}",
        inputs=[InputArg(name="prompt", type=InputType.TEXT)],
    )
    positional_args = ["This is my prompt text"]
    named_args: dict[str, str] = {}

    conv_positional, conv_named = validate_and_convert_args(
        xprompt, positional_args, named_args
    )

    # The positional arg should be in both lists
    assert conv_positional == ["This is my prompt text"]
    # The positional arg should also be mapped to the named arg 'prompt'
    assert conv_named == {"prompt": "This is my prompt text"}


def testvalidate_and_convert_args_multiple_positional_to_named() -> None:
    """Test that multiple positional args are mapped to their respective names."""
    xprompt = XPrompt(
        name="test",
        content="{{ first }} and {{ second }}",
        inputs=[
            InputArg(name="first", type=InputType.LINE),
            InputArg(name="second", type=InputType.LINE),
        ],
    )
    positional_args = ["value1", "value2"]
    named_args: dict[str, str] = {}

    conv_positional, conv_named = validate_and_convert_args(
        xprompt, positional_args, named_args
    )

    assert conv_positional == ["value1", "value2"]
    assert conv_named == {"first": "value1", "second": "value2"}


def testvalidate_and_convert_args_explicit_named_arg_not_overwritten() -> None:
    """Test that explicit named args take precedence over positional mapping."""
    xprompt = XPrompt(
        name="test",
        content="{{ prompt }}",
        inputs=[InputArg(name="prompt", type=InputType.TEXT)],
    )
    # Both a positional and a named arg provided for the same input
    positional_args = ["positional value"]
    named_args = {"prompt": "explicit named value"}

    conv_positional, conv_named = validate_and_convert_args(
        xprompt, positional_args, named_args
    )

    # Positional still maps to named, but then named_args processing overwrites
    assert conv_positional == ["positional value"]
    assert conv_named == {"prompt": "explicit named value"}


# --- Shorthand syntax tests ---


def test_shorthand_pattern_at_start_of_string() -> None:
    """Test that shorthand pattern matches at start of string."""
    match = re.search(SHORTHAND_PATTERN, "#foo: some text")
    assert match is not None
    assert match.group(1) == "foo"


def test_shorthand_pattern_after_newline() -> None:
    """Test that shorthand pattern matches after newline."""
    match = re.search(SHORTHAND_PATTERN, "prefix\n#bar: text here")
    assert match is not None
    assert match.group(1) == "bar"


def test_shorthand_pattern_namespaced() -> None:
    """Test that shorthand pattern matches namespaced xprompts."""
    match = re.search(SHORTHAND_PATTERN, "#mentor/aaa: some text")
    assert match is not None
    assert match.group(1) == "mentor/aaa"


def test_shorthand_pattern_not_mid_line() -> None:
    """Test that shorthand pattern doesn't match mid-line."""
    match = re.search(SHORTHAND_PATTERN, "text #foo: bar")
    assert match is None


def test_shorthand_pattern_requires_space_after_colon() -> None:
    """Test that pattern requires space after colon (distinguishes from :arg)."""
    # Without space - should not match shorthand pattern
    match = re.search(SHORTHAND_PATTERN, "#foo:bar")
    assert match is None


def testfind_shorthand_text_end_at_blank_line() -> None:
    """Test finding end at blank line."""
    prompt = "some text here\n\nmore text"
    end = _find_shorthand_text_end(prompt, 0)
    assert end == 14
    assert prompt[end : end + 2] == "\n\n"


def testfind_shorthand_text_end_at_eof() -> None:
    """Test finding end at end of string."""
    prompt = "no blank line here"
    end = _find_shorthand_text_end(prompt, 0)
    assert end == len(prompt)


def test_preprocess_shorthand_single_line() -> None:
    """Test preprocessing single-line shorthand."""
    prompt = "#foo: simple text"
    result = preprocess_shorthand_syntax(prompt, {"foo"})
    assert result == "#foo([[simple text]])"


def test_preprocess_shorthand_multiline_until_blank() -> None:
    """Test preprocessing multi-line shorthand until blank line."""
    prompt = "#foo: line one\nline two\n\nother text"
    result = preprocess_shorthand_syntax(prompt, {"foo"})
    assert result == "#foo([[line one\n  line two]])\n\nother text"


def test_preprocess_shorthand_multiline_until_eof() -> None:
    """Test preprocessing multi-line shorthand until end of string."""
    prompt = "#foo: line one\nline two\nline three"
    result = preprocess_shorthand_syntax(prompt, {"foo"})
    assert result == "#foo([[line one\n  line two\n  line three]])"


def test_preprocess_shorthand_unknown_name_unchanged() -> None:
    """Test that unknown xprompt names are not processed."""
    prompt = "#unknown: some text"
    result = preprocess_shorthand_syntax(prompt, {"foo", "bar"})
    assert result == "#unknown: some text"


def test_preprocess_shorthand_namespaced() -> None:
    """Test preprocessing namespaced xprompt shorthand."""
    prompt = "#mentor/aaa: review this code"
    result = preprocess_shorthand_syntax(prompt, {"mentor/aaa"})
    assert result == "#mentor/aaa([[review this code]])"


def test_preprocess_shorthand_multiple_in_prompt() -> None:
    """Test preprocessing multiple shorthands in one prompt."""
    prompt = "#foo: text one\n\n#bar: text two"
    result = preprocess_shorthand_syntax(prompt, {"foo", "bar"})
    assert result == "#foo([[text one]])\n\n#bar([[text two]])"


def test_preprocess_shorthand_not_at_line_start() -> None:
    """Test that shorthand mid-line is not processed."""
    prompt = "Use #foo: inline"
    result = preprocess_shorthand_syntax(prompt, {"foo"})
    # Should remain unchanged because #foo: is not at line start
    assert result == "Use #foo: inline"


def test_preprocess_shorthand_preserves_trailing_content() -> None:
    """Test that content after blank line terminator is preserved."""
    # \n\n terminates the shorthand, third \n and "more text" are preserved
    prompt = "#foo: line one\n\n\nmore text"
    result = preprocess_shorthand_syntax(prompt, {"foo"})
    # Should end at first \n\n, keeping the trailing \n before "more text"
    assert result == "#foo([[line one]])\n\n\nmore text"


# --- Double-colon shorthand pattern tests ---


def test_double_colon_shorthand_pattern_at_start() -> None:
    """Test that DOUBLE_COLON_SHORTHAND_PATTERN matches at start of string."""
    match = re.search(DOUBLE_COLON_SHORTHAND_PATTERN, "#foo:: some text")
    assert match is not None
    assert match.group(1) == "foo"


def test_double_colon_shorthand_pattern_not_single_colon() -> None:
    """Test that DOUBLE_COLON_SHORTHAND_PATTERN does NOT match single colon."""
    match = re.search(DOUBLE_COLON_SHORTHAND_PATTERN, "#foo: some text")
    assert match is None


# --- WorkflowResult tests ---


def test_workflow_result_construction() -> None:
    """Test basic WorkflowResult dataclass construction."""
    result = WorkflowResult(
        output='{"key": "value"}',
        response_text="Some response",
        artifacts_dir="/tmp/artifacts",
    )
    assert result.output == '{"key": "value"}'
    assert result.response_text == "Some response"
    assert result.artifacts_dir == "/tmp/artifacts"


def test_workflow_result_none_response_text() -> None:
    """Test WorkflowResult with None response_text."""
    result = WorkflowResult(output="", response_text=None, artifacts_dir="/tmp/x")
    assert result.response_text is None


# --- _flatten_anonymous_workflow tests ---


def _make_anonymous_workflow(prompt: str) -> Workflow:
    """Helper to create an anonymous workflow with a single prompt step."""
    return Workflow(
        name="tmp_abc123",
        steps=[WorkflowStep(name="main", prompt=prompt)],
    )


def test_flatten_anonymous_workflow_returns_none_for_non_single_step() -> None:
    """Test that multi-step workflows are not flattened."""
    workflow = Workflow(
        name="tmp_abc",
        steps=[
            WorkflowStep(name="step1", prompt="first"),
            WorkflowStep(name="step2", prompt="second"),
        ],
    )
    result = _flatten_anonymous_workflow(workflow)
    assert result is None


def test_flatten_anonymous_workflow_returns_none_for_non_prompt_step() -> None:
    """Test that non-prompt steps (e.g., bash) are not flattened."""
    workflow = Workflow(
        name="tmp_abc",
        steps=[WorkflowStep(name="main", bash="echo hello")],
    )
    result = _flatten_anonymous_workflow(workflow)
    assert result is None


def test_flatten_anonymous_workflow_returns_none_for_non_hash_prompt() -> None:
    """Test that prompts not starting with # are not flattened."""
    workflow = _make_anonymous_workflow("just a plain prompt")
    result = _flatten_anonymous_workflow(workflow)
    assert result is None


@patch("xprompt.loader.get_all_prompts")
def test_flatten_anonymous_workflow_returns_none_for_unknown_ref(
    mock_get_all_prompts: MagicMock,
) -> None:
    """Test that references to unknown workflows return None."""
    mock_get_all_prompts.return_value = {}
    workflow = _make_anonymous_workflow("#unknown_workflow")
    result = _flatten_anonymous_workflow(workflow)
    assert result is None


@patch("xprompt.loader.get_all_prompts")
def test_flatten_anonymous_workflow_returns_none_for_prompt_part_ref(
    mock_get_all_prompts: MagicMock,
) -> None:
    """Test that references to simple xprompts (with prompt_part) return None."""
    # A simple xprompt has a prompt_part step, not a prompt step
    simple_xprompt_wf = Workflow(
        name="greeting",
        steps=[WorkflowStep(name="main", prompt_part="Hello {{ name }}")],
    )
    mock_get_all_prompts.return_value = {"greeting": simple_xprompt_wf}
    workflow = _make_anonymous_workflow("#greeting")
    result = _flatten_anonymous_workflow(workflow)
    assert result is None


@patch("xprompt.loader.get_all_prompts")
def test_flatten_anonymous_workflow_returns_workflow_for_pure_multistep(
    mock_get_all_prompts: MagicMock,
) -> None:
    """Test that a pure multi-step workflow reference is flattened."""
    target_wf = Workflow(
        name="split",
        inputs=[InputArg(name="desc", type=InputType.LINE)],
        steps=[
            WorkflowStep(name="analyze", prompt="Analyze: {{ desc }}"),
            WorkflowStep(name="execute", prompt="Execute based on analysis"),
        ],
    )
    mock_get_all_prompts.return_value = {"split": target_wf}
    workflow = _make_anonymous_workflow("#split")
    result = _flatten_anonymous_workflow(workflow)
    assert result is not None
    ref_wf, pos_args, named_args = result
    assert ref_wf.name == "split"
    assert pos_args == []
    assert named_args == {}


@patch("xprompt.loader.get_all_prompts")
def test_flatten_anonymous_workflow_passes_positional_args(
    mock_get_all_prompts: MagicMock,
) -> None:
    """Test that positional args from the reference are returned."""
    target_wf = Workflow(
        name="split",
        inputs=[InputArg(name="split_desc", type=InputType.LINE)],
        steps=[
            WorkflowStep(name="analyze", prompt="Analyze: {{ split_desc }}"),
            WorkflowStep(name="execute", prompt="Execute"),
        ],
    )
    mock_get_all_prompts.return_value = {"split": target_wf}
    workflow = _make_anonymous_workflow("#split(my description)")
    result = _flatten_anonymous_workflow(workflow)
    assert result is not None
    ref_wf, pos_args, named_args = result
    assert ref_wf.name == "split"
    assert pos_args == ["my description"]
    assert named_args == {}


@patch("xprompt.loader.get_all_prompts")
def test_flatten_anonymous_workflow_passes_named_args(
    mock_get_all_prompts: MagicMock,
) -> None:
    """Test that named args from the reference are returned."""
    target_wf = Workflow(
        name="split",
        inputs=[InputArg(name="split_desc", type=InputType.LINE)],
        steps=[
            WorkflowStep(name="analyze", prompt="Analyze: {{ split_desc }}"),
            WorkflowStep(name="execute", prompt="Execute"),
        ],
    )
    mock_get_all_prompts.return_value = {"split": target_wf}
    workflow = _make_anonymous_workflow("#split(split_desc='test value')")
    result = _flatten_anonymous_workflow(workflow)
    assert result is not None
    ref_wf, pos_args, named_args = result
    assert ref_wf.name == "split"
    assert pos_args == []
    assert named_args == {"split_desc": "test value"}


# --- Simple xprompt positional arg rendering tests ---


def _build_simple_xprompt_render_ctx(
    workflow: Workflow,
    positional_args: list[str],
    named_args: dict[str, str],
) -> dict[str, object]:
    """Replicate the render context logic from execute_workflow for testing."""
    render_ctx: dict[str, object] = dict(named_args)
    for i, value in enumerate(positional_args):
        if i < len(workflow.inputs):
            input_arg = workflow.inputs[i]
            if input_arg.name not in render_ctx:
                render_ctx[input_arg.name] = value
    for input_arg in workflow.inputs:
        if input_arg.name not in render_ctx and input_arg.default is not UNSET:
            render_ctx[input_arg.name] = (
                "null" if input_arg.default is None else str(input_arg.default)
            )
    return render_ctx


def test_simple_xprompt_positional_arg_renders_template() -> None:
    """Test that positional args are mapped to input names for simple xprompts.

    This exercises the fix for the #presubmit xprompt bug where positional args
    were not mapped before render_template was called.
    """
    workflow = Workflow(
        name="presubmit",
        inputs=[InputArg(name="presubmit_output_path", type=InputType.PATH)],
        steps=[
            WorkflowStep(
                name="main",
                prompt_part=("Fix the errors in @{{ presubmit_output_path }} file."),
            )
        ],
    )
    positional_args = ["~/.gai/hooks/presubmit.out"]
    named_args: dict[str, str] = {}

    render_ctx = _build_simple_xprompt_render_ctx(workflow, positional_args, named_args)
    content = workflow.get_prompt_part_content()
    rendered = render_template(content, render_ctx)

    assert rendered == "Fix the errors in @~/.gai/hooks/presubmit.out file."


def test_simple_xprompt_named_arg_takes_precedence() -> None:
    """Test that named args take precedence over positional for simple xprompts."""
    workflow = Workflow(
        name="test",
        inputs=[InputArg(name="path", type=InputType.PATH)],
        steps=[WorkflowStep(name="main", prompt_part="Check @{{ path }}.")],
    )
    positional_args = ["positional_path"]
    named_args = {"path": "named_path"}

    render_ctx = _build_simple_xprompt_render_ctx(workflow, positional_args, named_args)
    content = workflow.get_prompt_part_content()
    rendered = render_template(content, render_ctx)

    assert rendered == "Check @named_path."


def test_simple_xprompt_default_applied_when_no_arg() -> None:
    """Test that defaults are applied for missing inputs in simple xprompts."""
    workflow = Workflow(
        name="test",
        inputs=[
            InputArg(name="path", type=InputType.PATH),
            InputArg(name="mode", type=InputType.LINE, default="strict"),
        ],
        steps=[
            WorkflowStep(
                name="main",
                prompt_part="Check @{{ path }} in {{ mode }} mode.",
            )
        ],
    )
    positional_args = ["/some/file"]
    named_args: dict[str, str] = {}

    render_ctx = _build_simple_xprompt_render_ctx(workflow, positional_args, named_args)
    content = workflow.get_prompt_part_content()
    rendered = render_template(content, render_ctx)

    assert rendered == "Check @/some/file in strict mode."


def test_simple_xprompt_null_default_renders_as_null() -> None:
    """Test that None defaults render as 'null' string."""
    workflow = Workflow(
        name="test",
        inputs=[
            InputArg(name="val", type=InputType.LINE, default=None),
        ],
        steps=[WorkflowStep(name="main", prompt_part="Value is {{ val }}.")],
    )
    render_ctx = _build_simple_xprompt_render_ctx(workflow, [], {})
    content = workflow.get_prompt_part_content()
    rendered = render_template(content, render_ctx)

    assert rendered == "Value is null."
