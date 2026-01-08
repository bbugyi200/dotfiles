"""Parser for the query language.

Grammar (EBNF):
    query        = ws?, or_expr, ws? ;
    or_expr      = and_expr, { ws, "OR",  ws, and_expr } ;
    and_expr     = unary_expr, { [ws, "AND"], ws, unary_expr } ;
    unary_expr   = { "!" }, primary ;
    primary      = string | property | error_suffix | not_error_suffix
                 | running_agent | not_running_agent | "(", or_expr, ")" ;
    string       = bare_word | [c], '"', { string_char }, '"' ;
    bare_word    = (letter | "_"), { letter | digit | "_" | "-" } ;
    property     = property_key, ":", property_value ;
    property_key = "status" | "project" | "ancestor" ;
    property_value = bare_word | quoted_string ;
    error_suffix = "!!!" | "!" (when standalone) ;
    not_error_suffix = "!!" (when standalone) ;
    running_agent = "@@@" | "@" (when standalone) ;
    not_running_agent = "!@" (when standalone) ;
    any_special = "!@$" (when standalone) ;

Precedence (tightest to loosest):
    1. ! (NOT)
    2. AND (explicit or implicit via juxtaposition)
    3. OR
    Parentheses override precedence.

Shorthands:
    - foo is equivalent to "foo" (bare word syntax)
    - "a" "b" is equivalent to "a" AND "b" (implicit AND)
    - !!! or standalone ! matches changespecs with ANY error suffix
    - !! (standalone) is equivalent to NOT !!! (matches changespecs with NO error suffix)
    - @@@ or standalone @ matches changespecs with running agents (CRS or fix-hook)
    - !@ (standalone) is equivalent to NOT @@@ (matches changespecs with NO running agents)
    - %d, %m, %s, %r expand to status:DRAFTED, status:MAILED, status:SUBMITTED, status:REVERTED
    - +project expands to project:project (match changespecs in a project)
    - ^name expands to ancestor:name (match changespecs with name or parent chain containing name)
"""

from .tokenizer import Token, TokenizerError, TokenType, tokenize
from .types import (
    ERROR_SUFFIX_QUERY,
    RUNNING_AGENT_QUERY,
    RUNNING_PROCESS_QUERY,
    AndExpr,
    NotExpr,
    OrExpr,
    PropertyMatch,
    QueryExpr,
    StringMatch,
)


class QueryParseError(Exception):
    """Raised when parsing fails."""

    def __init__(self, message: str, position: int = 0) -> None:
        self.position = position
        super().__init__(f"{message} (at position {position})")


