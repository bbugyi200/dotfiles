"""Output validation utilities for XPrompt responses."""

import copy
import json
import re
from typing import Any

from jsonschema import ValidationError, validate  # type: ignore[import-untyped]

from .models import OutputSpec, OutputType


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


# Set of semantic output types that map to JSON Schema "string"
_SEMANTIC_OUTPUT_TYPES = {t.value for t in OutputType}


def _validate_semantic_type(
    value: Any, output_type: str, field_path: str
) -> str | None:
    """Validate a value against a semantic output type.

    Args:
        value: The value to validate.
        output_type: The semantic type (word, line, text, path).
        field_path: The JSON path to this field for error messages.

    Returns:
        Error message if invalid, None if valid.
    """
    if not isinstance(value, str):
        return None  # Only validate strings

    if output_type == OutputType.WORD.value:
        if any(c.isspace() for c in value):
            truncated = value[:50] + "..." if len(value) > 50 else value
            return f"At {field_path}: expected word (no spaces), got '{truncated}'"
    elif output_type == OutputType.LINE.value:
        if "\n" in value:
            return f"At {field_path}: expected line (no newlines)"
    elif output_type == OutputType.PATH.value:
        if any(c.isspace() for c in value):
            truncated = value[:50] + "..." if len(value) > 50 else value
            return f"At {field_path}: expected path (no spaces), got '{truncated}'"
    # text has no validation
    return None


_SEMANTIC_TO_JSON_SCHEMA_TYPE = {
    "word": "string",
    "line": "string",
    "text": "string",
    "path": "string",
    "bool": "boolean",
    "int": "integer",
    "float": "number",
}


