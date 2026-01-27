"""XPrompt reference processing for prompts."""

import re
import sys
from typing import Any

from jinja2 import BaseLoader, Environment, StrictUndefined, TemplateError
from rich_utils import print_status

from .loader import get_all_xprompts
from .models import XPrompt, XPromptValidationError


class _XPromptError(Exception):
    """Base exception for xprompt processing errors."""

    pass


class _XPromptArgumentError(_XPromptError):
    """Raised when xprompt arguments don't match placeholders."""

    pass


def _process_text_block(value: str) -> str:
    """Process a value that may be a text block [[...]].

    Strips mandatory 2-space indentation from each line.
    Raises error if indentation is missing.
    """
    if not (value.startswith("[[") and value.endswith("]]")):
        return value

    content = value[2:-2]  # Remove [[ and ]]
    lines = content.split("\n")

    processed_lines: list[str] = []
    for i, line in enumerate(lines):
        if i == 0:
            # First line after [[ - strip leading whitespace
            processed_lines.append(line.lstrip())
        elif line.strip() == "":
            # Empty line - preserve as empty
            processed_lines.append("")
        else:
            # Strip exactly 2 spaces from beginning
            if line.startswith("  "):
                processed_lines.append(line[2:])
            else:
                raise _XPromptArgumentError(
                    f"Text block line must start with 2 spaces: {line!r}"
                )

    return "\n".join(processed_lines).strip()


# Maximum number of expansion iterations to prevent infinite loops
_MAX_EXPANSION_ITERATIONS = 100

# Pattern to match xprompt references: #name, #name(, #name:arg, or #name+
# Must be at start of string, after whitespace, or after certain punctuation
# Note: No space allowed after # (to avoid matching markdown headings)
# Supports:
#   - #name - simple xprompt (no args)
#   - #name( - parenthesis syntax start (matching ) found programmatically)
#   - #name:arg - colon syntax for single arg (word-like chars only)
#   - #name+ - plus syntax, equivalent to #name:true
_XPROMPT_PATTERN = (
    r"(?:^|(?<=\s)|(?<=[(\[{\"']))"  # Must be at start, after whitespace, or after ([{"'
    r"#([a-zA-Z_][a-zA-Z0-9_]*(?:/[a-zA-Z_][a-zA-Z0-9_]*)*)"  # Group 1: xprompt name with optional namespace
    r"(?:(\()|:([a-zA-Z0-9_.-]+)|(\+))?"  # Group 2: open paren OR Group 3: colon arg OR Group 4: plus
)


def _find_matching_paren_for_args(text: str, start: int) -> int | None:
    """Find the matching ) for an opening ( at position start.

    Respects quoted strings ("..." and '...'), text blocks ([[...]]),
    and nested parentheses.

    Args:
        text: The full text to search.
        start: Position of the opening '(' character.

    Returns:
        Position of the matching ')' or None if not found.
    """
    if start >= len(text) or text[start] != "(":
        return None

    depth = 1
    in_quotes = False
    quote_char = ""
    in_text_block = False
    i = start + 1

    while i < len(text):
        # Check for text block start
        if not in_quotes and not in_text_block and text[i : i + 2] == "[[":
            in_text_block = True
            i += 2
            continue
        # Check for text block end
        if in_text_block and text[i : i + 2] == "]]":
            in_text_block = False
            i += 2
            continue

        char = text[i]

        if in_text_block:
            i += 1
            continue

        if char in ('"', "'") and not in_quotes:
            in_quotes = True
            quote_char = char
        elif char == quote_char and in_quotes:
            in_quotes = False
            quote_char = ""
        elif not in_quotes:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return i

        i += 1

    return None


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


def _parse_named_arg(token: str) -> tuple[str | None, str]:
    """Parse a single token to extract name=value if present.

    Returns (name, value) if named arg, or (None, token) if positional.
    Handles quoted strings and text blocks [[...]].
    """
    in_quotes = False
    quote_char = ""
    in_text_block = False
    i = 0

    while i < len(token):
        char = token[i]
        # Check for text block start
        if not in_quotes and not in_text_block and token[i : i + 2] == "[[":
            in_text_block = True
            i += 2
            continue
        # Check for text block end
        if in_text_block and token[i : i + 2] == "]]":
            in_text_block = False
            i += 2
            continue
        if char in ('"', "'") and not in_quotes and not in_text_block:
            in_quotes = True
            quote_char = char
        elif char == quote_char and in_quotes:
            in_quotes = False
            quote_char = ""
        elif char == "=" and not in_quotes and not in_text_block:
            name = token[:i].strip()
            value = token[i + 1 :].strip()
            # Strip quotes from value if present
            if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]
            # Process text blocks
            value = _process_text_block(value)
            return name, value
        i += 1

    return None, token


