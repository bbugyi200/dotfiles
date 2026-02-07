"""Compile-time validation for workflows.

Validates workflows before execution to catch errors early with clear messages.
"""

import re
from dataclasses import dataclass

from xprompt._parsing import (
    find_matching_paren_for_args,
    parse_args,
    preprocess_shorthand_syntax,
)
from xprompt.loader import get_all_xprompts
from xprompt.models import XPrompt
from xprompt.workflow_models import Workflow, WorkflowStep, WorkflowValidationError

# Pattern to match xprompt references (same as processor.py)
_XPROMPT_PATTERN = (
    r"(?:^|(?<=\s)|(?<=[(\[{\"']))"
    r"#([a-zA-Z_][a-zA-Z0-9_]*(?:/[a-zA-Z_][a-zA-Z0-9_]*)*)"
    r"(?:(\()|:([a-zA-Z0-9_.-]+)|(\+))?"
)

# Pattern to match {{ variable }} or {{ variable.field }} template references
_TEMPLATE_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)")

# Pattern to capture full dotted paths like {{ research.prior_art.file_path }}
_TEMPLATE_REF_PATTERN = re.compile(
    r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)"
)


@dataclass
class _XPromptCall:
    """Parsed xprompt call from a template."""

    name: str
    positional_args: list[str]
    named_args: dict[str, str]
    raw_match: str


def _extract_xprompt_calls(content: str) -> list[_XPromptCall]:
    """Extract all xprompt references from template string.

    Args:
        content: The template content to scan.

    Returns:
        List of parsed xprompt calls.
    """
    calls: list[_XPromptCall] = []
    matches = list(re.finditer(_XPROMPT_PATTERN, content, re.MULTILINE))

    for match in matches:
        name = match.group(1)
        has_open_paren = match.group(2) is not None
        colon_arg = match.group(3)
        plus_suffix = match.group(4)

        positional_args: list[str] = []
        named_args: dict[str, str] = {}
        raw_match = match.group(0)

        if has_open_paren:
            paren_start = match.end() - 1
            paren_end = find_matching_paren_for_args(content, paren_start)
            if paren_end is not None:
                paren_content = content[paren_start + 1 : paren_end]
                positional_args, named_args = parse_args(paren_content)
                raw_match = content[match.start() : paren_end + 1]
        elif colon_arg is not None:
            positional_args = [colon_arg]
        elif plus_suffix is not None:
            positional_args = ["true"]

        calls.append(
            _XPromptCall(
                name=name,
                positional_args=positional_args,
                named_args=named_args,
                raw_match=raw_match,
            )
        )

    return calls


def _validate_xprompt_call(
    call: _XPromptCall,
    xprompt: XPrompt,
    step_name: str,
) -> list[str]:
    """Validate call arguments against xprompt definition.

    Args:
        call: The parsed xprompt call.
        xprompt: The xprompt definition to validate against.
        step_name: Name of the step containing the call (for error messages).

    Returns:
        List of error messages (empty if valid).
    """
    errors: list[str] = []

    # Check positional arg count
    if len(call.positional_args) > len(xprompt.inputs):
        errors.append(
            f"Step '{step_name}': #{call.name} has {len(call.positional_args)} "
            f"positional args but only {len(xprompt.inputs)} inputs defined"
        )

    # Check named args match defined input names
    defined_names = {inp.name for inp in xprompt.inputs}
    for arg_name in call.named_args:
        if arg_name not in defined_names:
            available = sorted(defined_names)
            errors.append(
                f"Step '{step_name}': #{call.name} has no input named '{arg_name}'. "
                f"Available: {available}"
            )

    # Check required args are provided
    # Build set of provided arg names
    provided_names: set[str] = set(call.named_args.keys())

    # Positional args map to inputs by position
    for i, _ in enumerate(call.positional_args):
        if i < len(xprompt.inputs):
            provided_names.add(xprompt.inputs[i].name)

    # Find missing required args (those without defaults)
    missing_required: list[str] = []
    for inp in xprompt.inputs:
        if inp.default is None and inp.name not in provided_names:
            # Skip check if a template variable could provide it at runtime
            # (but we still report it since we can't be sure)
            missing_required.append(inp.name)

    if missing_required:
        errors.append(
            f"Step '{step_name}': #{call.name} missing required args: {missing_required}"
        )

    return errors


