"""Functions for prompt injection and output validation."""

import re

from .output_schema import OutputSchema, OutputType
from .validators import get_validator


def inject_format_instructions(prompt: str, output: OutputSchema | None) -> str:
    """Append format instructions to prompt if output schema defined.

    Args:
        prompt: The original prompt text.
        output: The output schema definition, or None.

    Returns:
        The prompt with format instructions appended if applicable.
    """
    if output is None:
        return prompt

    # Get format instructions - prefer custom, fall back to validator default
    instructions = output.format_instructions
    if instructions is None and output.validator:
        validator_cls = get_validator(output.validator)
        if validator_cls:
            validator = validator_cls()
            instructions = validator.get_format_instructions()

    if instructions is None:
        return prompt

    # Append instructions to prompt
    return f"{prompt}\n\n{instructions}"


def validate_output(
    content: str, output: OutputSchema | None
) -> tuple[bool, str | None]:
    """Validate content against output schema.

    Args:
        content: The content to validate.
        output: The output schema definition, or None.

    Returns:
        Tuple of (is_valid, error_message). Always returns (True, None) if no schema.
    """
    if output is None:
        return (True, None)

    if output.validator is None:
        # No validator specified, just check that content exists
        return (True, None) if content.strip() else (False, "Empty output")

    validator_cls = get_validator(output.validator)
    if validator_cls is None:
        # Unknown validator - treat as valid with warning
        return (True, None)

    validator = validator_cls()

    # Extract content for validation if needed
    extracted = extract_content_for_validation(content, output.type)
    return validator.validate(extracted)


def extract_content_for_validation(response: str, output_type: OutputType) -> str:
    """Extract YAML/JSON from markdown code fences if present.

    Args:
        response: The agent response text.
        output_type: The expected output type.

    Returns:
        The extracted content, or the original response if no fences found.
    """
    if output_type == OutputType.YAML_SCHEMA:
        # Try to extract from YAML code fences
        yaml_pattern = r"```(?:ya?ml)?\s*\n(.*?)```"
        match = re.search(yaml_pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()

    # If no code fence found, return the stripped response
    return response.strip()
