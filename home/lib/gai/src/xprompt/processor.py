"""XPrompt reference processing for prompts."""

import re
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from rich_utils import print_status
from shared_utils import apply_section_marker_handling

from ._exceptions import XPromptError
from ._jinja import (
    is_jinja2_template,
    render_toplevel_jinja2,
    substitute_placeholders,
    validate_and_convert_args,
)
from ._parsing import (
    find_matching_paren_for_args,
    parse_args,
    parse_workflow_reference,
    preprocess_shorthand_syntax,
)
from .loader import get_all_workflows, get_all_xprompts
from .models import UNSET, XPrompt
from .workflow_models import WorkflowStep, WorkflowValidationError

if TYPE_CHECKING:
    from .workflow_models import Workflow

# Maximum number of expansion iterations to prevent infinite loops
_MAX_EXPANSION_ITERATIONS = 100

# Pattern to match xprompt references: #name, #name(, #name:arg, or #name+
# Must be at start of string, after whitespace, or after certain punctuation
# Note: No space allowed after # (to avoid matching markdown headings)
# Supports:
#   - #name - simple xprompt (no args)
#   - #name( - parenthesis syntax start (matching ) found programmatically)
#   - #name:arg - colon syntax for single arg (word-like chars only)
#   - #name:`arg` - colon syntax with backtick-delimited arg (any content)
#   - #name+ - plus syntax, equivalent to #name:true
_XPROMPT_PATTERN = (
    r"(?:^|(?<=\s)|(?<=[(\[{\"']))"  # Must be at start, after whitespace, or after ([{"'
    r"#([a-zA-Z_][a-zA-Z0-9_]*(?:/[a-zA-Z_][a-zA-Z0-9_]*)*)"  # Group 1: xprompt name with optional namespace
    r"(?:(\()|:(`[^`]*`|[a-zA-Z0-9_.-]*[a-zA-Z0-9_-])|(\+))?"  # Group 2: open paren OR Group 3: colon arg (backtick or word) OR Group 4: plus
)


def _expand_single_xprompt(
    xprompt: XPrompt,
    positional_args: list[str],
    named_args: dict[str, str],
    scope: dict[str, Any] | None = None,
) -> str:
    """Expand a single xprompt with its arguments.

    Args:
        xprompt: The XPrompt to expand.
        positional_args: List of positional argument values.
        named_args: Dictionary of named argument values.
        scope: Optional base context (e.g., workflow execution context).
            Xprompt-specific args take priority over scope values.

    Returns:
        The expanded xprompt content.

    Raises:
        _XPromptArgumentError: If arguments don't match placeholders.
    """
    # Validate and convert args if xprompt has typed inputs
    conv_positional, conv_named = validate_and_convert_args(
        xprompt, positional_args, named_args
    )

    return substitute_placeholders(
        xprompt.content, conv_positional, conv_named, xprompt.name, scope=scope
    )


