"""Snippet reference processing for prompts."""

import re
import sys

from jinja2 import BaseLoader, Environment, StrictUndefined, TemplateError
from rich_utils import print_status
from snippet_config import get_all_snippets


class _SnippetError(Exception):
    """Base exception for snippet processing errors."""

    pass


class _SnippetNotFoundError(_SnippetError):
    """Raised when a referenced snippet doesn't exist."""

    pass


class _SnippetArgumentError(_SnippetError):
    """Raised when snippet arguments don't match placeholders."""

    pass


# Maximum number of expansion iterations to prevent infinite loops
_MAX_EXPANSION_ITERATIONS = 100

# Pattern to match snippet references: #name, #name(args), #name:arg, or #name+
# Must be at start of string, after whitespace, or after certain punctuation
# Note: No space allowed after # (to avoid matching markdown headings)
# Supports:
#   - #name - simple snippet (no args)
#   - #name(args) - parenthesis syntax for one or more args
#   - #name:arg - colon syntax for single arg (word-like chars only)
#   - #name+ - plus syntax, equivalent to #name:true
_SNIPPET_PATTERN = (
    r"(?:^|(?<=\s)|(?<=[(\[{]))"  # Must be at start, after whitespace, or after ([{
    r"#([a-zA-Z_][a-zA-Z0-9_]*)"  # Group 1: snippet name
    r"(?:\(([^)]*)\)|:([a-zA-Z0-9_.-]+)|(\+))?"  # Group 2: paren args OR Group 3: colon arg OR Group 4: plus
)

# Lazy-initialized Jinja2 environment
_jinja_env: Environment | None = None


