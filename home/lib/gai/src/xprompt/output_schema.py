"""Output schema types for XPrompt validation."""

from dataclasses import dataclass
from enum import Enum


class OutputType(Enum):
    """Supported output types for XPrompt files."""

    YAML_SCHEMA = "yaml_schema"
    # Future extensions:
    # JSON_SCHEMA = "json_schema"
    # REGEX = "regex"
    # CUSTOM = "custom"


@dataclass
class OutputSchema:
    """Definition of an output schema for an XPrompt.

    Attributes:
        type: The expected output format type.
        validator: Name of a registered validator to use (optional).
        format_instructions: Custom format instructions to inject into prompt (optional).
            If not provided, the validator's default instructions are used.
    """

    type: OutputType
    validator: str | None = None
    format_instructions: str | None = None
