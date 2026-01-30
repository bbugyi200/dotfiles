"""Validator registry and built-in validators for XPrompt output validation."""

from abc import ABC, abstractmethod
from collections.abc import Callable

from split_spec import parse_split_spec, validate_split_spec


class OutputValidator(ABC):
    """Base class for output validators."""

    @abstractmethod
    def validate(self, content: str) -> tuple[bool, str | None]:
        """Validate content against the schema.

        Args:
            content: The content to validate.

        Returns:
            Tuple of (is_valid, error_message). error_message is None if valid.
        """
        pass

    @abstractmethod
    def get_format_instructions(self) -> str:
        """Get format instructions to inject into prompt.

        Returns:
            Format instructions string.
        """
        pass


_VALIDATOR_REGISTRY: dict[str, type[OutputValidator]] = {}


def register_validator(
    name: str,
) -> Callable[[type[OutputValidator]], type[OutputValidator]]:
    """Decorator to register a named validator.

    Args:
        name: The name to register the validator under.

    Returns:
        Decorator function.
    """

    def decorator(cls: type[OutputValidator]) -> type[OutputValidator]:
        _VALIDATOR_REGISTRY[name] = cls
        return cls

    return decorator


def get_validator(name: str) -> type[OutputValidator] | None:
    """Get validator class by name.

    Args:
        name: The registered name of the validator.

    Returns:
        The validator class if found, None otherwise.
    """
    return _VALIDATOR_REGISTRY.get(name)


@register_validator("split_spec")
class SplitSpecValidator(OutputValidator):
    """Validator for SplitSpec YAML output."""

    def validate(self, content: str) -> tuple[bool, str | None]:
        """Validate content as a SplitSpec.

        Args:
            content: The YAML content to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        try:
            spec = parse_split_spec(content)
            is_valid, error = validate_split_spec(spec)
            if not is_valid:
                return (False, error)
            return (True, None)
        except ValueError as e:
            return (False, str(e))

    def get_format_instructions(self) -> str:
        """Get format instructions for SplitSpec output.

        Returns:
            Format instructions string.
        """
        return """## Output Format Requirements

1. Output ONLY valid YAML - no explanation, no markdown code fences, just raw YAML
2. Each entry must have:
   - `name`: The CL name (string, required)
   - `description`: A clear description (string, required)
   - `parent`: (optional) The name of the parent CL if this builds on another
3. Use TWO blank lines between each entry for readability
4. No duplicate names are allowed
5. Parent references must point to existing entries in the spec"""
