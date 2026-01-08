"""Query syntax highlighting utilities.

This module provides shared tokenization and styling for query syntax highlighting,
used by the TUI widgets.
"""


def _is_bare_word_char(char: str) -> bool:
    """Check if a character can be part of a bare word."""
    return char.isalnum() or char in "_-"


def tokenize_query_for_display(query: str) -> list[tuple[str, str]]:
    """Tokenize a query string for syntax highlighting.

    Args:
        query: The query string to tokenize.

    Returns:
        List of (token, token_type) tuples where token_type is one of:
        - "keyword" for AND, OR
        - "negation" for !
        - "error_suffix" for !!! (error suffix shorthand)
        - "running_agent" for @@@ (running agent shorthand)
        - "paren" for ( and )
        - "quoted" for quoted strings (including the quotes)
        - "term" for unquoted search terms
        - "shorthand" for %d, %m, %s, %r, +project, ^ancestor
        - "property_key" for status:, project:, ancestor:
        - "property_value" for the value after a property key
        - "whitespace" for spaces
    """
    tokens: list[tuple[str, str]] = []
    i = 0

    while i < len(query):
        # Skip and collect whitespace
        if query[i].isspace():
            start = i
            while i < len(query) and query[i].isspace():
                i += 1
            tokens.append((query[start:i], "whitespace"))
            continue

        # Check for parentheses
        if query[i] in "()":
            tokens.append((query[i], "paren"))
            i += 1
            continue

        # Check for !!! (error suffix shorthand) - must come before single ! check
        if query[i : i + 3] == "!!!":
            tokens.append(("!!!", "error_suffix"))
            i += 3
            continue

        # Check for !! (not error suffix shorthand)
        if query[i : i + 2] == "!!" and (
            i + 2 >= len(query) or query[i + 2] in " \t\r\n"
        ):
            tokens.append(("!!", "error_suffix"))
            i += 2
            continue

        # Check for !@ (not running agent shorthand)
        if query[i : i + 2] == "!@" and (
            i + 2 >= len(query) or query[i + 2] in " \t\r\n"
        ):
            tokens.append(("!@", "running_agent"))
            i += 2
            continue

        # Check for !$ (not running process shorthand)
        if query[i : i + 2] == "!$" and (
            i + 2 >= len(query) or query[i + 2] in " \t\r\n"
        ):
            tokens.append(("!$", "running_process"))
            i += 2
            continue

        # Check for standalone ! (also error suffix)
        if query[i] == "!" and (i + 1 >= len(query) or query[i + 1] in " \t\r\n"):
            tokens.append(("!", "error_suffix"))
            i += 1
            continue

        # Check for negation (! followed by something)
        if query[i] == "!":
            tokens.append(("!", "negation"))
            i += 1
            continue

        # Check for @@@ (running agent shorthand)
        if query[i : i + 3] == "@@@":
            tokens.append(("@@@", "running_agent"))
            i += 3
            continue

        # Check for standalone @ (also running agent)
        if query[i] == "@" and (i + 1 >= len(query) or query[i + 1] in " \t\r\n"):
            tokens.append(("@", "running_agent"))
            i += 1
            continue

        # Check for $$$ (running process shorthand)
        if query[i : i + 3] == "$$$":
            tokens.append(("$$$", "running_process"))
            i += 3
            continue

        # Check for standalone $ (also running process)
        if query[i] == "$" and (i + 1 >= len(query) or query[i + 1] in " \t\r\n"):
            tokens.append(("$", "running_process"))
            i += 1
            continue

        # Check for status shorthand: %d, %m, %s, %r
        if query[i] == "%" and i + 1 < len(query) and query[i + 1].lower() in "dmsr":
            tokens.append((query[i : i + 2], "shorthand"))
            i += 2
            continue

        # Check for project shorthand: +identifier
        if (
            query[i] == "+"
            and i + 1 < len(query)
            and (query[i + 1].isalpha() or query[i + 1] == "_")
        ):
            start = i
            i += 1  # Skip +
            while i < len(query) and _is_bare_word_char(query[i]):
                i += 1
            tokens.append((query[start:i], "shorthand"))
            continue

        # Check for ancestor shorthand: ^identifier
        if (
            query[i] == "^"
            and i + 1 < len(query)
            and (query[i + 1].isalpha() or query[i + 1] == "_")
        ):
            start = i
            i += 1  # Skip ^
            while i < len(query) and _is_bare_word_char(query[i]):
                i += 1
            tokens.append((query[start:i], "shorthand"))
            continue

        # Check for quoted strings (with optional case-sensitivity prefix)
        if query[i] == '"' or (
            query[i] == "c" and i + 1 < len(query) and query[i + 1] == '"'
        ):
            start = i
            if query[i] == "c":
                i += 1  # Skip the 'c' prefix
            i += 1  # Skip opening quote
            while i < len(query) and query[i] != '"':
                if query[i] == "\\" and i + 1 < len(query):
                    i += 2  # Skip escaped character
                else:
                    i += 1
            if i < len(query):
                i += 1  # Skip closing quote
            tokens.append((query[start:i], "quoted"))
            continue

        # Check for keywords (AND, OR) - must be at word boundaries
        if (
            query[i : i + 3].upper() == "AND"
            and (i + 3 >= len(query) or not query[i + 3].isalnum())
            and (i == 0 or not query[i - 1].isalnum())
        ):
            tokens.append((query[i : i + 3], "keyword"))
            i += 3
            continue
        if (
            query[i : i + 2].upper() == "OR"
            and (i + 2 >= len(query) or not query[i + 2].isalnum())
            and (i == 0 or not query[i - 1].isalnum())
        ):
            tokens.append((query[i : i + 2], "keyword"))
            i += 2
            continue

        # Collect word (bare word or property key)
        if query[i].isalpha() or query[i] == "_":
            start = i
            while i < len(query) and _is_bare_word_char(query[i]):
                i += 1
            word = query[start:i]

            # Check if this is a property key (followed by :)
            if i < len(query) and query[i] == ":":
                word_lower = word.lower()
                if word_lower in ("status", "project", "ancestor"):
                    # Property key
                    tokens.append((word + ":", "property_key"))
                    i += 1  # Skip the colon

                    # Now parse the property value
                    if i < len(query) and query[i] == '"':
                        # Quoted value
                        start = i
                        i += 1
                        while i < len(query) and query[i] != '"':
                            if query[i] == "\\" and i + 1 < len(query):
                                i += 2
                            else:
                                i += 1
                        if i < len(query):
                            i += 1
                        tokens.append((query[start:i], "property_value"))
                    elif i < len(query) and (query[i].isalpha() or query[i] == "_"):
                        # Bare word value
                        start = i
                        while i < len(query) and _is_bare_word_char(query[i]):
                            i += 1
                        tokens.append((query[start:i], "property_value"))
                    continue

            # Not a property - it's a regular term
            # But first check if it's a keyword we missed
            word_upper = word.upper()
            if word_upper == "AND":
                tokens.append((word, "keyword"))
            elif word_upper == "OR":
                tokens.append((word, "keyword"))
            else:
                tokens.append((word, "term"))
            continue

        # Collect unquoted term (until whitespace, paren, or special char)
        start = i
        while i < len(query) and not query[i].isspace() and query[i] not in '()!"':
            # Stop if we hit AND or OR keyword
            remaining = query[i:]
            if remaining[:3].upper() == "AND" and (
                len(remaining) == 3 or not remaining[3].isalnum()
            ):
                break
            if remaining[:2].upper() == "OR" and (
                len(remaining) == 2 or not remaining[2].isalnum()
            ):
                break
            i += 1
        if i > start:
            tokens.append((query[start:i], "term"))

    return tokens


# Token type to Rich style mapping
QUERY_TOKEN_STYLES: dict[str, str] = {
    "keyword": "bold #87AFFF",
    "negation": "bold #FF5F5F",
    "error_suffix": "bold #FFFFFF on #AF0000",
    "rejected_proposal": "bold #FF5F5F on #444444",
    "running_agent": "bold #FFFFFF on #FF8C00",
    "killed_agent": "bold #FF8C00 on #444444",
    "running_process": "bold #3D2B1F on #FFD700",
    "pending_dead_process": "bold #FFD700 on #444444",
    "killed_process": "bold #B8A800 on #444444",
    "quoted": "#808080",
    "term": "#00D7AF",
    "paren": "bold #FFFFFF",
    "shorthand": "bold #AF87D7",
    "property_key": "bold #87D7FF",
    "property_value": "#D7AF5F",
    "whitespace": "",
}