def _parse_args(args_str: str) -> tuple[list[str], dict[str, str]]:
    """Parse argument string into positional and named arguments.

    Handles quoted strings and text blocks [[...]] that may contain commas or equals.
    Named args use syntax: name=value or name="value with spaces" or name=[[text block]]

    Args:
        args_str: The argument string (e.g., "arg1, name=value" or 'hello, "world"')

    Returns:
        Tuple of (positional_args, named_args).
    """
    if not args_str.strip():
        return [], {}

    # First tokenize by comma, respecting quotes and text blocks
    tokens: list[str] = []
    current_token = ""
    in_quotes = False
    quote_char = ""
    in_text_block = False
    i = 0

    while i < len(args_str):
        char = args_str[i]
        # Check for text block start
        if not in_quotes and not in_text_block and args_str[i : i + 2] == "[[":
            in_text_block = True
            current_token += "[["
            i += 2
            continue
        # Check for text block end
        if in_text_block and args_str[i : i + 2] == "]]":
            in_text_block = False
            current_token += "]]"
            i += 2
            continue
        if char in ('"', "'") and not in_quotes and not in_text_block:
            in_quotes = True
            quote_char = char
            current_token += char
        elif char == quote_char and in_quotes:
            in_quotes = False
            quote_char = ""
            current_token += char
        elif char == "," and not in_quotes and not in_text_block:
            if current_token.strip():
                tokens.append(current_token.strip())
            current_token = ""
        else:
            current_token += char
        i += 1

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
            # Process text blocks for positional args
            value = _process_text_block(value)
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


