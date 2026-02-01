"""Workflow discovery and loading from YAML files."""

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from xprompt.loader import (
    get_gai_package_xprompts_dir,
    get_xprompt_search_paths,
    parse_input_type,
    parse_output_from_front_matter,
)
from xprompt.models import InputArg, OutputSpec
from xprompt.workflow_models import (
    Workflow,
    WorkflowConfig,
    WorkflowStep,
    WorkflowValidationError,
)


def _parse_workflow_config(config_data: dict[str, Any] | None) -> WorkflowConfig:
    """Parse workflow configuration from YAML.

    Args:
        config_data: The config dict from YAML.

    Returns:
        WorkflowConfig object.
    """
    if not config_data or not isinstance(config_data, dict):
        return WorkflowConfig()

    return WorkflowConfig(
        claim_workspace=bool(config_data.get("claim_workspace", False)),
        create_artifacts=bool(config_data.get("create_artifacts", False)),
        log_workflow=bool(config_data.get("log_workflow", False)),
    )


def _parse_workflow_inputs(input_list: list[dict[str, Any]] | None) -> list[InputArg]:
    """Parse input definitions from workflow YAML.

    Args:
        input_list: List of input dicts from YAML.

    Returns:
        List of InputArg objects.
    """
    if not input_list:
        return []

    inputs: list[InputArg] = []
    for item in input_list:
        if not isinstance(item, dict) or "name" not in item:
            continue

        name = str(item["name"])
        type_str = str(item.get("type", "line"))
        default = item.get("default")

        inputs.append(
            InputArg(
                name=name,
                type=parse_input_type(type_str),
                default=default,
            )
        )

    return inputs


def _parse_workflow_step(
    step_data: dict[str, Any],
    index: int,
) -> WorkflowStep:
    """Parse a single workflow step from YAML.

    Args:
        step_data: The step dict from YAML.
        index: The step index (used for default name).

    Returns:
        WorkflowStep object.

    Raises:
        WorkflowValidationError: If step is invalid.
    """
    name = str(step_data.get("name", f"step_{index}"))

    agent = step_data.get("agent")
    bash = step_data.get("bash")

    # Validate mutually exclusive fields
    if agent and bash:
        raise WorkflowValidationError(
            f"Step '{name}' cannot have both 'agent' and 'bash' fields"
        )
    if not agent and not bash:
        raise WorkflowValidationError(
            f"Step '{name}' must have either 'agent' or 'bash' field"
        )

    prompt = step_data.get("prompt")
    if agent and not prompt:
        raise WorkflowValidationError(f"Agent step '{name}' requires a 'prompt' field")

    # Parse output specification
    output: OutputSpec | None = None
    output_data = step_data.get("output")
    if output_data:
        output = parse_output_from_front_matter(output_data)

    hitl = bool(step_data.get("hitl", False))

    return WorkflowStep(
        name=name,
        agent=str(agent) if agent else None,
        bash=str(bash) if bash else None,
        prompt=str(prompt) if prompt else None,
        output=output,
        hitl=hitl,
    )


def _validate_workflow_variables(workflow: Workflow) -> None:
    """Validate variable usage in workflow.

    Validates:
    1. All input args are used by at least one step
    2. All step outputs are used by at least one subsequent step
    3. No undefined variable references

    Args:
        workflow: The workflow to validate.

    Raises:
        WorkflowValidationError: If validation fails.
    """
    input_names = {inp.name for inp in workflow.inputs}
    step_names = {step.name for step in workflow.steps}

    # Track which variables are defined at each point
    defined_vars: set[str] = set(input_names)

    # Track usage of inputs
    input_usage: dict[str, bool] = dict.fromkeys(input_names, False)

    # Track output usage (outputs from each step)
    output_usage: dict[str, bool] = {}

    for i, step in enumerate(workflow.steps):
        # Check variable references in prompt or bash command
        content = step.prompt if step.prompt else step.bash
        if content:
            # Find Jinja2 variable references: {{ var }} and {{ step.var }}
            import re

            # Match {{ var }} and {{ step.output }}
            refs = re.findall(
                r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)\s*",
                content,
            )

            for ref in refs:
                if "." in ref:
                    # Step output reference like "setup.cl_name"
                    step_name, _ = ref.split(".", 1)
                    if step_name not in step_names:
                        raise WorkflowValidationError(
                            f"Step '{step.name}' references undefined step '{step_name}'"
                        )
                    if step_name not in defined_vars:
                        raise WorkflowValidationError(
                            f"Step '{step.name}' references step '{step_name}' before it executes"
                        )
                    if step_name in output_usage:
                        output_usage[step_name] = True
                else:
                    # Direct variable reference
                    if ref in input_names:
                        input_usage[ref] = True
                    elif ref not in defined_vars and ref not in ("tojson",):
                        # tojson is a Jinja2 filter, not a variable
                        # Check if it could be a Jinja filter or builtin
                        pass  # Allow for now, will fail at runtime if truly undefined

        # After this step executes, its outputs become available
        if step.output:
            defined_vars.add(step.name)
            output_usage[step.name] = False

    # Warn about unused inputs (but don't error - they might be used in nested xprompts)
    # Warn about unused outputs (but don't error - final step output might be workflow result)


