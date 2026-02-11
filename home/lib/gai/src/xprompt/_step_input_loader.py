"""Step input loading and validation for workflow execution."""

import os
from typing import Any

import yaml  # type: ignore[import-untyped]

from xprompt.models import OutputSpec
from xprompt.output_validation import validate_against_schema
from xprompt.workflow_models import WorkflowValidationError

_FILE_EXTENSIONS = (".yml", ".yaml", ".json")


def _looks_like_file_path(value: str) -> bool:
    """Check if value looks like a file path based on its extension."""
    return value.endswith(_FILE_EXTENSIONS)


def _load_file(file_path: str) -> Any:
    """Load and parse a YAML/JSON file, expanding ~ in the path."""
    file_path = os.path.expanduser(file_path)
    if not os.path.exists(file_path):
        raise WorkflowValidationError(f"Step input file does not exist: {file_path}")
    try:
        with open(file_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        raise WorkflowValidationError(
            f"Failed to load step input from {file_path}: {e}"
        ) from e


def load_step_input_value(
    value: str,
    output_spec: OutputSpec | None,
) -> Any:
    """Load step input from inline data, @file reference, or auto-detected file path.

    Args:
        value: Either an inline YAML/JSON string, a @file reference, or a file
            path ending in .yml/.yaml/.json.
        output_spec: Optional output specification to validate against.

    Returns:
        The parsed and validated data.

    Raises:
        WorkflowValidationError: If file doesn't exist or validation fails.
    """
    if value.startswith("@"):
        data = _load_file(value[1:])
    elif _looks_like_file_path(value):
        data = _load_file(value)
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
