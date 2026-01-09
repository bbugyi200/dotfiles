"""Snippet reference processing for prompts."""

import re
import sys

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

# Pattern to match snippet references: #name, #name(args), or #name:arg
# Must be at start of string, after whitespace, or after certain punctuation
# Note: No space allowed after # (to avoid matching markdown headings)
# Supports:
#   - #name - simple snippet (no args)
#   - #name(args) - parenthesis syntax for one or more args
#   - #name:arg - colon syntax for single arg (word-like chars only)
_SNIPPET_PATTERN = (
    r"(?:^|(?<=\s)|(?<=[(\[{]))"  # Must be at start, after whitespace, or after ([{
    r"#([a-zA-Z_][a-zA-Z0-9_]*)"  # Group 1: snippet name
    r"(?:\(([^)]*)\)|:([a-zA-Z0-9_.-]+))?"  # Group 2: paren args OR Group 3: colon arg
)


def _parse_args(args_str: str) -> list[str]:
    """Parse argument string into list of arguments.

    Handles quoted strings that may contain commas.

    Args:
        args_str: The argument string (e.g., "arg1, arg2" or 'hello, "world, here"')

    Returns:
        List of argument values with whitespace stripped.
    """
    if not args_str.strip():
        return []

    args: list[str] = []
    current_arg = ""
    in_quotes = False
    quote_char = ""

    for char in args_str:
        if char in ('"', "'") and not in_quotes:
            in_quotes = True
            quote_char = char
        elif char == quote_char and in_quotes:
            in_quotes = False
            quote_char = ""
        elif char == "," and not in_quotes:
            args.append(current_arg.strip())
            current_arg = ""
        else:
            current_arg += char

    # Don't forget the last argument
    if current_arg.strip():
        args.append(current_arg.strip())

    return args


def _substitute_placeholders(content: str, args: list[str], snippet_name: str) -> str:
    """Substitute {1}, {2}, etc. placeholders with arguments.

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


def _expand_single_snippet(
    name: str,
    args: list[str],
    snippets: dict[str, str],
) -> str:
    """Expand a single snippet with its arguments.

    Args:
        name: The snippet name
        args: List of argument values
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
    return _substitute_placeholders(content, args, name)


def process_snippet_references(prompt: str) -> str:
    """Process snippet references in the prompt.

    Expands all #snippet_name and #snippet_name(arg1, arg2) patterns
    with their corresponding content from the config file.

    Supports:
    - Simple snippets: #foo
    - Snippets with args: #bar(arg1, arg2)
    - Positional placeholders: {1}, {2}
    - Optional placeholders with defaults: {1:default}
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

                # Extract arguments from either parenthesis or colon syntax
                paren_args = match.group(2)
                colon_arg = match.group(3)
                if paren_args is not None:
                    args = _parse_args(paren_args)
                elif colon_arg is not None:
                    args = [colon_arg]
                else:
                    args = []

                expanded = _expand_single_snippet(name, args, snippets)

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

    return prompt
