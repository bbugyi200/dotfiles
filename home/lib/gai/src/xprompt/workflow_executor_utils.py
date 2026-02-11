"""Utility functions for workflow execution."""

import json
import re
from typing import Any

from jinja2 import Environment, StrictUndefined


def _finalize_value(value: Any) -> Any:
    """Convert Python booleans to lowercase strings for bash compatibility.

    Jinja2 renders Python True/False as "True"/"False", but bash expects
    "true"/"false" for comparisons like [ "$var" = "true" ].
    """
    if isinstance(value, bool):
        return str(value).lower()
    return value


def create_jinja_env() -> Environment:
    """Create a Jinja2 environment for template rendering."""
    env = Environment(undefined=StrictUndefined, finalize=_finalize_value)
    # Add tojson filter
    env.filters["tojson"] = json.dumps
    return env


def render_template(template: str, context: dict[str, Any]) -> str:
    """Render a Jinja2 template with the given context.

    Args:
        template: The template string with {{ var }} placeholders.
        context: Dictionary of variable values.

    Returns:
        The rendered template string.
    """
    env = create_jinja_env()
    jinja_template = env.from_string(template)
    return jinja_template.render(context)


def parse_bash_output(output: str) -> dict[str, Any]:
    """Parse bash command output into a dictionary.

    Supports three formats:
    1. JSON: {"key": "value", ...}
    2. Key=Value: Each line is key=value
    3. Positional: Each line is a value (keys must be inferred from schema)

    Args:
        output: The command output string.

    Returns:
        Dictionary of parsed values.
    """
    output = output.strip()

    # Try JSON first
    if output.startswith("{") or output.startswith("["):
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass

    # Try key=value format
    result: dict[str, Any] = {}
    lines = output.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for key=value pattern
        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)=(.*)$", line)
        if match:
            key, value = match.groups()
            result[key] = value
        else:
            # If we find a line without =, treat whole output as text
            # This handles multi-line values
            if not result:
                return {"_output": output}

    return result
