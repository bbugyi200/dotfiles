"""Tokenizer for the query language."""

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    """Token types for the query language."""

    STRING = auto()  # Quoted string (with optional 'c' prefix)
    PROPERTY = auto()  # Property filter: key:value (status:, project:, ancestor:)
    AND = auto()  # AND keyword
    OR = auto()  # OR keyword
    NOT = auto()  # ! operator
    ERROR_SUFFIX = auto()  # !!! shorthand (or standalone !) for error suffix search
    NOT_ERROR_SUFFIX = auto()  # !! shorthand for NOT !!! (no error suffix)
    RUNNING_AGENT = auto()  # @@@ shorthand (or standalone @) for running agent search
    NOT_RUNNING_AGENT = auto()  # !@ shorthand for NOT @@@ (no running agents)
    RUNNING_PROCESS = (
        auto()
    )  # $$$ shorthand (or standalone $) for running process search
    NOT_RUNNING_PROCESS = auto()  # !$ shorthand for NOT $$$ (no running processes)
    ANY_SPECIAL = auto()  # !@$ shorthand for (!!! OR @@@ OR $$$)
    LPAREN = auto()  # (
    RPAREN = auto()  # )
    EOF = auto()  # End of input


# Valid property keys for property filters
VALID_PROPERTY_KEYS = frozenset({"status", "project", "ancestor", "name", "sibling"})

# Status shorthand mappings: %d -> DRAFTED, %m -> MAILED, etc.
STATUS_SHORTHANDS = {
    "d": "DRAFTED",
    "m": "MAILED",
    "r": "REVERTED",
    "s": "SUBMITTED",
    "w": "WIP",
}


@dataclass
class Token:
    """A token from the query language.

    Attributes:
        type: The type of token.
        value: The token's value (string content for STRING tokens, property value
            for PROPERTY tokens).
        case_sensitive: For STRING tokens, whether the match is case-sensitive.
        position: Position in input for error messages.
        property_key: For PROPERTY tokens, the property key (status, project, ancestor).
    """

    type: TokenType
    value: str
    case_sensitive: bool = False
    position: int = 0
    property_key: str | None = None


class TokenizerError(Exception):
    """Raised when tokenization fails."""

    def __init__(self, message: str, position: int) -> None:
        self.position = position
        super().__init__(f"{message} at position {position}")


def _skip_whitespace(query: str, pos: int) -> int:
    """Skip whitespace characters and return new position."""
    while pos < len(query) and query[pos] in " \t\r\n":
        pos += 1
    return pos


def _parse_string(query: str, pos: int, case_sensitive: bool) -> tuple[Token, int]:
    """Parse a quoted string starting at pos (after the opening quote).

    Args:
        query: The query string.
        pos: Position of the opening quote.
        case_sensitive: Whether this is a case-sensitive string (c"...").

    Returns:
        Tuple of (Token, new_position).

    Raises:
        TokenizerError: If the string is not properly terminated.
    """
    start_pos = pos
    pos += 1  # Skip opening quote
    value_chars: list[str] = []

    while pos < len(query):
        char = query[pos]

        if char == '"':
            # End of string
            return (
                Token(
                    type=TokenType.STRING,
                    value="".join(value_chars),
                    case_sensitive=case_sensitive,
                    position=start_pos,
                ),
                pos + 1,
            )
        elif char == "\\":
            # Escape sequence
            if pos + 1 >= len(query):
                raise TokenizerError("Unterminated escape sequence", pos)
            next_char = query[pos + 1]
            if next_char == "\\":
                value_chars.append("\\")
            elif next_char == '"':
                value_chars.append('"')
            elif next_char == "n":
                value_chars.append("\n")
            elif next_char == "r":
                value_chars.append("\r")
            elif next_char == "t":
                value_chars.append("\t")
            else:
                raise TokenizerError(f"Invalid escape sequence: \\{next_char}", pos)
            pos += 2
        else:
            value_chars.append(char)
            pos += 1

    raise TokenizerError("Unterminated string", start_pos)


def _is_bare_word_char(char: str) -> bool:
    """Check if a character can be part of a bare word (foo, my_test-value)."""
    return char.isalnum() or char in "_-"