def _is_jinja2_template(content: str) -> bool:
    """Detect if snippet content uses Jinja2 syntax.

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


def _parse_named_arg(token: str) -> tuple[str | None, str]:
    """Parse a single token to extract name=value if present.

    Returns (name, value) if named arg, or (None, token) if positional.
    """
    in_quotes = False
    quote_char = ""

    for i, char in enumerate(token):
        if char in ('"', "'") and not in_quotes:
            in_quotes = True
            quote_char = char
        elif char == quote_char and in_quotes:
            in_quotes = False
            quote_char = ""
        elif char == "=" and not in_quotes:
            name = token[:i].strip()
            value = token[i + 1 :].strip()
            # Strip quotes from value if present
            if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]
            return name, value

    return None, token


def _parse_args(args_str: str) -> tuple[list[str], dict[str, str]]:
    """Parse argument string into positional and named arguments.

    Handles quoted strings that may contain commas or equals signs.
    Named args use syntax: name=value or name="value with spaces"

    Args:
        args_str: The argument string (e.g., "arg1, name=value" or 'hello, "world"')

    Returns:
        Tuple of (positional_args, named_args).
    """
    if not args_str.strip():
        return [], {}

    # First tokenize by comma, respecting quotes
    tokens: list[str] = []
    current_token = ""
    in_quotes = False
    quote_char = ""

    for char in args_str:
        if char in ('"', "'") and not in_quotes:
            in_quotes = True
            quote_char = char
            current_token += char
        elif char == quote_char and in_quotes:
            in_quotes = False
            quote_char = ""
            current_token += char
        elif char == "," and not in_quotes:
            if current_token.strip():
                tokens.append(current_token.strip())
            current_token = ""
        else:
            current_token += char

    # Don't forget the last token
    if current_token.strip():
        tokens.append(current_token.strip())

    # Now parse each token as positional or named
    positional: list[str] = []
    named: dict[str, str] = {}

    for token in tokens:
        name, value = _parse_named_arg(token)
        if name is not None:
            named[name] = value
        else:
            # Strip quotes from positional args too
            if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]
            positional.append(value)

    return positional, named


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


def _render_jinja2_template(
    content: str,
    positional_args: list[str],
    named_args: dict[str, str],
    snippet_name: str,
) -> str:
    """Render snippet content as a Jinja2 template.

    Args:
        content: The Jinja2 template content
        positional_args: List of positional argument values
        named_args: Dictionary of named argument values
        snippet_name: Name of the snippet (for error messages)

    Returns:
        Rendered template content

    Raises:
        _SnippetArgumentError: On template errors or missing variables
    """
    env = _get_jinja_env()

    # Build context with positional args as _1, _2, etc.
    context: dict[str, str | list[str]] = {}
    for i, arg in enumerate(positional_args, 1):
        context[f"_{i}"] = arg
    context["_args"] = positional_args

    # Add named args directly
    context.update(named_args)

    try:
        template = env.from_string(content)
        return template.render(**context)
    except TemplateError as e:
        raise _SnippetArgumentError(
            f"Snippet '#{snippet_name}' template error: {e}"
        ) from e


def _render_toplevel_jinja2(content: str) -> str:
    """Render top-level prompt content as a Jinja2 template.

    Unlike snippet rendering, this has no arguments - it just processes
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
    content: str, args: list[str], snippet_name: str
) -> str:
    """Substitute {1}, {2}, etc. placeholders with arguments (legacy mode).

    Also handles optional placeholders with defaults: {1:default}

    Args:
        content: The snippet content with placeholders
        args: List of argument values
        snippet_name: Name of the snippet (for error messages)

    Returns:
        Content with placeholders replaced

    Raises:
        _SnippetArgumentError: If required placeholder is missing an argument
    """
    # Find all placeholders: {1}, {2}, {1:default}, etc.
    placeholder_pattern = r"\{(\d+)(?::([^}]*))?\}"

    def replace(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1  # Convert to 0-based
        default = match.group(2)

        if index < len(args):
            return args[index]
        elif default is not None:
            return default
        else:
            raise _SnippetArgumentError(
                f"Snippet '#{snippet_name}' requires argument {{{index + 1}}} "
                f"but only {len(args)} argument(s) provided"
            )

    return re.sub(placeholder_pattern, replace, content)


def _substitute_placeholders(
    content: str,
    positional_args: list[str],
    named_args: dict[str, str],
    snippet_name: str,
) -> str:
    """Substitute placeholders using appropriate mode (Jinja2 or legacy).

    Automatically detects whether to use Jinja2 or legacy substitution
    based on the content.
    """
    if _is_jinja2_template(content):
        return _render_jinja2_template(
            content, positional_args, named_args, snippet_name
        )
    else:
        return _substitute_legacy_placeholders(content, positional_args, snippet_name)


def _expand_single_snippet(
    name: str,
    positional_args: list[str],
    named_args: dict[str, str],
    snippets: dict[str, str],
) -> str:
    """Expand a single snippet with its arguments.

    Args:
        name: The snippet name
        positional_args: List of positional argument values
        named_args: Dictionary of named argument values
        snippets: All available snippets

    Returns:
        The expanded snippet content

    Raises:
        _SnippetNotFoundError: If snippet doesn't exist
        _SnippetArgumentError: If arguments don't match placeholders
    """
    if name not in snippets:
        raise _SnippetNotFoundError(f"Snippet '#{name}' not found in config")

    content = snippets[name]
    return _substitute_placeholders(content, positional_args, named_args, name)


def process_snippet_references(prompt: str) -> str:
    """Process snippet references in the prompt.

    Expands all #snippet_name and #snippet_name(arg1, arg2) patterns
    with their corresponding content from the config file.

    Supports:
    - Simple snippets: #foo
    - Snippets with positional args: #bar(arg1, arg2)
    - Snippets with named args: #bar(name=value, other="text")
    - Mixed args: #bar(pos1, name=value)
    - Colon syntax for single arg: #foo:arg
    - Plus syntax (equivalent to :true): #foo+
    - Legacy placeholders: {1}, {2}, {1:default}
    - Jinja2 templates: {{ name }}, {% if %}, etc.
    - Recursive expansion (snippets can reference other snippets)

    Args:
        prompt: The prompt text to process

    Returns:
        The transformed prompt with snippets expanded

    Raises:
        SystemExit: If any snippet processing error occurs
    """
    snippets = get_all_snippets()
    if not snippets:
        return prompt  # No snippets defined

    # Check if there are any potential snippet references
    if "#" not in prompt:
        return prompt

    iteration = 0
    while iteration < _MAX_EXPANSION_ITERATIONS:
        # Find all snippet references
        matches = list(re.finditer(_SNIPPET_PATTERN, prompt, re.MULTILINE))

        if not matches:
            break  # No more snippets to expand

        # Check if any matches are actual snippets we know about
        has_known_snippet = False
        for match in matches:
            name = match.group(1)
            if name in snippets:
                has_known_snippet = True
                break

        if not has_known_snippet:
            break  # No known snippets to expand

        # Expand from last to first to preserve positions
        try:
            for match in reversed(matches):
                name = match.group(1)

                # Skip if this isn't a known snippet
                if name not in snippets:
                    continue

                # Extract arguments from parenthesis, colon, or plus syntax
                paren_args = match.group(2)
                colon_arg = match.group(3)
                plus_suffix = match.group(4)
                if paren_args is not None:
                    positional_args, named_args = _parse_args(paren_args)
                elif colon_arg is not None:
                    positional_args, named_args = [colon_arg], {}
                elif plus_suffix is not None:
                    positional_args, named_args = ["true"], {}
                else:
                    positional_args, named_args = [], {}

                expanded = _expand_single_snippet(
                    name, positional_args, named_args, snippets
                )

                # Handle section snippets (content starting with ###)
                # Prepend \n\n when the snippet is not at the start of a line
                if expanded.startswith("###"):
                    is_at_line_start = (
                        match.start() == 0 or prompt[match.start() - 1] == "\n"
                    )
                    if not is_at_line_start:
                        expanded = "\n\n" + expanded

                prompt = prompt[: match.start()] + expanded + prompt[match.end() :]
        except _SnippetError as e:
            print_status(str(e), "error")
            sys.exit(1)

        iteration += 1

    if iteration >= _MAX_EXPANSION_ITERATIONS:
        print_status(
            f"Maximum snippet expansion depth ({_MAX_EXPANSION_ITERATIONS}) exceeded. "
            "Check for circular references.",
            "error",
        )
        sys.exit(1)

    # Process any Jinja2 templates in the final prompt
    if _is_jinja2_template(prompt):
        prompt = _render_toplevel_jinja2(prompt)

    return prompt