def process_xprompt_references(
    prompt: str,
    extra_xprompts: dict[str, XPrompt] | None = None,
    scope: dict[str, Any] | None = None,
) -> str:
    """Process xprompt references in the prompt.

    Expands all #xprompt_name and #xprompt_name(arg1, arg2) patterns
    with their corresponding content from files or config.

    Supports:
    - Simple xprompts: #foo
    - XPrompts with positional args: #bar(arg1, arg2)
    - XPrompts with named args: #bar(name=value, other="text")
    - Mixed args: #bar(pos1, name=value)
    - Text block args: #bar([[multi-line content]])
    - Colon syntax for single arg: #foo:arg
    - Plus syntax (equivalent to :true): #foo+
    - Legacy placeholders: {1}, {2}, {1:default}
    - Jinja2 templates: {{ name }}, {% if %}, etc.
    - Recursive expansion (xprompts can reference other xprompts)

    Args:
        prompt: The prompt text to process
        extra_xprompts: Optional additional xprompts that take highest priority
            (e.g., workflow-local xprompts).
        scope: Optional base context (e.g., workflow execution context) passed
            through to Jinja2 template rendering. Xprompt-specific args take
            priority over scope values.

    Returns:
        The transformed prompt with xprompts expanded

    Raises:
        SystemExit: If any xprompt processing error occurs
    """
    xprompts = get_all_xprompts()
    if extra_xprompts:
        xprompts.update(extra_xprompts)
    if not xprompts:
        return prompt  # No xprompts defined

    # Check if there are any potential xprompt references
    if "#" not in prompt:
        return prompt

    iteration = 0
    while iteration < _MAX_EXPANSION_ITERATIONS:
        # Pre-process shorthand syntax on each iteration
        # (expanded content may contain shorthand that needs processing)
        prompt = preprocess_shorthand_syntax(prompt, set(xprompts.keys()))

        # Find all xprompt references
        matches = list(re.finditer(_XPROMPT_PATTERN, prompt, re.MULTILINE))

        if not matches:
            break  # No more xprompts to expand

        # Check if any matches are actual xprompts we know about
        has_known_xprompt = False
        for match in matches:
            name = match.group(1)
            if name in xprompts:
                has_known_xprompt = True
                break

        if not has_known_xprompt:
            break  # No known xprompts to expand

        # Expand from last to first to preserve positions
        try:
            for match in reversed(matches):
                name = match.group(1)

                # Skip if this isn't a known xprompt
                if name not in xprompts:
                    continue

                xprompt = xprompts[name]

                # Extract arguments from parenthesis, colon, or plus syntax
                # Group 2: open paren marker, Group 3: colon arg, Group 4: plus
                has_open_paren = match.group(2) is not None
                colon_arg = match.group(3)
                plus_suffix = match.group(4)

                # Track the actual end position (may extend beyond match.end())
                match_end = match.end()

                positional_args: list[str]
                named_args: dict[str, str]
                if has_open_paren:
                    # Two-phase parsing: regex matched #name(, now find matching )
                    paren_start = match.end() - 1  # Position of the '('
                    paren_end = find_matching_paren_for_args(prompt, paren_start)
                    if paren_end is None:
                        # Unclosed paren - treat as no args
                        positional_args, named_args = [], {}
                    else:
                        # Extract content between ( and )
                        paren_content = prompt[paren_start + 1 : paren_end]
                        positional_args, named_args = parse_args(paren_content)
                        match_end = paren_end + 1  # Include the closing )
                elif colon_arg is not None:
                    # Strip backticks if present (backtick-delimited syntax)
                    if colon_arg.startswith("`") and colon_arg.endswith("`"):
                        colon_arg = colon_arg[1:-1]
                    positional_args, named_args = [colon_arg], {}
                elif plus_suffix is not None:
                    positional_args, named_args = ["true"], {}
                else:
                    positional_args, named_args = [], {}

                expanded = _expand_single_xprompt(
                    xprompt, positional_args, named_args, scope=scope
                )

                # Handle section markers (### or ---) with proper line positioning
                is_at_line_start = (
                    match.start() == 0 or prompt[match.start() - 1] == "\n"
                )
                expanded = apply_section_marker_handling(expanded, is_at_line_start)

                prompt = prompt[: match.start()] + expanded + prompt[match_end:]
        except XPromptError as e:
            print_status(str(e), "error")
            sys.exit(1)

        iteration += 1

    if iteration >= _MAX_EXPANSION_ITERATIONS:
        print_status(
            f"Maximum xprompt expansion depth ({_MAX_EXPANSION_ITERATIONS}) exceeded. "
            "Check for circular references.",
            "error",
        )
        sys.exit(1)

    return prompt


def is_workflow_reference(name: str) -> bool:
    """Check if a name refers to a workflow.

    Args:
        name: The xprompt/workflow name to check.

    Returns:
        True if the name matches a workflow, False otherwise.
    """
    workflows = get_all_workflows()
    return name in workflows