def _parse_property_value(query: str, pos: int) -> tuple[str, int]:
    """Parse a property value (bare word or quoted string).

    Args:
        query: The query string.
        pos: Current position (at start of value).

    Returns:
        Tuple of (value, new_position).

    Raises:
        TokenizerError: If value is empty or malformed.
    """
    if pos >= len(query):
        raise TokenizerError("Expected property value", pos)

    # Check for quoted value
    if query[pos] == '"':
        start_pos = pos
        pos += 1  # Skip opening quote
        value_chars: list[str] = []
        while pos < len(query):
            char = query[pos]
            if char == '"':
                return "".join(value_chars), pos + 1
            elif char == "\\":
                if pos + 1 >= len(query):
                    raise TokenizerError("Unterminated escape sequence", pos)
                next_char = query[pos + 1]
                if next_char == "\\":
                    value_chars.append("\\")
                elif next_char == '"':
                    value_chars.append('"')
                elif next_char == "n":
                    value_chars.append("\n")
                elif next_char == "r":
                    value_chars.append("\r")
                elif next_char == "t":
                    value_chars.append("\t")
                else:
                    raise TokenizerError(f"Invalid escape sequence: \\{next_char}", pos)
                pos += 2
            else:
                value_chars.append(char)
                pos += 1
        raise TokenizerError("Unterminated string", start_pos)

    # Bare word value
    start = pos
    while pos < len(query) and _is_bare_word_char(query[pos]):
        pos += 1
    if pos == start:
        raise TokenizerError("Expected property value", pos)
    return query[start:pos], pos


