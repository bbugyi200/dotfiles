"""XPrompt data models for typed prompt templates."""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InputType(Enum):
    """Supported input argument types for XPrompt files."""

    WORD = "word"  # Single word, no whitespace
    LINE = "line"  # Single line, no newlines
    TEXT = "text"  # Multi-line text (any content)
    PATH = "path"  # File path (no whitespace + must exist)
    INT = "int"
    BOOL = "bool"
    FLOAT = "float"


class XPromptValidationError(Exception):
    """Raised when input validation fails."""

    pass


@dataclass
class InputArg:
    """Definition of an input argument for an XPrompt.

    Attributes:
        name: The argument name (used for named args like `name=value`).
        type: The expected type of the argument value.
        default: Default value if argument is not provided (None means required).
    """

    name: str
    type: InputType = InputType.LINE
    default: Any = None

    def validate_and_convert(self, value: str) -> Any:
        """Validate and convert a string value to the declared type.

        Args:
            value: The string value to convert.

        Returns:
            The converted value in the appropriate type.

        Raises:
            XPromptValidationError: If value cannot be converted to declared type.
        """
        if self.type == InputType.WORD:
            if any(c.isspace() for c in value):
                raise XPromptValidationError(
                    f"Argument '{self.name}' expects word (no spaces), got '{value}'"
                )
            return value
        elif self.type == InputType.LINE:
            if "\n" in value:
                raise XPromptValidationError(
                    f"Argument '{self.name}' expects line (no newlines), "
                    f"got value with newlines"
                )
            return value
        elif self.type == InputType.TEXT:
            return value  # No validation
        elif self.type == InputType.PATH:
            if any(c.isspace() for c in value):
                raise XPromptValidationError(
                    f"Argument '{self.name}' expects path (no spaces), got '{value}'"
                )
            expanded = os.path.expanduser(value)
            if not os.path.exists(expanded):
                raise XPromptValidationError(
                    f"Argument '{self.name}' path does not exist: '{value}'"
                )
            return value  # Return original value, not expanded
        elif self.type == InputType.INT:
            try:
                return int(value)
            except ValueError:
                raise XPromptValidationError(
                    f"Argument '{self.name}' expects int, got '{value}'"
                ) from None
        elif self.type == InputType.FLOAT:
            try:
                return float(value)
            except ValueError:
                raise XPromptValidationError(
                    f"Argument '{self.name}' expects float, got '{value}'"
                ) from None
        elif self.type == InputType.BOOL:
            lower_value = value.lower()
            if lower_value in ("true", "1", "yes", "on"):
                return True
            elif lower_value in ("false", "0", "no", "off"):
                return False
            else:
                raise XPromptValidationError(
                    f"Argument '{self.name}' expects bool, got '{value}'"
                )
        else:
            # Should never happen, but handle gracefully
            return value


@dataclass
class XPrompt:
    """An XPrompt template with optional typed input arguments.

    Attributes:
        name: The xprompt name (used in #name syntax).
        content: The template content (may contain Jinja2 or legacy placeholders).
        inputs: List of input argument definitions from YAML front matter.
        source_path: File path or "config" indicating where this xprompt was loaded from.
    """

    name: str
    content: str
    inputs: list[InputArg] = field(default_factory=list)
    source_path: str | None = None

    def get_input_by_name(self, name: str) -> InputArg | None:
        """Get an input argument definition by name.

        Args:
            name: The argument name to look up.

        Returns:
            The InputArg if found, None otherwise.
        """
        for input_arg in self.inputs:
            if input_arg.name == name:
                return input_arg
        return None

    def get_input_by_position(self, position: int) -> InputArg | None:
        """Get an input argument definition by position (0-indexed).

        Args:
            position: The 0-indexed position of the argument.

        Returns:
            The InputArg if position is valid, None otherwise.
        """
        if 0 <= position < len(self.inputs):
            return self.inputs[position]
        return None
