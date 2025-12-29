"""AST types for the query language."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StringMatch:
    """A string match expression.

    Attributes:
        value: The string to match against.
        case_sensitive: If True, match is case-sensitive. Default is False.
    """

    value: str
    case_sensitive: bool = False


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