def tokenize(query: str) -> Iterator[Token]:
    """Tokenize a query string into tokens.

    Args:
        query: The query string to tokenize.

    Yields:
        Token objects.

    Raises:
        TokenizerError: If tokenization fails.
    """
    pos = 0
    length = len(query)

    while pos < length:
        pos = _skip_whitespace(query, pos)
        if pos >= length:
            break

        char = query[pos]

        # Check for case-sensitive string prefix
        if char == "c" and pos + 1 < length and query[pos + 1] == '"':
            token, pos = _parse_string(query, pos + 1, case_sensitive=True)
            yield token
        # Regular string
        elif char == '"':
            token, pos = _parse_string(query, pos, case_sensitive=False)
            yield token
        # NOT operator or ERROR_SUFFIX/NOT_RUNNING_AGENT shorthand
        elif char == "!":
            # Check for !!! (error suffix shorthand)
            if query[pos : pos + 3] == "!!!":
                yield Token(type=TokenType.ERROR_SUFFIX, value="!!!", position=pos)
                pos += 3
            # Check for !! (NOT !!! shorthand) - only when standalone
            # Standalone means: at end, or followed by whitespace
            elif query[pos : pos + 2] == "!!" and (
                pos + 2 >= length or query[pos + 2] in " \t\r\n"
            ):
                yield Token(type=TokenType.NOT_ERROR_SUFFIX, value="!!", position=pos)
                pos += 2
            # Check for !@ (NOT @@@ shorthand) - NOT running agent
            elif query[pos : pos + 2] == "!@" and (
                pos + 2 >= length or query[pos + 2] in " \t\r\n"
            ):
                yield Token(type=TokenType.NOT_RUNNING_AGENT, value="!@", position=pos)
                pos += 2
            # Check for !$ (NOT $$$ shorthand) - NOT running process
            elif query[pos : pos + 2] == "!$" and (
                pos + 2 >= length or query[pos + 2] in " \t\r\n"
            ):
                yield Token(
                    type=TokenType.NOT_RUNNING_PROCESS, value="!$", position=pos
                )
                pos += 2
            # Check for standalone ! (transforms to !!!)
            # Standalone means: at end, or followed by whitespace
            elif pos + 1 >= length or query[pos + 1] in " \t\r\n":
                yield Token(type=TokenType.ERROR_SUFFIX, value="!", position=pos)
                pos += 1
            else:
                # Regular NOT operator (e.g., !"foo")
                yield Token(type=TokenType.NOT, value="!", position=pos)
                pos += 1
        # RUNNING_AGENT shorthand (@@@, @)
        elif char == "@":
            # Check for @@@ (running agent shorthand)
            if query[pos : pos + 3] == "@@@":
                yield Token(type=TokenType.RUNNING_AGENT, value="@@@", position=pos)
                pos += 3
            # Check for standalone @ (transforms to @@@)
            # Standalone means: at end, or followed by whitespace
            elif pos + 1 >= length or query[pos + 1] in " \t\r\n":
                yield Token(type=TokenType.RUNNING_AGENT, value="@", position=pos)
                pos += 1
            else:
                raise TokenizerError(f"Unexpected character: {char}", pos)
        # RUNNING_PROCESS shorthand ($$$, $)
        elif char == "$":
            # Check for $$$ (running process shorthand)
            if query[pos : pos + 3] == "$$$":
                yield Token(type=TokenType.RUNNING_PROCESS, value="$$$", position=pos)
                pos += 3
            # Check for standalone $ (transforms to $$$)
            # Standalone means: at end, or followed by whitespace
            elif pos + 1 >= length or query[pos + 1] in " \t\r\n":
                yield Token(type=TokenType.RUNNING_PROCESS, value="$", position=pos)
                pos += 1
            else:
                raise TokenizerError(f"Unexpected character: {char}", pos)
        # ANY_SPECIAL shorthand (*) - matches !!! OR @@@ OR $$$
        elif char == "*":
            # Check for standalone * (any special: error OR running agent OR running process)
            if pos + 1 >= length or query[pos + 1] in " \t\r\n":
                yield Token(type=TokenType.ANY_SPECIAL, value="*", position=pos)
                pos += 1
            else:
                raise TokenizerError(f"Unexpected character: {char}", pos)
        # Parentheses
        elif char == "(":
            yield Token(type=TokenType.LPAREN, value="(", position=pos)
            pos += 1
        elif char == ")":
            yield Token(type=TokenType.RPAREN, value=")", position=pos)
            pos += 1
        # Status shorthand: %d, %m, %s, %r
        elif char == "%":
            start = pos
            pos += 1
            if pos < length and query[pos].lower() in STATUS_SHORTHANDS:
                status_value = STATUS_SHORTHANDS[query[pos].lower()]
                pos += 1
                yield Token(
                    type=TokenType.PROPERTY,
                    value=status_value,
                    position=start,
                    property_key="status",
                )
            else:
                raise TokenizerError(
                    "Invalid status shorthand (use %d, %m, %r, %s, or %w)", start
                )
        # Project shorthand: +identifier
        elif char == "+":
            start = pos
            pos += 1
            if pos < length and (query[pos].isalpha() or query[pos] == "_"):
                value, pos = _parse_property_value(query, pos)
                yield Token(
                    type=TokenType.PROPERTY,
                    value=value,
                    position=start,
                    property_key="project",
                )
            else:
                raise TokenizerError("Expected project name after '+'", start)
        # Ancestor shorthand: ^identifier
        elif char == "^":
            start = pos
            pos += 1
            if pos < length and (query[pos].isalpha() or query[pos] == "_"):
                value, pos = _parse_property_value(query, pos)
                yield Token(
                    type=TokenType.PROPERTY,
                    value=value,
                    position=start,
                    property_key="ancestor",
                )
            else:
                raise TokenizerError("Expected ancestor name after '^'", start)
        # Name shorthand: &identifier
        elif char == "&":
            start = pos
            pos += 1
            if pos < length and (query[pos].isalpha() or query[pos] == "_"):
                value, pos = _parse_property_value(query, pos)
                yield Token(
                    type=TokenType.PROPERTY,
                    value=value,
                    position=start,
                    property_key="name",
                )
            else:
                raise TokenizerError("Expected name after '&'", start)
        # Keywords (AND/OR), bare words, or property filters (key:value)
        elif char.isalpha() or char == "_":
            start = pos
            while pos < length and _is_bare_word_char(query[pos]):
                pos += 1
            word = query[start:pos]
            word_upper = word.upper()
            word_lower = word.lower()

            if word_upper == "AND":
                yield Token(type=TokenType.AND, value=word, position=start)
            elif word_upper == "OR":
                yield Token(type=TokenType.OR, value=word, position=start)
            elif word_upper == "NOT":
                yield Token(type=TokenType.NOT, value=word, position=start)
            # Check for property filter syntax: key:value
            elif pos < length and query[pos] == ":":
                if word_lower in VALID_PROPERTY_KEYS:
                    pos += 1  # Skip the colon
                    value, pos = _parse_property_value(query, pos)
                    yield Token(
                        type=TokenType.PROPERTY,
                        value=value,
                        position=start,
                        property_key=word_lower,
                    )
                else:
                    raise TokenizerError(
                        f"Unknown property key: {word} (valid keys: status, project, ancestor, name, sibling)",
                        start,
                    )
            else:
                # Bare word treated as case-insensitive string
                yield Token(
                    type=TokenType.STRING,
                    value=word,
                    case_sensitive=False,
                    position=start,
                )
        else:
            raise TokenizerError(f"Unexpected character: {char}", pos)

    yield Token(type=TokenType.EOF, value="", position=pos)