def _collect_step_content(step: WorkflowStep) -> list[str]:
    """Collect all template content from a step.

    Args:
        step: The workflow step to scan.

    Returns:
        List of content strings that may contain template references.
    """
    contents: list[str] = []

    if step.prompt:
        contents.append(step.prompt)
    if step.bash:
        contents.append(step.bash)
    if step.python:
        contents.append(step.python)
    if step.prompt_part:
        contents.append(step.prompt_part)
    if step.condition:
        contents.append(step.condition)
    if step.for_loop:
        for value in step.for_loop.values():
            contents.append(value)
    if step.repeat_config:
        contents.append(step.repeat_config.condition)
    if step.while_config:
        contents.append(step.while_config.condition)
    if step.parallel_config:
        for nested_step in step.parallel_config.steps:
            contents.extend(_collect_step_content(nested_step))

    return contents


def _collect_used_variables(workflow: Workflow) -> set[str]:
    """Collect all variable names referenced in workflow templates.

    Args:
        workflow: The workflow to scan.

    Returns:
        Set of variable names referenced in templates.
    """
    used_vars: set[str] = set()

    for step in workflow.steps:
        for content in _collect_step_content(step):
            # Find all {{ variable }} or {{ variable.field }} references
            for match in _TEMPLATE_VAR_PATTERN.finditer(content):
                var_name = match.group(1)
                # Skip special variables like 'item' from for-loops
                if var_name not in ("item", "loop"):
                    used_vars.add(var_name)

    return used_vars


def _detect_unused_inputs(workflow: Workflow, used_vars: set[str]) -> list[str]:
    """Find inputs that are defined but never used.

    Args:
        workflow: The workflow to check.
        used_vars: Set of variable names referenced in templates.

    Returns:
        List of unused input names.
    """
    unused: list[str] = []

    for inp in workflow.inputs:
        # Skip auto-generated step inputs
        if inp.is_step_input:
            continue
        if inp.name not in used_vars:
            unused.append(inp.name)

    return unused


def _validate_prompt_part_steps(workflow: Workflow) -> list[str]:
    """Validate prompt_part steps in a workflow.

    Validates:
    - At most one prompt_part step per workflow
    - prompt_part steps cannot have control flow (if, for, repeat, while)
    - prompt_part steps cannot have output specification
    - prompt_part steps cannot have hitl: true

    Args:
        workflow: The workflow to validate.

    Returns:
        List of error messages (empty if valid).
    """
    errors: list[str] = []
    prompt_part_count = 0

    for step in workflow.steps:
        if not step.is_prompt_part_step():
            continue

        prompt_part_count += 1

        # Validate no control flow
        if step.condition:
            errors.append(
                f"Step '{step.name}' with 'prompt_part' cannot have 'if' condition"
            )
        if step.for_loop:
            errors.append(
                f"Step '{step.name}' with 'prompt_part' cannot have 'for' loop"
            )
        if step.repeat_config:
            errors.append(
                f"Step '{step.name}' with 'prompt_part' cannot have 'repeat' loop"
            )
        if step.while_config:
            errors.append(
                f"Step '{step.name}' with 'prompt_part' cannot have 'while' loop"
            )

        # Validate no output specification
        if step.output:
            errors.append(
                f"Step '{step.name}' with 'prompt_part' cannot have 'output' specification"
            )

        # Validate no HITL
        if step.hitl:
            errors.append(
                f"Step '{step.name}' with 'prompt_part' cannot have 'hitl: true'"
            )

    # Validate at most one prompt_part
    if prompt_part_count > 1:
        errors.append(
            f"Workflow has {prompt_part_count} prompt_part steps, "
            "but at most one is allowed"
        )

    return errors


