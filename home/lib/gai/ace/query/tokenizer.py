"""Tokenizer for the query language."""

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    """Token types for the query language."""

    STRING = auto()  # Quoted string (with optional 'c' prefix)
    AND = auto()  # AND keyword
    OR = auto()  # OR keyword
    NOT = auto()  # ! operator
    LPAREN = auto()  # (
    RPAREN = auto()  # )
    EOF = auto()  # End of input


@dataclass
class Token:
    """A token from the query language.

    Attributes:
        type: The type of token.
        value: The token's value (string content for STRING tokens).
        case_sensitive: For STRING tokens, whether the match is case-sensitive.
        position: Position in input for error messages.
    """

    type: TokenType
    value: str
    case_sensitive: bool = False
    position: int = 0


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


def _is_keyword_char(char: str) -> bool:
    """Check if a character can be part of a keyword (AND/OR)."""
    return char.isalpha()


def _is_bare_string_char(char: str) -> bool:
    """Check if a character can be part of a bare string (@foo)."""
    return char.isalnum() or char in "_-"


def _parse_bare_string(query: str, pos: int) -> tuple[Token, int]:
    """Parse a bare string starting at pos (after the @ symbol).

    Args:
        query: The query string.
        pos: Position of the @ symbol.

    Returns:
        Tuple of (Token, new_position).

    Raises:
        TokenizerError: If the bare string is empty.
    """
    start_pos = pos
    pos += 1  # Skip @
    value_start = pos

    while pos < len(query) and _is_bare_string_char(query[pos]):
        pos += 1

    if pos == value_start:
        raise TokenizerError("Empty bare string after @", start_pos)

    value = query[value_start:pos]
    return (
        Token(
            type=TokenType.STRING,
            value=value,
            case_sensitive=False,
            position=start_pos,
        ),
        pos,
    )


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
        # Bare string shorthand (@foo -> "foo")
        elif char == "@":
            token, pos = _parse_bare_string(query, pos)
            yield token
        # NOT operator
        elif char == "!":
            yield Token(type=TokenType.NOT, value="!", position=pos)
            pos += 1
        # Parentheses
        elif char == "(":
            yield Token(type=TokenType.LPAREN, value="(", position=pos)
            pos += 1
        elif char == ")":
            yield Token(type=TokenType.RPAREN, value=")", position=pos)
            pos += 1
        # Keywords (AND/OR)
        elif _is_keyword_char(char):
            start = pos
            while pos < length and _is_keyword_char(query[pos]):
                pos += 1
            keyword = query[start:pos]
            keyword_upper = keyword.upper()

            if keyword_upper == "AND":
                yield Token(type=TokenType.AND, value=keyword, position=start)
            elif keyword_upper == "OR":
                yield Token(type=TokenType.OR, value=keyword, position=start)
            else:
                raise TokenizerError(f"Unknown keyword: {keyword}", start)
        else:
            raise TokenizerError(f"Unexpected character: {char}", pos)

    yield Token(type=TokenType.EOF, value="", position=pos)