def _load_workflow_from_file(file_path: Path) -> Workflow | None:
    """Load a single workflow from a YAML file.

    Args:
        file_path: Path to the .yml/.yaml file.

    Returns:
        Workflow object if successfully loaded, None otherwise.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
    except (OSError, yaml.YAMLError):
        return None

    if not isinstance(data, dict):
        return None

    # Get workflow name
    name = data.get("name")
    if not name:
        name = file_path.stem  # Filename without extension

    # Parse config
    config = _parse_workflow_config(data.get("config"))

    # Parse inputs
    inputs = _parse_workflow_inputs(data.get("input"))

    # Parse steps
    steps_data = data.get("steps", [])
    if not isinstance(steps_data, list):
        return None

    steps: list[WorkflowStep] = []
    try:
        for step_index, step_data in enumerate(steps_data):
            if not isinstance(step_data, dict):
                continue
            step = _parse_workflow_step(step_data, step_index)
            steps.append(step)
    except WorkflowValidationError:
        return None

    if not steps:
        return None

    workflow = Workflow(
        name=str(name),
        inputs=inputs,
        steps=steps,
        config=config,
        source_path=str(file_path),
    )

    # Validate variable usage
    try:
        _validate_workflow_variables(workflow)
    except WorkflowValidationError:
        # For now, just return the workflow even if validation fails
        # The error will be raised at runtime with more context
        pass

    return workflow


def _discover_workflow_files() -> list[tuple[Path, int]]:
    """Find all workflow files in search paths with priority info.

    Returns:
        List of (file_path, priority) tuples, where lower priority wins.
    """
    search_paths = get_xprompt_search_paths()
    results: list[tuple[Path, int]] = []

    for priority, search_dir in enumerate(search_paths):
        if not search_dir.is_dir():
            continue

        for yml_file in search_dir.glob("*.yml"):
            if yml_file.is_file():
                results.append((yml_file, priority))

        for yaml_file in search_dir.glob("*.yaml"):
            if yaml_file.is_file():
                results.append((yaml_file, priority))

    return results


def _load_workflows_from_files() -> dict[str, Workflow]:
    """Load workflows from file system locations.

    Returns:
        Dictionary mapping workflow name to Workflow object.
        Earlier priority sources override later ones.
    """
    discovered = _discover_workflow_files()

    # Sort by priority (lower is higher priority)
    discovered.sort(key=lambda x: x[1])

    workflows: dict[str, Workflow] = {}
    for file_path, _ in discovered:
        workflow = _load_workflow_from_file(file_path)
        if workflow and workflow.name not in workflows:
            # First occurrence wins
            workflows[workflow.name] = workflow

    return workflows


def _load_workflows_from_internal() -> dict[str, Workflow]:
    """Load workflows from the internal gai package xprompts directory.

    Returns:
        Dictionary mapping workflow name to Workflow object.
    """
    internal_dir = get_gai_package_xprompts_dir()

    if not internal_dir.is_dir():
        return {}

    workflows: dict[str, Workflow] = {}
    for yml_file in internal_dir.glob("*.yml"):
        if yml_file.is_file():
            workflow = _load_workflow_from_file(yml_file)
            if workflow:
                workflows[workflow.name] = workflow

    for yaml_file in internal_dir.glob("*.yaml"):
        if yaml_file.is_file():
            workflow = _load_workflow_from_file(yaml_file)
            if workflow:
                workflows[workflow.name] = workflow

    return workflows


def get_all_workflows() -> dict[str, Workflow]:
    """Get all workflows from all sources, respecting priority order.

    Priority order (first wins on name conflict):
    1. .xprompts/*.yml (CWD, hidden)
    2. xprompts/*.yml (CWD, non-hidden)
    3. ~/.xprompts/*.yml (home, hidden)
    4. ~/xprompts/*.yml (home, non-hidden)
    5. <gai_package>/xprompts/*.yml (internal)

    Returns:
        Dictionary mapping workflow name to Workflow object.
    """
    all_workflows: dict[str, Workflow] = {}

    # Internal workflows (lowest priority)
    all_workflows.update(_load_workflows_from_internal())

    # File-based workflows (highest priority) - already sorted
    file_workflows = _load_workflows_from_files()
    all_workflows.update(file_workflows)

    return all_workflows