class _Parser:
    """Recursive descent parser for the query language."""

    def __init__(self, query: str) -> None:
        self.query = query
        try:
            self.tokens = list(tokenize(query))
        except TokenizerError as e:
            raise QueryParseError(str(e), e.position) from e
        self.pos = 0

    def _current(self) -> Token:
        """Get the current token."""
        if self.pos >= len(self.tokens):
            return self.tokens[-1]  # Return EOF
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        """Advance to the next token and return the previous one."""
        token = self._current()
        self.pos += 1
        return token

    def _expect(self, token_type: TokenType) -> Token:
        """Expect a specific token type, raise error if not found."""
        token = self._current()
        if token.type != token_type:
            raise QueryParseError(
                f"Expected {token_type.name}, got {token.type.name}", token.position
            )
        return self._advance()

    def _check(self, token_type: TokenType) -> bool:
        """Check if current token is of a specific type."""
        return self._current().type == token_type

    def parse(self) -> QueryExpr:
        """Parse the query and return the AST."""
        if self._check(TokenType.EOF):
            raise QueryParseError("Empty query", 0)

        expr = self._parse_or_expr()

        if not self._check(TokenType.EOF):
            token = self._current()
            raise QueryParseError(
                f"Unexpected token: {token.value or token.type.name}", token.position
            )

        return expr

    def _parse_or_expr(self) -> QueryExpr:
        """Parse OR expression: and_expr { OR and_expr }."""
        left = self._parse_and_expr()

        operands = [left]
        while self._check(TokenType.OR):
            self._advance()  # consume OR
            right = self._parse_and_expr()
            operands.append(right)

        if len(operands) == 1:
            return operands[0]
        return OrExpr(operands=operands)

    def _can_start_unary(self) -> bool:
        """Check if current token can start a unary expression."""
        return self._current().type in (
            TokenType.STRING,
            TokenType.PROPERTY,
            TokenType.NOT,
            TokenType.LPAREN,
            TokenType.ERROR_SUFFIX,
            TokenType.NOT_ERROR_SUFFIX,
            TokenType.RUNNING_AGENT,
            TokenType.NOT_RUNNING_AGENT,
            TokenType.RUNNING_PROCESS,
            TokenType.NOT_RUNNING_PROCESS,
            TokenType.ANY_SPECIAL,
        )

    def _parse_and_expr(self) -> QueryExpr:
        """Parse AND expression: unary_expr { [AND] unary_expr }.

        Supports implicit AND: "a" "b" is equivalent to "a" AND "b".
        """
        left = self._parse_unary_expr()

        operands = [left]
        while True:
            if self._check(TokenType.AND):
                self._advance()  # consume explicit AND
                right = self._parse_unary_expr()
                operands.append(right)
            elif self._can_start_unary():
                # Implicit AND: no AND keyword but next token can start unary
                right = self._parse_unary_expr()
                operands.append(right)
            else:
                break

        if len(operands) == 1:
            return operands[0]
        return AndExpr(operands=operands)

    def _parse_unary_expr(self) -> QueryExpr:
        """Parse unary expression: { ! } primary."""
        not_count = 0
        while self._check(TokenType.NOT):
            self._advance()
            not_count += 1

        expr = self._parse_primary()

        # Apply NOT operators from innermost to outermost
        for _ in range(not_count):
            expr = NotExpr(operand=expr)

        return expr

    def _parse_primary(self) -> QueryExpr:
        """Parse primary expression: string | property | error_suffix | ( or_expr )."""
        token = self._current()

        if token.type == TokenType.STRING:
            self._advance()
            return StringMatch(value=token.value, case_sensitive=token.case_sensitive)

        if token.type == TokenType.PROPERTY:
            self._advance()
            # property_key is guaranteed to be set for PROPERTY tokens
            assert token.property_key is not None
            return PropertyMatch(key=token.property_key, value=token.value)

        if token.type == TokenType.ERROR_SUFFIX:
            self._advance()
            # Expand to the internal query string, marked as error suffix
            return StringMatch(
                value=ERROR_SUFFIX_QUERY, case_sensitive=False, is_error_suffix=True
            )

        if token.type == TokenType.NOT_ERROR_SUFFIX:
            self._advance()
            # !! is shorthand for NOT !!! - create identical AST
            return NotExpr(
                operand=StringMatch(
                    value=ERROR_SUFFIX_QUERY, case_sensitive=False, is_error_suffix=True
                )
            )

        if token.type == TokenType.RUNNING_AGENT:
            self._advance()
            # Expand to the internal marker, marked as running agent
            return StringMatch(
                value=RUNNING_AGENT_QUERY, case_sensitive=False, is_running_agent=True
            )

        if token.type == TokenType.NOT_RUNNING_AGENT:
            self._advance()
            # !@ is shorthand for NOT @@@ - create identical AST
            return NotExpr(
                operand=StringMatch(
                    value=RUNNING_AGENT_QUERY,
                    case_sensitive=False,
                    is_running_agent=True,
                )
            )

        if token.type == TokenType.RUNNING_PROCESS:
            self._advance()
            # Expand to the internal marker, marked as running process
            return StringMatch(
                value=RUNNING_PROCESS_QUERY,
                case_sensitive=False,
                is_running_process=True,
            )

        if token.type == TokenType.NOT_RUNNING_PROCESS:
            self._advance()
            # !$ is shorthand for NOT $$$ - create identical AST
            return NotExpr(
                operand=StringMatch(
                    value=RUNNING_PROCESS_QUERY,
                    case_sensitive=False,
                    is_running_process=True,
                )
            )

        if token.type == TokenType.ANY_SPECIAL:
            self._advance()
            # !@$ is shorthand for (!!! OR @@@ OR $$$)
            return OrExpr(
                operands=[
                    StringMatch(
                        value=ERROR_SUFFIX_QUERY,
                        case_sensitive=False,
                        is_error_suffix=True,
                    ),
                    StringMatch(
                        value=RUNNING_AGENT_QUERY,
                        case_sensitive=False,
                        is_running_agent=True,
                    ),
                    StringMatch(
                        value=RUNNING_PROCESS_QUERY,
                        case_sensitive=False,
                        is_running_process=True,
                    ),
                ]
            )

        if token.type == TokenType.LPAREN:
            self._advance()  # consume (
            expr = self._parse_or_expr()
            self._expect(TokenType.RPAREN)  # consume )
            return expr

        raise QueryParseError(
            f"Expected string or '(', got {token.value or token.type.name}",
            token.position,
        )


def parse_query(query: str) -> QueryExpr:
    """Parse a query string into an AST.

    Args:
        query: The query string to parse.

    Returns:
        The parsed query expression tree.

    Raises:
        QueryParseError: If the query is malformed.

    Examples:
        >>> parse_query('"foobar"')
        StringMatch(value='foobar', case_sensitive=False)

        >>> parse_query('c"FooBar"')
        StringMatch(value='FooBar', case_sensitive=True)

        >>> parse_query('"a" AND "b"')
        AndExpr(operands=[StringMatch(value='a', ...), StringMatch(value='b', ...)])
    """
    parser = _Parser(query)
    return parser.parse()
