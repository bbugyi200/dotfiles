"""Argument parsing, text block processing, and shorthand syntax."""

import re


def escape_for_xprompt(text: str) -> str:
    """Escape text for use in an xprompt argument string.

    Escapes double quotes and backslashes.

    Args:
        text: The text to escape.

    Returns:
        The escaped text safe for use in xprompt argument.
    """
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _process_text_block(value: str) -> str:
    """Process a value that may be a text block [[...]].

    Strips leading whitespace from the first line and dedents continuation
    lines by their minimum common indentation, preserving relative indentation.
    Empty lines are preserved as-is.
    """
    if not (value.startswith("[[") and value.endswith("]]")):
        return value

    content = value[2:-2]  # Remove [[ and ]]
    lines = content.split("\n")

    if not lines:
        return ""

    # First line after [[ - strip leading whitespace
    first_line = lines[0].lstrip()
    continuation_lines = lines[1:]

    # Find minimum indentation among non-empty continuation lines
    min_indent = None
    for line in continuation_lines:
        if line.strip() == "":
            continue
        indent = len(line) - len(line.lstrip())
        if min_indent is None or indent < min_indent:
            min_indent = indent

    if min_indent is None:
        min_indent = 0

    processed_lines: list[str] = [first_line]
    for line in continuation_lines:
        if line.strip() == "":
            processed_lines.append("")
        else:
            processed_lines.append(line[min_indent:])

    return "\n".join(processed_lines).strip()


# Pattern to match shorthand syntax: #name: text (at beginning of line)
# Note: The space after colon distinguishes from existing #name:arg syntax
SHORTHAND_PATTERN = re.compile(
    r"(?:^|(?<=\n))"  # Must be at start of string or after newline
    r"#([a-zA-Z_][a-zA-Z0-9_]*(?:/[a-zA-Z_][a-zA-Z0-9_]*)*)"  # Group 1: name
    r": "  # Colon followed by space
)

# Pattern to match paren shorthand: #name( at beginning of line
_PAREN_SHORTHAND_PATTERN = re.compile(
    r"(?:^|(?<=\n))" r"#([a-zA-Z_][a-zA-Z0-9_]*(?:/[a-zA-Z_][a-zA-Z0-9_]*)*)" r"\("
)

# Pattern to match double-colon shorthand: #name:: text (at beginning of line)
DOUBLE_COLON_SHORTHAND_PATTERN = re.compile(
    r"(?:^|(?<=\n))"  # Must be at start of string or after newline
    r"#([a-zA-Z_][a-zA-Z0-9_]*(?:/[a-zA-Z_][a-zA-Z0-9_]*)*)"  # Group 1: name
    r":: "  # Double colon followed by space
)

# Pattern to find the start of the next xprompt directive at a line boundary.
# Used by double-colon shorthand to know where its text ends.
_NEXT_DIRECTIVE_PATTERN = re.compile(
    r"\n(?=#[a-zA-Z_][a-zA-Z0-9_]*(?:/[a-zA-Z_][a-zA-Z0-9_]*)*(?:\(|::? ))"
)


def _find_shorthand_text_end(prompt: str, start: int) -> int:
    """Find the end of shorthand text (at \\n\\n or end of string)."""
    blank_line_pos = prompt.find("\n\n", start)
    if blank_line_pos == -1:
        return len(prompt)
    return blank_line_pos


def _find_double_colon_text_end(prompt: str, start: int) -> int:
    """Find the end of double-colon text (at next directive or end of string).

    Unlike single-colon shorthand which terminates at blank lines, double-colon
    text includes blank lines and only terminates at the next xprompt directive
    at the start of a line, or at EOF.
    """
    match = _NEXT_DIRECTIVE_PATTERN.search(prompt, start)
    if match is None:
        return len(prompt)
    return match.start()


def _format_as_text_block(text: str) -> str:
    """Format text for use inside a [[...]] text block.

    Adds 2-space indent on continuation lines, preserves empty lines.
    """
    lines = text.split("\n")
    formatted_lines = [lines[0]]
    for line in lines[1:]:
        if line.strip() == "":
            formatted_lines.append("")
        else:
            formatted_lines.append("  " + line)
    return "\n".join(formatted_lines)


def _preprocess_paren_shorthand(prompt: str, xprompt_names: set[str]) -> str:
    """Convert #name(args): text shorthand to #name(args, [[text]]) format."""
    matches = list(re.finditer(_PAREN_SHORTHAND_PATTERN, prompt))

    for match in reversed(matches):
        name = match.group(1)
        if name not in xprompt_names:
            continue

        # Position of the opening '('
        paren_open = match.end() - 1
        paren_close = find_matching_paren_for_args(prompt, paren_open)
        if paren_close is None:
            continue

        # Check for "):: " (double-colon) or "): " (single-colon) after paren
        after_paren = prompt[paren_close + 1 :]
        if after_paren.startswith(":: "):
            text_start = paren_close + 4  # skip "):: "
            text_end = _find_double_colon_text_end(prompt, text_start)
        elif after_paren.startswith(": "):
            text_start = paren_close + 3  # skip "): "
            text_end = _find_shorthand_text_end(prompt, text_start)
        else:
            continue
        text = prompt[text_start:text_end].rstrip()

        text_block_content = _format_as_text_block(text)
        args_str = prompt[paren_open + 1 : paren_close].strip()

        if args_str:
            replacement = f"#{name}({args_str}, [[{text_block_content}]])"
        else:
            # Empty parens: #name(): text → #name([[text]])
            replacement = f"#{name}([[{text_block_content}]])"

        prompt = prompt[: match.start()] + replacement + prompt[text_end:]

    return prompt


