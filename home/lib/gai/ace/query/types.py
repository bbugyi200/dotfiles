"""AST types for the query language."""

from __future__ import annotations

from dataclasses import dataclass

# The internal expansion of the !!! shorthand (matches error suffix markers)
ERROR_SUFFIX_QUERY = " - (!: "


@dataclass
class StringMatch:
    """A string match expression.

    Attributes:
        value: The string to match against.
        case_sensitive: If True, match is case-sensitive. Default is False.
        is_error_suffix: If True, this represents the !!! shorthand for error
            suffix search. Used by to_canonical_string() to output "!!!" instead
            of the internal expansion.
    """

    value: str
    case_sensitive: bool = False
    is_error_suffix: bool = False


@dataclass
class NotExpr:
    """Negation expression.

    Attributes:
        operand: The expression to negate.
    """

    operand: QueryExpr


@dataclass
class AndExpr:
    """AND expression (conjunction).

    Attributes:
        operands: List of expressions that must all match.
    """

    operands: list[QueryExpr]


@dataclass
class OrExpr:
    """OR expression (disjunction).

    Attributes:
        operands: List of expressions where at least one must match.
    """

    operands: list[QueryExpr]


# Union of all expression types
QueryExpr = StringMatch | NotExpr | AndExpr | OrExpr


def _escape_string_value(value: str) -> str:
    """Escape special characters in a string value for display."""
    result = value.replace("\\", "\\\\")
    result = result.replace('"', '\\"')
    result = result.replace("\n", "\\n")
    result = result.replace("\r", "\\r")
    result = result.replace("\t", "\\t")
    return result


def to_canonical_string(expr: QueryExpr) -> str:
    """Convert a query expression to its canonical string representation.

    This produces a normalized form with:
    - Explicit AND keywords between atoms
    - Uppercase AND/OR keywords
    - Quoted strings (not @-shorthand)

    Args:
        expr: The query expression to convert.

    Returns:
        The canonical string representation.

    Examples:
        >>> to_canonical_string(StringMatch("foo"))
        '"foo"'
        >>> to_canonical_string(AndExpr([StringMatch("a"), StringMatch("b")]))
        '"a" AND "b"'
    """
    if isinstance(expr, StringMatch):
        # Special case: error suffix shorthand outputs as !!!
        if expr.is_error_suffix:
            return "!!!"
        escaped = _escape_string_value(expr.value)
        if expr.case_sensitive:
            return f'c"{escaped}"'
        return f'"{escaped}"'

    if isinstance(expr, NotExpr):
        inner = to_canonical_string(expr.operand)
        # Add parens around complex inner expressions
        if isinstance(expr.operand, (AndExpr, OrExpr)):
            return f"!({inner})"
        return f"!{inner}"

    if isinstance(expr, AndExpr):
        parts = []
        for op in expr.operands:
            inner = to_canonical_string(op)
            # Wrap OR expressions in parens to preserve precedence
            if isinstance(op, OrExpr):
                inner = f"({inner})"
            parts.append(inner)
        return " AND ".join(parts)

    if isinstance(expr, OrExpr):
        parts = []
        for op in expr.operands:
            inner = to_canonical_string(op)
            # Wrap AND expressions in parens to preserve precedence
            if isinstance(op, AndExpr):
                inner = f"({inner})"
            parts.append(inner)
        return " OR ".join(parts)

    # Should never reach here with proper typing
    raise TypeError(f"Unknown expression type: {type(expr)}")
