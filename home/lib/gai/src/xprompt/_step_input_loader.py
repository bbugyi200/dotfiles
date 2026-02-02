"""Step input loading and validation for workflow execution."""

import os
from typing import Any

import yaml  # type: ignore[import-untyped]

from xprompt.models import OutputSpec
from xprompt.output_validation import validate_against_schema
from xprompt.workflow_models import WorkflowValidationError


def load_step_input_value(
    value: str,
    output_spec: OutputSpec | None,
) -> Any:
    """Load step input from inline data or @file reference.

    Args:
        value: Either an inline YAML/JSON string or a @file reference.
        output_spec: Optional output specification to validate against.

    Returns:
        The parsed and validated data.

    Raises:
        WorkflowValidationError: If file doesn't exist or validation fails.
    """
    # Handle @file references
    if value.startswith("@"):
        file_path = os.path.expanduser(value[1:])
        if not os.path.exists(file_path):
            raise WorkflowValidationError(
                f"Step input file does not exist: {file_path}"
            )
        try:
            with open(file_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as e:
            raise WorkflowValidationError(
                f"Failed to load step input from {file_path}: {e}"
            ) from e
    else:
        # Try to parse as inline YAML/JSON
        try:
            data = yaml.safe_load(value)
        except yaml.YAMLError as e:
            raise WorkflowValidationError(
                f"Failed to parse step input as YAML/JSON: {e}"
            ) from e

    # Validate against output schema if provided
    if output_spec is not None:
        is_valid, error = validate_against_schema(data, output_spec.schema)
        if not is_valid:
            raise WorkflowValidationError(f"Step input validation failed: {error}")

    return data