def preprocess_shorthand_syntax(prompt: str, xprompt_names: set[str]) -> str:
    """Convert shorthand #name: text syntax to #name([[text]]) format."""
    # Pass 1: Handle paren shorthand (#name(args): text and #name(args):: text)
    prompt = _preprocess_paren_shorthand(prompt, xprompt_names)

    # Pass 2: Handle simple double-colon shorthand (#name:: text)
    matches = list(re.finditer(DOUBLE_COLON_SHORTHAND_PATTERN, prompt))

    for match in reversed(matches):
        name = match.group(1)
        if name not in xprompt_names:
            continue

        text_start = match.end()
        text_end = _find_double_colon_text_end(prompt, text_start)
        text = prompt[text_start:text_end].rstrip()

        text_block_content = _format_as_text_block(text)
        replacement = f"#{name}([[{text_block_content}]])"

        prompt = prompt[: match.start()] + replacement + prompt[text_end:]

    # Pass 3: Handle simple single-colon shorthand (#name: text)
    matches = list(re.finditer(SHORTHAND_PATTERN, prompt))

    for match in reversed(matches):  # Process last-to-first to preserve positions
        name = match.group(1)
        if name not in xprompt_names:
            continue

        text_start = match.end()
        text_end = _find_shorthand_text_end(prompt, text_start)
        text = prompt[text_start:text_end].rstrip()

        text_block_content = _format_as_text_block(text)
        replacement = f"#{name}([[{text_block_content}]])"

        prompt = prompt[: match.start()] + replacement + prompt[text_end:]

    return prompt


def find_matching_paren_for_args(text: str, start: int) -> int | None:
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


def strip_hitl_suffix(workflow_ref: str) -> tuple[str, bool | None]:
    """Extract !! or ?? HITL override suffix from a workflow reference.

    The suffix is expected on the name portion of the reference (before any
    ``(``, ``:``, or ``+`` delimiter).

    Args:
        workflow_ref: The workflow reference string (without leading ``#``).

    Returns:
        Tuple of (cleaned_ref, hitl_override) where hitl_override is True
        for ``!!``, False for ``??``, or None if no suffix was present.
    """
    # Find name boundary (first (, :, or +)
    name_end = len(workflow_ref)
    for i, ch in enumerate(workflow_ref):
        if ch in ("(", ":", "+"):
            name_end = i
            break
    name_part = workflow_ref[:name_end]
    rest = workflow_ref[name_end:]
    if name_part.endswith("!!"):
        return name_part[:-2] + rest, True
    if name_part.endswith("??"):
        return name_part[:-2] + rest, False
    return workflow_ref, None


def parse_workflow_reference(
    workflow_ref: str,
) -> tuple[str, list[str], dict[str, str]]:
    """Parse a workflow reference string into name and arguments.

    Handles:
    - Parenthesis syntax: workflow_name(arg1, key=value)
    - Simple colon syntax: workflow_name:value (no space after colon)
    - Multi-line colon syntax: workflow_name: text... (space after colon)
    - Plus syntax: workflow_name+ (equivalent to :true)
    - Plain name: workflow_name

    Args:
        workflow_ref: The workflow reference string (without leading #).

    Returns:
        Tuple of (workflow_name, positional_args, named_args).
    """
    # Plus syntax: workflow+ -> ["true"]
    if workflow_ref.endswith("+"):
        return workflow_ref[:-1], ["true"], {}

    # Parenthesis syntax: workflow(args)
    if "(" in workflow_ref:
        paren_idx = workflow_ref.index("(")
        workflow_name = workflow_ref[:paren_idx]
        if workflow_ref.endswith(")"):
            args_str = workflow_ref[paren_idx + 1 : -1]
            if args_str:
                positional_args, named_args = parse_args(args_str)
                return workflow_name, positional_args, named_args
        return workflow_name, [], {}

    # Colon syntax: workflow:value or workflow: text
    if ":" in workflow_ref:
        colon_idx = workflow_ref.index(":")
        workflow_name = workflow_ref[:colon_idx]
        rest = workflow_ref[colon_idx + 1 :]
        # The entire rest (with or without leading space) is a single positional arg
        # But we strip leading space for multi-line syntax aesthetics
        if rest.startswith(" "):
            return workflow_name, [rest[1:]], {}
        return workflow_name, [rest], {}

    # Plain name, no args
    return workflow_ref, [], {}


def parse_args(args_str: str) -> tuple[list[str], dict[str, str]]:
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
