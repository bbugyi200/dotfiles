"""Output validation utilities for XPrompt responses."""

import json
import re
from typing import Any

from jsonschema import ValidationError, validate  # type: ignore[import-untyped]

from .models import OutputSpec


class OutputValidationError(Exception):
    """Raised when output validation fails."""

    def __init__(self, message: str, raw_response: str) -> None:
        """Initialize the error with message and raw response.

        Args:
            message: The error message describing why validation failed.
            raw_response: The original response that failed validation.
        """
        super().__init__(message)
        self.message = message
        self.raw_response = raw_response


def extract_structured_content(response: str) -> tuple[Any, str]:
    """Extract JSON or YAML content from a response, handling code fences.

    Attempts to extract structured data from:
    1. Code fence blocks (```json, ```yaml, ```)
    2. Raw JSON/YAML in the response

    Args:
        response: The raw response text from the agent.

    Returns:
        Tuple of (parsed_data, format_type) where format_type is "json" or "yaml".

    Raises:
        OutputValidationError: If no valid structured content can be extracted.
    """
    # Try to extract from code fences first
    fence_pattern = r"```(?:json|yaml|yml)?\s*\n?([\s\S]*?)```"
    matches = re.findall(fence_pattern, response)

    content_to_try: list[str] = []

    # Add fenced content first (higher priority)
    for match in matches:
        content_to_try.append(match.strip())

    # Also try the full response stripped
    content_to_try.append(response.strip())

    # Try parsing each candidate as JSON first, then YAML
    for content in content_to_try:
        # Try JSON first
        try:
            data = json.loads(content)
            return data, "json"
        except json.JSONDecodeError:
            pass

        # Try YAML (which is a superset of JSON)
        # Only accept structured YAML (dict or list), not plain strings
        try:
            import yaml  # type: ignore[import-untyped]

            data = yaml.safe_load(content)
            if data is not None and isinstance(data, (dict, list)):
                return data, "yaml"
        except Exception:
            pass

    raise OutputValidationError(
        "Could not extract valid JSON or YAML from response",
        raw_response=response,
    )


def validate_against_schema(
    data: Any, schema: dict[str, Any]
) -> tuple[bool, str | None]:
    """Validate data against a JSON Schema.

    Args:
        data: The parsed data to validate.
        schema: The JSON Schema to validate against.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    try:
        validate(instance=data, schema=schema)
        return True, None
    except ValidationError as e:
        # Build a helpful error message
        path = " -> ".join(str(p) for p in e.absolute_path) if e.absolute_path else ""
        if path:
            error_msg = f"At {path}: {e.message}"
        else:
            error_msg = e.message
        return False, error_msg


def generate_format_instructions(output_spec: OutputSpec) -> str:
    """Generate prompt instructions for the required output format.

    Args:
        output_spec: The output specification from the xprompt.

    Returns:
        A string with formatting instructions to append to the prompt.
    """
    if output_spec.type != "json_schema":
        return ""

    schema_str = json.dumps(output_spec.schema, indent=2)

    instructions = f"""

---
OUTPUT FORMAT REQUIREMENTS:

Your response MUST be valid JSON that conforms to the following JSON Schema:

```json
{schema_str}
```

IMPORTANT:
- Output ONLY the JSON data, wrapped in a code fence (```json ... ```)
- Do NOT include any explanation or commentary before or after the JSON
- The JSON must be valid and parseable
- The JSON must conform exactly to the schema above
"""
    return instructions


def validate_response(response: str, output_spec: OutputSpec) -> tuple[Any, str | None]:
    """Validate an agent response against an output specification.

    Args:
        response: The raw response text from the agent.
        output_spec: The output specification to validate against.

    Returns:
        Tuple of (parsed_data, error_message). error_message is None if valid.

    Raises:
        OutputValidationError: If the response cannot be parsed.
    """
    if output_spec.type != "json_schema":
        # Only json_schema type is supported for now
        return response, None

    # Extract structured content
    data, _ = extract_structured_content(response)

    # Validate against schema
    is_valid, error_msg = validate_against_schema(data, output_spec.schema)

    if is_valid:
        return data, None
    else:
        return data, error_msg