def _flatten_anonymous_workflow(
    workflow: "Workflow",
    project: str | None = None,
) -> "tuple[Workflow, list[str], dict[str, str]] | None":
    """Flatten an anonymous workflow that wraps a single workflow reference.

    If the anonymous workflow's single prompt step is entirely a ``#name(args)``
    reference to a pure multi-step workflow (one without a prompt_part), return
    that referenced workflow with the parsed args. Otherwise return None.

    Args:
        workflow: The anonymous workflow to check.
        project: Optional project name for loading prompts.

    Returns:
        Tuple of (referenced_workflow, positional_args, named_args) if
        flattening is appropriate, None otherwise.
    """
    from .loader import get_all_prompts

    # Only flatten single-step prompt workflows
    if len(workflow.steps) != 1 or not workflow.steps[0].is_prompt_step():
        return None

    prompt_text = (workflow.steps[0].prompt or "").strip()

    # Must be exactly a single #name or #name(args) reference
    if not prompt_text.startswith("#"):
        return None

    # Reject if there's extra text beyond the reference
    ref_text = prompt_text[1:]  # Strip leading #
    wf_name, positional_args, named_args = parse_workflow_reference(ref_text)

    # Reconstruct what the reference should look like and verify it matches
    # (i.e., no extra text around the reference)
    prompts = get_all_prompts(project=project)
    if wf_name not in prompts:
        return None

    referenced = prompts[wf_name]

    # Only flatten pure multi-step workflows (no prompt_part)
    # Workflows with prompt_part are handled by embedded workflow expansion
    if referenced.has_prompt_part():
        return None

    return referenced, positional_args, named_args


def _write_failed_workflow_state(
    workflow_name: str,
    artifacts_dir: str,
    error_message: str,
) -> None:
    """Write a workflow_state.json for validation failures.

    This ensures that the TUI can display the error when a workflow fails
    validation before execution starts.
    """
    import json
    import os
    from datetime import datetime

    state_dict = {
        "workflow_name": workflow_name,
        "status": "failed",
        "current_step_index": 0,
        "steps": [],
        "context": {},
        "artifacts_dir": artifacts_dir,
        "start_time": datetime.now().isoformat(),
        "pid": os.getpid(),
        "error": error_message,
        "is_anonymous": workflow_name.startswith("tmp_"),
    }
    state_path = os.path.join(artifacts_dir, "workflow_state.json")
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state_dict, f, indent=2)


@dataclass
class WorkflowResult:
    """Result from executing a workflow.

    Attributes:
        output: JSON string of the last step's output.
        response_text: Raw response text from the last prompt step, if any.
        artifacts_dir: Path to the artifacts directory.
    """

    output: str
    response_text: str | None
    artifacts_dir: str