def _mark_output_refs(content: str, output_usage: dict[str, bool]) -> None:
    """Scan content for template refs and mark matching output keys as used.

    Args:
        content: Template content string to scan.
        output_usage: Dict of output keys to used status (mutated in place).
    """
    for match in _TEMPLATE_REF_PATTERN.finditer(content):
        ref = match.group(1)
        parts = ref.split(".")

        if len(parts) == 1:
            # {{ step }} or {{ step | tojson }}
            if parts[0] in output_usage:
                output_usage[parts[0]] = True
        elif len(parts) == 2:
            # {{ step.field }} → marks "step"
            if parts[0] in output_usage:
                output_usage[parts[0]] = True
        else:
            # {{ parent.nested.field }} → marks "parent" and "parent.nested"
            if parts[0] in output_usage:
                output_usage[parts[0]] = True
            dotted = f"{parts[0]}.{parts[1]}"
            if dotted in output_usage:
                output_usage[dotted] = True


def _detect_unused_outputs(workflow: Workflow) -> list[str]:
    """Find steps with output that are never referenced by other steps.

    The last step is exempt since its output may be consumed when the workflow
    is embedded (via _propagate_last_embedded_output).

    Args:
        workflow: The workflow to check.

    Returns:
        List of error messages for unused outputs.
    """
    output_usage: dict[str, bool] = {}

    # Register all steps that have output
    for step in workflow.steps:
        if step.output:
            output_usage[step.name] = False
        if step.parallel_config:
            # Only track nested outputs when join is "object" or unset AND no for_loop
            join = step.join
            skip_nested = (
                join in ("array", "text", "lastOf") or step.for_loop is not None
            )
            if not skip_nested:
                for nested in step.parallel_config.steps:
                    if nested.output:
                        output_usage[f"{step.name}.{nested.name}"] = False

    # Scan all step content for references
    for step in workflow.steps:
        for content in _collect_step_content(step):
            _mark_output_refs(content, output_usage)

    # Scan workflow-local xprompt content
    for xprompt in workflow.xprompts.values():
        _mark_output_refs(xprompt.content, output_usage)

    # Determine exempt steps (last step)
    exempt_keys: set[str] = set()
    if workflow.has_prompt_part():
        post_steps = workflow.get_post_prompt_steps()
        if post_steps:
            last_step = post_steps[-1]
        else:
            last_step = None
    else:
        last_step = workflow.steps[-1] if workflow.steps else None

    if last_step:
        exempt_keys.add(last_step.name)
        # If last step is parallel, exempt all nested steps too
        if last_step.parallel_config:
            for nested in last_step.parallel_config.steps:
                exempt_keys.add(f"{last_step.name}.{nested.name}")

    # Return errors for unused outputs that aren't exempt
    errors: list[str] = []
    for key, used in output_usage.items():
        if not used and key not in exempt_keys:
            errors.append(f"Step '{key}' has output but is never referenced")

    return errors


def _detect_unused_xprompts(
    workflow: Workflow, xprompts: dict[str, XPrompt]
) -> list[str]:
    """Find workflow-local xprompts that are never referenced.

    Scans step content and other workflow-local xprompt content for #name
    references. Any workflow-local xprompt not referenced anywhere is reported.

    Args:
        workflow: The workflow to check.
        xprompts: Merged xprompt dict (global + workflow-local).

    Returns:
        List of error messages for unused workflow-local xprompts.
    """
    if not workflow.xprompts:
        return []

    xprompt_usage: dict[str, bool] = dict.fromkeys(workflow.xprompts, False)
    xprompt_names = set(xprompts.keys())

    # Scan step content
    for step in workflow.steps:
        for content in _collect_step_content(step):
            preprocessed = preprocess_shorthand_syntax(content, xprompt_names)
            for call in _extract_xprompt_calls(preprocessed):
                if call.name in xprompt_usage:
                    xprompt_usage[call.name] = True

    # Scan other workflow-local xprompt content (xprompts can reference each other)
    for xp in workflow.xprompts.values():
        preprocessed = preprocess_shorthand_syntax(xp.content, xprompt_names)
        for call in _extract_xprompt_calls(preprocessed):
            if call.name in xprompt_usage:
                xprompt_usage[call.name] = True

    errors: list[str] = []
    for name, used in xprompt_usage.items():
        if not used:
            errors.append(
                f"Workflow-local xprompt '{name}' is defined but never referenced"
            )
    return errors