def _convert_semantic_schema_to_json_schema(
    schema: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Convert semantic types in a schema to JSON Schema types.

    Args:
        schema: The schema potentially containing semantic types.

    Returns:
        Tuple of (converted_schema, type_map) where type_map maps JSON paths
        to their original semantic types.
    """
    converted = copy.deepcopy(schema)
    type_map: dict[str, str] = {}

    def _convert_recursive(node: Any, path: str) -> None:
        if not isinstance(node, dict):
            return

        # Check if this node has a semantic type
        if "type" in node:
            if isinstance(node["type"], list):
                converted_types = []
                for t in node["type"]:
                    if t in _SEMANTIC_OUTPUT_TYPES:
                        type_map[path] = t
                        converted_types.append(_SEMANTIC_TO_JSON_SCHEMA_TYPE.get(t, t))
                    else:
                        converted_types.append(t)
                node["type"] = converted_types
            elif node["type"] in _SEMANTIC_OUTPUT_TYPES:
                type_map[path] = node["type"]
                node["type"] = _SEMANTIC_TO_JSON_SCHEMA_TYPE.get(
                    node["type"], node["type"]
                )

        # Recurse into properties
        if "properties" in node and isinstance(node["properties"], dict):
            for prop_name, prop_schema in node["properties"].items():
                prop_path = f"{path}.{prop_name}" if path else prop_name
                _convert_recursive(prop_schema, prop_path)

        # Recurse into items (for arrays)
        if "items" in node:
            items = node["items"]
            if isinstance(items, dict):
                items_path = f"{path}[]" if path else "[]"
                _convert_recursive(items, items_path)
            elif isinstance(items, list):
                for i, item in enumerate(items):
                    items_path = f"{path}[{i}]" if path else f"[{i}]"
                    _convert_recursive(item, items_path)

        # Recurse into additionalProperties
        if "additionalProperties" in node and isinstance(
            node["additionalProperties"], dict
        ):
            ap_path = f"{path}.*" if path else "*"
            _convert_recursive(node["additionalProperties"], ap_path)

        # Recurse into anyOf, oneOf, allOf
        for key in ("anyOf", "oneOf", "allOf"):
            if key in node and isinstance(node[key], list):
                for i, sub_schema in enumerate(node[key]):
                    _convert_recursive(sub_schema, path)

    _convert_recursive(converted, "")
    return converted, type_map


def _validate_semantic_types_recursive(
    data: Any,
    schema: dict[str, Any],
    type_map: dict[str, str],
    path: str,
) -> list[str]:
    """Walk parsed data and schema together to validate semantic types.

    Args:
        data: The parsed data to validate.
        schema: The original schema (before conversion).
        type_map: Map of JSON paths to semantic types.
        path: Current path in the data structure.

    Returns:
        List of error messages for any semantic type violations.
    """
    errors: list[str] = []

    # Check if this path has a semantic type
    if path in type_map:
        error = _validate_semantic_type(data, type_map[path], path or "root")
        if error:
            errors.append(error)

    if isinstance(data, dict):
        properties = schema.get("properties", {})
        for key, value in data.items():
            child_path = f"{path}.{key}" if path else key
            if key in properties:
                errors.extend(
                    _validate_semantic_types_recursive(
                        value, properties[key], type_map, child_path
                    )
                )
            else:
                # Check additionalProperties
                ap = schema.get("additionalProperties")
                if isinstance(ap, dict):
                    ap_path = f"{path}.*" if path else "*"
                    if ap_path in type_map:
                        error = _validate_semantic_type(
                            value, type_map[ap_path], child_path
                        )
                        if error:
                            errors.append(error)

    elif isinstance(data, list):
        items_schema = schema.get("items", {})
        if isinstance(items_schema, dict):
            items_path = f"{path}[]" if path else "[]"
            for item in data:
                errors.extend(
                    _validate_semantic_types_recursive(
                        item, items_schema, type_map, items_path
                    )
                )

    return errors


def _convert_data_types(
    data: Any, schema: dict[str, Any], type_map: dict[str, str], path: str = ""
) -> Any:
    """Convert string data values to appropriate types based on semantic types.

    Args:
        data: The data to convert (may be modified in place for dicts/lists).
        schema: The schema with semantic types.
        type_map: Map of JSON paths to semantic types.
        path: Current path in the data structure.

    Returns:
        Converted data (may be the same object or a new one).
    """
    # Check if this path has a type that needs conversion
    if path in type_map and isinstance(data, str):
        semantic_type = type_map[path]
        if semantic_type == "bool":
            lower_val = data.lower()
            if lower_val in ("true", "1", "yes", "on"):
                return True
            elif lower_val in ("false", "0", "no", "off"):
                return False
        elif semantic_type == "int":
            try:
                return int(data)
            except ValueError:
                pass
        elif semantic_type == "float":
            try:
                return float(data)
            except ValueError:
                pass

    if isinstance(data, dict):
        properties = schema.get("properties", {})
        for key in list(data.keys()):
            child_path = f"{path}.{key}" if path else key
            if key in properties:
                data[key] = _convert_data_types(
                    data[key], properties[key], type_map, child_path
                )
            else:
                # Check additionalProperties
                ap = schema.get("additionalProperties")
                if isinstance(ap, dict):
                    ap_path = f"{path}.*" if path else "*"
                    data[key] = _convert_data_types(data[key], ap, type_map, ap_path)

    elif isinstance(data, list):
        items_schema = schema.get("items", {})
        if isinstance(items_schema, dict):
            items_path = f"{path}[]" if path else "[]"
            for i, item in enumerate(data):
                data[i] = _convert_data_types(item, items_schema, type_map, items_path)

    return data


def validate_against_schema(
    data: Any, schema: dict[str, Any]
) -> tuple[bool, str | None]:
    """Validate data against a JSON Schema with semantic type support.

    Supports semantic output types (word, line, text, path, bool, int, float) in
    addition to standard JSON Schema types. Semantic types are converted to JSON
    Schema types for validation, and string data values are converted to the
    appropriate types (bool, int, float) before validation.

    Args:
        data: The parsed data to validate.
        schema: The JSON Schema to validate against (may contain semantic types).

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    # Convert semantic types to JSON Schema types
    converted_schema, type_map = _convert_semantic_schema_to_json_schema(schema)

    # Convert string data to appropriate types based on semantic types
    if type_map:
        data = _convert_data_types(data, schema, type_map, "")

    # Validate with standard JSON Schema
    try:
        validate(instance=data, schema=converted_schema)
    except ValidationError as e:
        # Build a helpful error message
        path = " -> ".join(str(p) for p in e.absolute_path) if e.absolute_path else ""
        if path:
            error_msg = f"At {path}: {e.message}"
        else:
            error_msg = e.message
        return False, error_msg

    # Then, validate semantic types (for string constraints like word, line, path)
    if type_map:
        semantic_errors = _validate_semantic_types_recursive(data, schema, type_map, "")
        if semantic_errors:
            return False, semantic_errors[0]  # Return first error

    return True, None


def extract_semantic_type_hints(schema: Any, path: str = "") -> list[str]:
    """Extract semantic type hints from a schema for format instructions.

    Args:
        schema: The schema to extract hints from (may be non-dict in recursive calls).
        path: Current path in the schema.

    Returns:
        List of hint strings describing semantic type constraints.
    """
    hints: list[str] = []

    if not isinstance(schema, dict):
        return hints

    # Check if this node has a semantic type
    type_val = schema.get("type", "")
    is_nullable = False
    if isinstance(type_val, list):
        is_nullable = "null" in type_val
        type_val = next((t for t in type_val if t in _SEMANTIC_OUTPUT_TYPES), "")
    if type_val in _SEMANTIC_OUTPUT_TYPES:
        field_desc = path if path else "root"
        null_suffix = " (or null)" if is_nullable else ""
        if type_val == OutputType.WORD.value:
            hints.append(
                f"- `{field_desc}`: must be a single word (no spaces){null_suffix}"
            )
        elif type_val == OutputType.LINE.value:
            hints.append(
                f"- `{field_desc}`: must be a single line (no newlines){null_suffix}"
            )
        elif type_val == OutputType.PATH.value:
            hints.append(
                f"- `{field_desc}`: must be a valid path (no spaces){null_suffix}"
            )
        # text, bool, int, float have no special constraints to describe

    # Recurse into properties
    if "properties" in schema and isinstance(schema["properties"], dict):
        for prop_name, prop_schema in schema["properties"].items():
            prop_path = f"{path}.{prop_name}" if path else prop_name
            hints.extend(extract_semantic_type_hints(prop_schema, prop_path))

    # Recurse into items (for arrays)
    if "items" in schema and isinstance(schema["items"], dict):
        items_path = f"{path}[]" if path else "items"
        hints.extend(extract_semantic_type_hints(schema["items"], items_path))

    return hints


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

    # Extract semantic type hints
    semantic_hints = extract_semantic_type_hints(output_spec.schema)
    semantic_section = ""
    if semantic_hints:
        hints_text = "\n".join(semantic_hints)
        semantic_section = f"""

FIELD CONSTRAINTS:
{hints_text}
"""

    instructions = f"""

---
OUTPUT FORMAT REQUIREMENTS:

Your response MUST be valid JSON that conforms to the following JSON Schema:

```json
{schema_str}
```
{semantic_section}
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