def execute_workflow(
    name: str,
    positional_args: list[str],
    named_args: dict[str, str],
    artifacts_dir: str | None = None,
    *,
    silent: bool = False,
    project: str | None = None,
    workflow_obj: "Workflow | None" = None,
    hitl_override: bool | None = None,
) -> WorkflowResult:
    """Execute a workflow and return its result.

    Args:
        name: The workflow name (can be a workflow or converted xprompt).
        positional_args: Positional arguments.
        named_args: Named arguments.
        artifacts_dir: Optional directory for workflow artifacts.
        silent: If True, disable console output and use auto-approve for HITL.
            Use this when running workflows from non-interactive contexts (e.g., TUI).
        project: Optional project name for loading prompts.
        workflow_obj: Optional pre-built Workflow object (e.g., anonymous workflows).
            When provided, skips the name-based lookup.
        hitl_override: Force HITL on (True) or off (False) for all steps,
            overriding individual step ``hitl`` settings.  None preserves
            per-step behavior.

    Returns:
        WorkflowResult with output, response text, and artifacts directory.

    Raises:
        WorkflowExecutionError: If workflow execution fails.
    """
    import json
    import os
    import tempfile
    from typing import Any

    from ._step_input_loader import load_step_input_value
    from .loader import get_all_prompts
    from .workflow_executor import WorkflowExecutor
    from .workflow_hitl import CLIHITLHandler, TUIHITLHandler
    from .workflow_models import WorkflowExecutionError
    from .workflow_output import WorkflowOutputHandler
    from .workflow_validator import validate_workflow

    if workflow_obj is not None:
        workflow = workflow_obj
    else:
        # Use unified loader to get both workflows and converted xprompts
        prompts = get_all_prompts(project=project)
        if name not in prompts:
            raise WorkflowExecutionError(f"Workflow '{name}' not found")
        workflow = prompts[name]

    # Create artifacts_dir early so we can write state on validation failure
    if artifacts_dir is None:
        artifacts_dir = tempfile.mkdtemp(prefix=f"workflow-{name}-")
    else:
        os.makedirs(artifacts_dir, exist_ok=True)

    # Handle simple xprompts: convert prompt_part to prompt step so they go
    # through WorkflowExecutor (producing workflow_state.json and markers)
    if workflow.is_simple_xprompt():
        from xprompt.workflow_executor_utils import render_template
        from xprompt.workflow_models import Workflow as WfModel

        # Build render context with positional args mapped to input names
        render_ctx: dict[str, Any] = dict(named_args)
        for i, value in enumerate(positional_args):
            if i < len(workflow.inputs):
                input_arg = workflow.inputs[i]
                if input_arg.name not in render_ctx:
                    render_ctx[input_arg.name] = value
        # Apply defaults for missing inputs
        for input_arg in workflow.inputs:
            if input_arg.name not in render_ctx and input_arg.default is not UNSET:
                render_ctx[input_arg.name] = (
                    "null" if input_arg.default is None else str(input_arg.default)
                )

        content = workflow.get_prompt_part_content()
        rendered = render_template(content, render_ctx)
        workflow = WfModel(
            name=workflow.name,
            inputs=[],
            steps=[WorkflowStep(name="main", prompt=rendered)],
            source_path=workflow.source_path,
            xprompts=workflow.xprompts,
        )

    # Flatten anonymous workflows that wrap a single multi-step workflow
    # reference (e.g., "gai run '#split(...)'" → execute split directly)
    if workflow.is_anonymous():
        flattened = _flatten_anonymous_workflow(workflow, project=project)
        if flattened is not None:
            workflow, positional_args, named_args = flattened
            name = workflow.name

    # Compile-time validation with error state on failure
    try:
        validate_workflow(workflow)
    except WorkflowValidationError as e:
        _write_failed_workflow_state(
            workflow_name=name,
            artifacts_dir=artifacts_dir,
            error_message=str(e),
        )
        raise

    # Build args dict from positional and named args
    args: dict[str, str] = dict(named_args)

    # Map positional args to input names
    for i, value in enumerate(positional_args):
        if i < len(workflow.inputs):
            input_arg = workflow.inputs[i]
            if input_arg.name not in args:
                args[input_arg.name] = value

    # Apply defaults for missing args
    for input_arg in workflow.inputs:
        if input_arg.name not in args and input_arg.default is not UNSET:
            if input_arg.default is None:
                args[input_arg.name] = "null"
            else:
                args[input_arg.name] = str(input_arg.default)

    # Process step inputs: load from @file or parse inline YAML/JSON
    # Step inputs allow users to skip steps by providing their outputs directly
    processed_args: dict[str, Any] = {}
    for input_arg in workflow.inputs:
        if input_arg.name not in args:
            continue
        value = args[input_arg.name]
        if input_arg.is_step_input:
            # Load and validate step input
            processed_args[input_arg.name] = load_step_input_value(
                value, input_arg.output_schema
            )
        else:
            processed_args[input_arg.name] = value
    args = processed_args

    # Create handlers based on silent mode
    # Suppress workflow output for single-step anonymous workflows
    # (e.g., "gai run hello" shouldn't show "[Step 1/1: main]")
    is_anonymous_single_step = workflow.is_anonymous() and len(workflow.steps) == 1

    hitl_handler: TUIHITLHandler | CLIHITLHandler
    if silent:
        hitl_handler = TUIHITLHandler(artifacts_dir)
        output_handler = None
    elif is_anonymous_single_step:
        hitl_handler = CLIHITLHandler()
        output_handler = None
    else:
        hitl_handler = CLIHITLHandler()
        output_handler = WorkflowOutputHandler()

    # Create and run executor
    executor = WorkflowExecutor(
        workflow=workflow,
        args=args,
        artifacts_dir=artifacts_dir,
        hitl_handler=hitl_handler,
        output_handler=output_handler,
        hitl_override=hitl_override,
    )

    success = executor.execute()

    if not success:
        raise WorkflowExecutionError(f"Workflow '{name}' was rejected or failed")

    # Extract output and response text
    output_str = ""
    response_text: str | None = None
    if executor.state.steps:
        last_step = executor.state.steps[-1]
        if last_step.output:
            output_str = json.dumps(last_step.output, indent=2)
            # Extract raw response text from _raw key if present
            if isinstance(last_step.output, dict) and "_raw" in last_step.output:
                response_text = last_step.output["_raw"]

    return WorkflowResult(
        output=output_str,
        response_text=response_text,
        artifacts_dir=artifacts_dir,
    )


