"""Jinja2 template handling and placeholder substitution."""

import re
import sys
from typing import Any

from jinja2 import BaseLoader, Environment, StrictUndefined, TemplateError
from rich_utils import print_status

from ._exceptions import XPromptArgumentError
from .models import UNSET, XPrompt, XPromptValidationError

# Lazy-initialized Jinja2 environment
_jinja_env: Environment | None = None


def is_jinja2_template(content: str) -> bool:
    """Detect if content uses Jinja2 syntax.

    Returns True if the content contains Jinja2 markers:
    - {{ ... }} for variable interpolation
    - {% ... %} for control structures
    - {# ... #} for comments
    """
    return bool(
        re.search(r"\{\{.*?\}\}", content, re.DOTALL)
        or re.search(r"\{%.*?%\}", content, re.DOTALL)
        or re.search(r"\{#.*?#\}", content, re.DOTALL)
    )


def _get_jinja_env() -> Environment:
    """Get or create the Jinja2 environment."""
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(
            loader=BaseLoader(),
            undefined=StrictUndefined,
            autoescape=False,
        )
    return _jinja_env


def validate_and_convert_args(
    xprompt: XPrompt,
    positional_args: list[str],
    named_args: dict[str, str],
) -> tuple[list[Any], dict[str, Any]]:
    """Validate and convert arguments using xprompt's input definitions.

    Args:
        xprompt: The XPrompt with input definitions.
        positional_args: Raw positional argument strings.
        named_args: Raw named argument strings.

    Returns:
        Tuple of (converted_positional, converted_named).

    Raises:
        XPromptArgumentError: If validation fails.
    """
    if not xprompt.inputs:
        # No typed inputs defined, pass through as-is
        return positional_args, named_args

    converted_positional: list[Any] = []
    converted_named: dict[str, Any] = {}
    used_input_names: set[str] = set()

    # Process positional args
    for i, value in enumerate(positional_args):
        input_def = xprompt.get_input_by_position(i)
        if input_def and value == "null":
            # Null pass-through: keep raw value in positional list but don't
            # add to converted_named so the callee's own default applies.
            converted_positional.append(value)
        elif input_def:
            try:
                converted_value = input_def.validate_and_convert(value)
                converted_positional.append(converted_value)
                # Map positional arg to named arg using input definition name
                converted_named[input_def.name] = converted_value
                used_input_names.add(input_def.name)
            except XPromptValidationError as e:
                raise XPromptArgumentError(
                    f"XPrompt '#{xprompt.name}' argument error: {e}"
                ) from e
        else:
            # More positional args than defined inputs, pass through
            converted_positional.append(value)

    # Process named args
    for name, value in named_args.items():
        if value == "null":
            # Null pass-through: skip so the callee's own default applies.
            continue
        input_def = xprompt.get_input_by_name(name)
        if input_def:
            try:
                converted_named[name] = input_def.validate_and_convert(value)
                used_input_names.add(name)
            except XPromptValidationError as e:
                raise XPromptArgumentError(
                    f"XPrompt '#{xprompt.name}' argument error: {e}"
                ) from e
        else:
            # Named arg not in input definitions, pass through
            converted_named[name] = value

    # Apply defaults for missing required inputs
    for input_def in xprompt.inputs:
        if input_def.name not in used_input_names:
            if input_def.default is not UNSET:
                converted_named[input_def.name] = input_def.default
            # Don't error on missing required - let Jinja2/legacy handle it

    return converted_positional, converted_named


def _render_jinja2_template(
    content: str,
    positional_args: list[Any],
    named_args: dict[str, Any],
    xprompt_name: str,
    scope: dict[str, Any] | None = None,
) -> str:
    """Render xprompt content as a Jinja2 template.

    Args:
        content: The Jinja2 template content
        positional_args: List of positional argument values
        named_args: Dictionary of named argument values
        xprompt_name: Name of the xprompt (for error messages)
        scope: Optional base context (e.g., workflow execution context).
            Xprompt-specific args take priority over scope values.

    Returns:
        Rendered template content

    Raises:
        XPromptArgumentError: On template errors or missing variables
    """
    env = _get_jinja_env()

    # Build context: scope first, then positional/named args override
    context: dict[str, Any] = {}
    if scope:
        context.update(scope)
    for i, arg in enumerate(positional_args, 1):
        context[f"_{i}"] = arg
    context["_args"] = positional_args

    # Add named args directly (overrides scope)
    context.update(named_args)

    try:
        template = env.from_string(content)
        return template.render(**context)
    except TemplateError as e:
        raise XPromptArgumentError(
            f"XPrompt '#{xprompt_name}' template error: {e}"
        ) from e


def render_toplevel_jinja2(content: str) -> str:
    """Render top-level prompt content as a Jinja2 template.

    Unlike xprompt rendering, this has no arguments - it just processes
    Jinja2 syntax in the prompt itself.

    Args:
        content: The prompt content that may contain Jinja2 syntax

    Returns:
        Rendered content

    Raises:
        SystemExit: On template errors
    """
    env = _get_jinja_env()
    try:
        template = env.from_string(content)
        return template.render()
    except TemplateError as e:
        print_status(f"Jinja2 template error in prompt: {e}", "error")
        sys.exit(1)


def _substitute_legacy_placeholders(
    content: str, args: list[Any], xprompt_name: str
) -> str:
    """Substitute {1}, {2}, etc. placeholders with arguments (legacy mode).

    Also handles optional placeholders with defaults: {1:default}

    Args:
        content: The xprompt content with placeholders
        args: List of argument values
        xprompt_name: Name of the xprompt (for error messages)

    Returns:
        Content with placeholders replaced

    Raises:
        XPromptArgumentError: If required placeholder is missing an argument
    """
    # Find all placeholders: {1}, {2}, {1:default}, etc.
    placeholder_pattern = r"\{(\d+)(?::([^}]*))?\}"

    def replace(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1  # Convert to 0-based
        default = match.group(2)

        if index < len(args):
            return str(args[index])
        elif default is not None:
            return default
        else:
            raise XPromptArgumentError(
                f"XPrompt '#{xprompt_name}' requires argument {{{index + 1}}} "
                f"but only {len(args)} argument(s) provided"
            )

    return re.sub(placeholder_pattern, replace, content)


def substitute_placeholders(
    content: str,
    positional_args: list[Any],
    named_args: dict[str, Any],
    xprompt_name: str,
    scope: dict[str, Any] | None = None,
) -> str:
    """Substitute placeholders using appropriate mode (Jinja2 or legacy).

    Automatically detects whether to use Jinja2 or legacy substitution
    based on the content.
    """
    if is_jinja2_template(content):
        return _render_jinja2_template(
            content, positional_args, named_args, xprompt_name, scope=scope
        )
    else:
        return _substitute_legacy_placeholders(content, positional_args, xprompt_name)