def _detect_unused_xprompt_inputs(workflow: Workflow) -> list[str]:
    """Find inputs on workflow-local xprompts that are never used in content.

    For each workflow-local xprompt that has inputs, checks whether each input
    name appears as a {{ variable }} reference in the xprompt's content.

    Args:
        workflow: The workflow to check.

    Returns:
        List of error messages for unused xprompt inputs.
    """
    errors: list[str] = []

    for name, xp in workflow.xprompts.items():
        if not xp.inputs:
            continue

        # Collect variable names used in this xprompt's content
        used_vars: set[str] = set()
        for match in _TEMPLATE_VAR_PATTERN.finditer(xp.content):
            used_vars.add(match.group(1))

        for inp in xp.inputs:
            if inp.name not in used_vars:
                errors.append(
                    f"Xprompt '{name}' input '{inp.name}' "
                    f"is defined but never referenced in its content"
                )

    return errors


def _validate_xprompt_names(workflow: Workflow) -> list[str]:
    """Validate that all workflow-local xprompt names start with '_'.

    Args:
        workflow: The workflow to check.

    Returns:
        List of error messages for invalid xprompt names.
    """
    errors: list[str] = []
    for name in workflow.xprompts:
        if not name.startswith("_"):
            errors.append(
                f"Workflow-local xprompt '{name}' must start with '_' (e.g. '_{name}')"
            )
    return errors


def validate_workflow(workflow: Workflow) -> None:
    """Validate a workflow before execution.

    Performs compile-time checks:
    - Validates xprompt names start with '_'
    - Detects unused inputs (defined but never referenced)
    - Validates xprompt calls (required args, named arg names, positional counts)
    - Validates prompt_part steps (at most one, no control flow, no output, no hitl)

    Args:
        workflow: The workflow to validate.

    Raises:
        WorkflowValidationError: If validation fails.
    """
    errors: list[str] = []

    # Validate xprompt names early (before other xprompt checks)
    errors.extend(_validate_xprompt_names(workflow))

    xprompts = get_all_xprompts()
    xprompts.update(workflow.xprompts)  # workflow-local takes priority

    # Validate prompt_part steps
    prompt_part_errors = _validate_prompt_part_steps(workflow)
    errors.extend(prompt_part_errors)

    # Check for unused inputs
    used_vars = _collect_used_variables(workflow)
    unused_inputs = _detect_unused_inputs(workflow, used_vars)
    if unused_inputs:
        errors.append(f"Unused inputs: {unused_inputs}")

    # Check for unused outputs
    unused_output_errors = _detect_unused_outputs(workflow)
    errors.extend(unused_output_errors)

    # Check for unused workflow-local xprompts
    errors.extend(_detect_unused_xprompts(workflow, xprompts))

    # Check for unused workflow-local xprompt inputs
    errors.extend(_detect_unused_xprompt_inputs(workflow))

    # Validate xprompt calls in each step
    for step in workflow.steps:
        for content in _collect_step_content(step):
            # Preprocess shorthand syntax (#name: text -> #name([[text]]))
            preprocessed = preprocess_shorthand_syntax(content, set(xprompts.keys()))
            calls = _extract_xprompt_calls(preprocessed)
            for call in calls:
                if call.name in xprompts:
                    xprompt = xprompts[call.name]
                    call_errors = _validate_xprompt_call(call, xprompt, step.name)
                    errors.extend(call_errors)

    if errors:
        error_msg = f"Workflow '{workflow.name}' validation failed:\n"
        for error in errors:
            error_msg += f"  - {error}\n"
        raise WorkflowValidationError(error_msg.rstrip())