def _validate_and_convert_args(
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
        _XPromptArgumentError: If validation fails.
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
        if input_def:
            try:
                converted_positional.append(input_def.validate_and_convert(value))
                used_input_names.add(input_def.name)
            except XPromptValidationError as e:
                raise _XPromptArgumentError(
                    f"XPrompt '#{xprompt.name}' argument error: {e}"
                ) from e
        else:
            # More positional args than defined inputs, pass through
            converted_positional.append(value)

    # Process named args
    for name, value in named_args.items():
        input_def = xprompt.get_input_by_name(name)
        if input_def:
            try:
                converted_named[name] = input_def.validate_and_convert(value)
                used_input_names.add(name)
            except XPromptValidationError as e:
                raise _XPromptArgumentError(
                    f"XPrompt '#{xprompt.name}' argument error: {e}"
                ) from e
        else:
            # Named arg not in input definitions, pass through
            converted_named[name] = value

    # Apply defaults for missing required inputs
    for input_def in xprompt.inputs:
        if input_def.name not in used_input_names:
            if input_def.default is not None:
                converted_named[input_def.name] = input_def.default
            # Don't error on missing required - let Jinja2/legacy handle it

    return converted_positional, converted_named


def _render_jinja2_template(
    content: str,
    positional_args: list[Any],
    named_args: dict[str, Any],
    xprompt_name: str,
) -> str:
    """Render xprompt content as a Jinja2 template.

    Args:
        content: The Jinja2 template content
        positional_args: List of positional argument values
        named_args: Dictionary of named argument values
        xprompt_name: Name of the xprompt (for error messages)

    Returns:
        Rendered template content

    Raises:
        _XPromptArgumentError: On template errors or missing variables
    """
    env = _get_jinja_env()

    # Build context with positional args as _1, _2, etc.
    context: dict[str, Any] = {}
    for i, arg in enumerate(positional_args, 1):
        context[f"_{i}"] = arg
    context["_args"] = positional_args

    # Add named args directly
    context.update(named_args)

    try:
        template = env.from_string(content)
        return template.render(**context)
    except TemplateError as e:
        raise _XPromptArgumentError(
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
        _XPromptArgumentError: If required placeholder is missing an argument
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
            raise _XPromptArgumentError(
                f"XPrompt '#{xprompt_name}' requires argument {{{index + 1}}} "
                f"but only {len(args)} argument(s) provided"
            )

    return re.sub(placeholder_pattern, replace, content)


def _substitute_placeholders(
    content: str,
    positional_args: list[Any],
    named_args: dict[str, Any],
    xprompt_name: str,
) -> str:
    """Substitute placeholders using appropriate mode (Jinja2 or legacy).

    Automatically detects whether to use Jinja2 or legacy substitution
    based on the content.
    """
    if is_jinja2_template(content):
        return _render_jinja2_template(
            content, positional_args, named_args, xprompt_name
        )
    else:
        return _substitute_legacy_placeholders(content, positional_args, xprompt_name)


def _expand_single_xprompt(
    xprompt: XPrompt,
    positional_args: list[str],
    named_args: dict[str, str],
) -> str:
    """Expand a single xprompt with its arguments.

    Args:
        xprompt: The XPrompt to expand.
        positional_args: List of positional argument values.
        named_args: Dictionary of named argument values.

    Returns:
        The expanded xprompt content.

    Raises:
        _XPromptArgumentError: If arguments don't match placeholders.
    """
    # Validate and convert args if xprompt has typed inputs
    conv_positional, conv_named = _validate_and_convert_args(
        xprompt, positional_args, named_args
    )

    return _substitute_placeholders(
        xprompt.content, conv_positional, conv_named, xprompt.name
    )


def process_xprompt_references(prompt: str) -> str:
    """Process xprompt references in the prompt.

    Expands all #xprompt_name and #xprompt_name(arg1, arg2) patterns
    with their corresponding content from files or config.

    Supports:
    - Simple xprompts: #foo
    - XPrompts with positional args: #bar(arg1, arg2)
    - XPrompts with named args: #bar(name=value, other="text")
    - Mixed args: #bar(pos1, name=value)
    - Text block args: #bar([[multi-line content]])
    - Colon syntax for single arg: #foo:arg
    - Plus syntax (equivalent to :true): #foo+
    - Legacy placeholders: {1}, {2}, {1:default}
    - Jinja2 templates: {{ name }}, {% if %}, etc.
    - Recursive expansion (xprompts can reference other xprompts)

    Args:
        prompt: The prompt text to process

    Returns:
        The transformed prompt with xprompts expanded

    Raises:
        SystemExit: If any xprompt processing error occurs
    """
    xprompts = get_all_xprompts()
    if not xprompts:
        return prompt  # No xprompts defined

    # Check if there are any potential xprompt references
    if "#" not in prompt:
        return prompt

    iteration = 0
    while iteration < _MAX_EXPANSION_ITERATIONS:
        # Find all xprompt references
        matches = list(re.finditer(_XPROMPT_PATTERN, prompt, re.MULTILINE))

        if not matches:
            break  # No more xprompts to expand

        # Check if any matches are actual xprompts we know about
        has_known_xprompt = False
        for match in matches:
            name = match.group(1)
            if name in xprompts:
                has_known_xprompt = True
                break

        if not has_known_xprompt:
            break  # No known xprompts to expand

        # Expand from last to first to preserve positions
        try:
            for match in reversed(matches):
                name = match.group(1)

                # Skip if this isn't a known xprompt
                if name not in xprompts:
                    continue

                xprompt = xprompts[name]

                # Extract arguments from parenthesis, colon, or plus syntax
                # Group 2: open paren marker, Group 3: colon arg, Group 4: plus
                has_open_paren = match.group(2) is not None
                colon_arg = match.group(3)
                plus_suffix = match.group(4)

                # Track the actual end position (may extend beyond match.end())
                match_end = match.end()

                positional_args: list[str]
                named_args: dict[str, str]
                if has_open_paren:
                    # Two-phase parsing: regex matched #name(, now find matching )
                    paren_start = match.end() - 1  # Position of the '('
                    paren_end = _find_matching_paren_for_args(prompt, paren_start)
                    if paren_end is None:
                        # Unclosed paren - treat as no args
                        positional_args, named_args = [], {}
                    else:
                        # Extract content between ( and )
                        paren_content = prompt[paren_start + 1 : paren_end]
                        positional_args, named_args = _parse_args(paren_content)
                        match_end = paren_end + 1  # Include the closing )
                elif colon_arg is not None:
                    positional_args, named_args = [colon_arg], {}
                elif plus_suffix is not None:
                    positional_args, named_args = ["true"], {}
                else:
                    positional_args, named_args = [], {}

                expanded = _expand_single_xprompt(xprompt, positional_args, named_args)

                # Handle section xprompts (content starting with ###)
                # Prepend \n\n when the xprompt is not at the start of a line
                if expanded.startswith("###"):
                    is_at_line_start = (
                        match.start() == 0 or prompt[match.start() - 1] == "\n"
                    )
                    if not is_at_line_start:
                        expanded = "\n\n" + expanded

                prompt = prompt[: match.start()] + expanded + prompt[match_end:]
        except _XPromptError as e:
            print_status(str(e), "error")
            sys.exit(1)

        iteration += 1

    if iteration >= _MAX_EXPANSION_ITERATIONS:
        print_status(
            f"Maximum xprompt expansion depth ({_MAX_EXPANSION_ITERATIONS}) exceeded. "
            "Check for circular references.",
            "error",
        )
        sys.exit(1)

    return prompt


# Backward compatibility alias
def process_snippet_references(prompt: str) -> str:
    """Legacy alias for process_xprompt_references.

    Deprecated: Use process_xprompt_references instead.
    """
    return process_xprompt_references(prompt)