def expand_workflow_for_embedding(
    workflow_name: str,
    positional_args: list[str],
    named_args: dict[str, str],
) -> tuple[str, list[WorkflowStep], list[WorkflowStep]]:
    """Expand a workflow for embedding into a containing prompt.

    When a workflow with a `prompt_part` step is embedded in a prompt,
    this function extracts:
    - The rendered prompt_part content (to append to the containing prompt)
    - Pre-steps (steps before prompt_part) to execute before the prompt
    - Post-steps (steps after prompt_part) to execute after the prompt

    If the workflow has no prompt_part, all steps are returned as post-steps.

    Args:
        workflow_name: The name of the workflow to expand.
        positional_args: Positional arguments for the workflow.
        named_args: Named arguments for the workflow.

    Returns:
        Tuple of (prompt_part_content, pre_steps, post_steps).

    Raises:
        WorkflowValidationError: If workflow not found.
    """
    from xprompt.workflow_executor_utils import render_template

    workflows = get_all_workflows()
    if workflow_name not in workflows:
        raise WorkflowValidationError(f"Workflow '{workflow_name}' not found")

    workflow = workflows[workflow_name]

    # Build args dict from positional and named args
    args: dict[str, str] = dict(named_args)

    # Map positional args to input names
    for i, value in enumerate(positional_args):
        if i < len(workflow.inputs):
            input_arg = workflow.inputs[i]
            if input_arg.name not in args:
                args[input_arg.name] = value

    # Apply defaults for missing args
    for input_arg in workflow.inputs:
        if input_arg.name not in args and input_arg.default is not UNSET:
            if input_arg.default is None:
                args[input_arg.name] = "null"
            else:
                args[input_arg.name] = str(input_arg.default)

    # Get pre and post steps
    pre_steps = workflow.get_pre_prompt_steps()
    post_steps = workflow.get_post_prompt_steps()

    # Render prompt_part content with args as initial context
    # Note: Pre-step outputs will be added to context during execution
    prompt_part_content = workflow.get_prompt_part_content()
    if prompt_part_content:
        # Render with just the input args for now
        # The full context (with pre-step outputs) will be used at execution time
        # when the prompt_part is actually expanded
        prompt_part_content = render_template(prompt_part_content, args)

    return prompt_part_content, pre_steps, post_steps


__all__ = [
    "WorkflowResult",
    "execute_workflow",
    "expand_workflow_for_embedding",
    "is_jinja2_template",
    "is_workflow_reference",
    "process_xprompt_references",
    "render_toplevel_jinja2",
]
