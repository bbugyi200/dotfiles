"""XPrompt reference processing for prompts."""

import re
import sys

from rich_utils import print_status

from ._exceptions import XPromptError
from ._jinja import (
    is_jinja2_template,
    render_toplevel_jinja2,
    substitute_placeholders,
    validate_and_convert_args,
)
from ._parsing import (
    find_matching_paren_for_args,
    parse_args,
    preprocess_shorthand_syntax,
)
from .loader import get_all_xprompts
from .models import OutputSpec, XPrompt

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


def get_primary_output_schema(prompt: str) -> OutputSpec | None:
    """Find the first xprompt with an output schema in the original prompt.

    This function scans the prompt text (before expansion) for xprompt references
    and returns the output specification from the first one that has an output
    field defined. This is used to determine the expected output format for the
    entire prompt.

    Args:
        prompt: The original prompt text (before xprompt expansion).

    Returns:
        The OutputSpec from the first xprompt with an output field, or None
        if no xprompts have output specifications.
    """
    xprompts = get_all_xprompts()
    if not xprompts or "#" not in prompt:
        return None

    # Find all xprompt references in order
    matches = list(re.finditer(_XPROMPT_PATTERN, prompt, re.MULTILINE))

    for match in matches:
        name = match.group(1)
        if name in xprompts:
            xprompt = xprompts[name]
            if xprompt.output is not None:
                return xprompt.output

    return None


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
    conv_positional, conv_named = validate_and_convert_args(
        xprompt, positional_args, named_args
    )

    return substitute_placeholders(
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

    # Pre-process shorthand syntax (#name: text -> #name([[text]]))
    prompt = preprocess_shorthand_syntax(prompt, set(xprompts.keys()))

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
                    paren_end = find_matching_paren_for_args(prompt, paren_start)
                    if paren_end is None:
                        # Unclosed paren - treat as no args
                        positional_args, named_args = [], {}
                    else:
                        # Extract content between ( and )
                        paren_content = prompt[paren_start + 1 : paren_end]
                        positional_args, named_args = parse_args(paren_content)
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
        except XPromptError as e:
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


# Re-export public functions from _jinja for backward compatibility
__all__ = [
    "get_primary_output_schema",
    "is_jinja2_template",
    "process_snippet_references",
    "process_xprompt_references",
    "render_toplevel_jinja2",
]
